#!/usr/bin/env python3
"""Bring the source into the work folder, whatever it is: a URL, an .html file,
a Word .docx, a PDF, or a Markdown / plain-text file.

    python extract.py SOURCE [--work DIR] [--selector CSS] [--lang xx]

Writes into WORK (default ./work):
  source.docx / source.pdf / source.html / url.txt
                                        the source as received
  source-content.html                   the cleaned main content (web sources only)
  source.md                             the source text as Markdown: read this, and
                                        quote its headings in the source map
  input.md                              the "input" block for the companion report:
                                        what was given, the URL written out or the
                                        file name, when, and which part was used
  structure.json                        what build.py needs later: source type, title,
                                        language, the page's tag/class map, reference docx
and prints a short summary plus the next step.

Web sources need beautifulsoup4, lxml and markdownify; PDF sources need pdfminer.six
(pip install -r requirements.txt). Word sources need pandoc (found on PATH or
downloaded to a local cache on first use).
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from etr_common import base_lang, ensure_pandoc, read_text, run, write_text  # noqa: E402

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) easy-to-read-skill/1.0"

# Page chrome that is not content. Matched against each class / id token. State classes
# such as "has-breadcrumb" or "is-menu-open" describe the container, not chrome, so
# tokens with those prefixes are ignored.
CHROME_TOKEN = re.compile(
    r"^(?!has-|is-|with-|no-|show-)(?:.*[-_])?(breadcrumbs?|sidemenu|side-menu|menu|navigation|nav|cookie|cookies|"
    r"toolbar|skip-?link|share|social|visually-hidden|sr-only|hidden)(?:[-_].*)?$",
    re.I,
)
CHROME_SELECTORS = (
    "script, style, noscript, svg, iframe, form, nav, header, footer, aside, "
    "[role=navigation], [role=banner], [role=contentinfo], [role=search], [aria-hidden=true]"
)
# Most specific first; the first one with enough text wins, so a page that wraps its
# news teasers and side menus in <body> or <main> still yields the article itself.
MAIN_CANDIDATES = ["[role=main]", "article", "#main-content", "#content", "#hlavny-obsah", "#obsah",
                   ".main-content", ".page-content", ".content", "main", "body"]
MIN_MAIN_CHARS = 300
MAPPED_TAGS = ["h1", "h2", "h3", "h4", "p", "ul", "ol", "li", "a", "strong", "em", "table", "blockquote"]

# PDF: list markers at the start of a line, page-number lines, bold font names.
PDF_BULLET = re.compile(r"^\s*(?:([•●▪■◦○·‣⁃–—*-])|(\d{1,2}[.)])|([a-z][.)]))\s+")
PDF_PAGE_NO = re.compile(r"^\s*(?:strana|str\.|page|seite|s\.)?\s*\d+\s*(?:(?:z|zo|of|/|von|ze)\s*\d+)?\s*$", re.I)
PDF_BOLD = re.compile(r"bold|black|heavy|semibold|demi", re.I)
PDF_SYMBOL_FONT = re.compile(r"dingbat|wingding|webding|symbol", re.I)
MIN_CHARS_PER_PAGE = 30


def need(modules: list[str], what: str) -> None:
    try:
        for m in modules:
            __import__(m)
    except ImportError:
        print(
            f"{what} need {', '.join(modules)}.\n"
            f"Run:  python -m pip install -r {Path(__file__).parent / 'requirements.txt'}",
            file=sys.stderr,
        )
        sys.exit(2)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "sk,cs,en"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
        charset = r.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def now() -> str:
    return dt.datetime.now().isoformat(timespec="minutes")


# ---------------------------------------------------------------- web
def is_chrome(el) -> bool:
    tokens = list(el.get("class", [])) + ([el.get("id")] if el.get("id") else [])
    return any(CHROME_TOKEN.match(t) for t in tokens if t)


def _content_score(el) -> int:
    """Characters of text that are not link text (menus and teaser lists score low)."""
    text = el.get_text(" ", strip=True)
    links = " ".join(a.get_text(" ", strip=True) for a in el.find_all("a"))
    return len(text) - len(links)


def pick_main(soup, selector: str | None):
    """The most specific content container that still holds a real amount of text."""
    if selector:
        el = soup.select_one(selector)
        if el is None:
            print(f"selector {selector!r} matched nothing", file=sys.stderr)
            sys.exit(2)
        return el
    fallback, fallback_score = None, -1
    for sel in MAIN_CANDIDATES:
        for el in soup.select(sel):
            score = _content_score(el)
            if score >= MIN_MAIN_CHARS:
                return el
            if score > fallback_score:
                fallback, fallback_score = el, score
    return fallback


def clean(el) -> None:
    for t in el.select(CHROME_SELECTORS):
        t.decompose()
    for t in list(el.find_all(True)):
        if t is not el and t.parent is not None and is_chrome(t):
            t.decompose()


def class_map(el) -> dict[str, str]:
    """For each content tag, the class string the page uses most (may be '')."""
    out = {}
    for tag in MAPPED_TAGS:
        counter = collections.Counter()
        for node in el.find_all(tag):
            cls = " ".join(node.get("class", []))
            if tag in ("p", "li", "a", "strong", "em") or tag.startswith("h"):
                if len(node.get_text(strip=True)) < 2:
                    continue
            counter[cls] += 1
        if counter:
            out[tag] = counter.most_common(1)[0][0]
    return out


def tidy_markdown(md: str) -> str:
    md = md.replace(" ", " ")
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


def short_selector(el) -> str:
    s = el.name
    if el.get("id"):
        s += "#" + el.get("id")
    elif el.get("class"):
        s += "." + ".".join(el.get("class"))
    return s


def extract_web(source: str, work: Path, selector: str | None, lang: str | None) -> dict:
    need(["bs4", "lxml", "markdownify"], "Web sources")
    from bs4 import BeautifulSoup
    from markdownify import markdownify

    is_url = re.match(r"https?://", source, re.I) is not None
    if is_url:
        html = fetch(source)
        write_text(work / "source.html", html)
        write_text(work / "url.txt", source + "\n")
    else:
        html = read_text(source)
        shutil.copy(source, work / "source.html")
    soup = BeautifulSoup(html, "lxml")
    page_lang = (soup.html.get("lang") if soup.html else None) or ""
    title_tag = soup.title.get_text(strip=True) if soup.title else ""
    canonical = ""
    for sel, attr in (("link[rel=canonical]", "href"), ("meta[property='og:url']", "content")):
        tag = soup.select_one(sel)
        if tag and tag.get(attr, "").startswith("http"):
            canonical = tag[attr]
            break
    main = pick_main(soup, selector)
    if main is None:
        print("no content found", file=sys.stderr)
        sys.exit(2)
    clean(main)
    h1 = main.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else title_tag.split("|")[0].split(",")[0].strip()
    cmap = class_map(main)
    write_text(work / "source-content.html", main.prettify())
    md = markdownify(str(main), heading_style="ATX", bullets="-")
    write_text(work / "source.md", tidy_markdown(md))
    struct = {
        "type": "web",
        "source": source,
        "fetched": now(),
        "title": title,
        "lang": base_lang(lang or page_lang or "sk"),
        "page_lang": page_lang,
        "main_selector": selector or f"<{main.name}"
        + (f' id="{main.get("id")}"' if main.get("id") else "")
        + (f' class="{" ".join(main.get("class", []))}"' if main.get("class") else "")
        + ">",
        "class_map": cmap,
    }
    struct["input"] = {
        "kind": "url" if is_url else "html",
        "url": source if is_url else "",
        "file": "" if is_url else Path(source).name,
        "size": 0 if is_url else Path(source).stat().st_size,
        "original_url": "" if is_url else canonical,
        "title": title,
        "when": struct["fetched"],
        "part": selector or short_selector(main),
    }
    return struct


# ---------------------------------------------------------------- docx
def docx_style_summary(path: Path) -> dict:
    info = {}
    try:
        with zipfile.ZipFile(path) as z:
            styles = z.read("word/styles.xml").decode("utf-8", "replace")
            core = z.read("docProps/core.xml").decode("utf-8", "replace") if "docProps/core.xml" in z.namelist() else ""
            theme = z.read("word/theme/theme1.xml").decode("utf-8", "replace") if "word/theme/theme1.xml" in z.namelist() else ""
    except (KeyError, zipfile.BadZipFile) as e:
        print(f"could not read styles from {path}: {e}", file=sys.stderr)
        return info
    m = re.search(r"<w:docDefaults>.*?</w:docDefaults>", styles, re.S)
    defaults = m.group(0) if m else ""
    font = re.search(r'w:ascii="([^"]+)"', defaults)
    theme_font = re.search(r'w:asciiTheme="([^"]+)"', defaults)
    if font:
        info["font"] = font.group(1)
    elif theme_font and theme:
        which = "minorFont" if "minor" in theme_font.group(1) else "majorFont"
        tf = re.search(rf"<a:{which}>.*?<a:latin typeface=\"([^\"]+)\"", theme, re.S)
        if tf:
            info["font"] = tf.group(1) + " (theme)"
    size = re.search(r'<w:sz w:val="(\d+)"', defaults)
    if size:
        info["size_pt"] = int(size.group(1)) / 2
    lang = re.search(r'<w:lang w:val="([^"]+)"', defaults)
    if lang:
        info["doc_lang"] = lang.group(1)
    t = re.search(r"<dc:title>([^<]*)</dc:title>", core)
    if t and t.group(1).strip():
        info["title"] = t.group(1).strip()
    just = re.search(r'<w:jc w:val="both"', styles)
    info["justified_styles"] = bool(just)
    return info


def extract_docx(source: str, work: Path, lang: str | None) -> dict:
    pandoc = ensure_pandoc()
    src = Path(source)
    ref = work / "source.docx"
    shutil.copy(src, ref)
    media = work / "media"
    run([pandoc, str(ref), "-t", "gfm", "--wrap=none", "--markdown-headings=atx",
         f"--extract-media={media}", "-o", str(work / "source.md")])
    md = read_text(work / "source.md")
    write_text(work / "source.md", tidy_markdown(md))
    info = docx_style_summary(ref)
    h1 = re.search(r"^#\s+(.+)$", md, re.M)
    title = info.get("title") or (h1.group(1).strip() if h1 else src.stem)
    return {
        "type": "docx",
        "source": str(src),
        "title": title,
        "lang": base_lang(lang or info.get("doc_lang") or "sk"),
        "reference": "source.docx",
        "source_styles": info,
        "input": {"kind": "docx", "file": src.name, "size": src.stat().st_size, "title": title, "when": now()},
    }


# ---------------------------------------------------------------- pdf
def _pdf_text(value) -> str:
    from pdfminer.pdftypes import resolve1
    from pdfminer.utils import decode_text

    value = resolve1(value)
    if isinstance(value, bytes):
        return decode_text(value).strip()
    if value is None:
        return ""
    return str(getattr(value, "name", value)).strip()


def _pdf_meta(path: Path) -> dict:
    from pdfminer.pdfdocument import PDFDocument, PDFPasswordIncorrect
    from pdfminer.pdfparser import PDFParser
    from pdfminer.pdftypes import resolve1

    try:
        with open(path, "rb") as f:
            doc = PDFDocument(PDFParser(f))
            info = doc.info[0] if doc.info else {}
            catalog = doc.catalog
            mark = resolve1(catalog.get("MarkInfo")) or {}
            return {
                "title": _pdf_text(info.get("Title")),
                "producer": _pdf_text(info.get("Producer")),
                "lang": _pdf_text(catalog.get("Lang")),
                "tagged": "StructTreeRoot" in catalog or bool(resolve1(mark.get("Marked")) if isinstance(mark, dict) else False),
            }
    except PDFPasswordIncorrect:
        print("The PDF is password-protected. Ask for an unprotected copy or the Word file.", file=sys.stderr)
        sys.exit(2)


def _pdf_lines(path: Path) -> list[list[list[dict]]]:
    """pages -> text boxes -> lines, each line with its text, median size, boldness and
    whether it starts with a glyph from a symbol font (a Wingdings or Dingbats bullet)."""
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LAParams, LTChar, LTTextContainer, LTTextLine

    pages = []
    for page in extract_pages(str(path), laparams=LAParams()):
        height = page.height or 842
        boxes = []
        for el in page:
            if not isinstance(el, LTTextContainer):
                continue
            lines = []
            for line in el:
                if not isinstance(line, LTTextLine):
                    continue
                chars = [c for c in line if isinstance(c, LTChar) and c.get_text().strip()]
                text = re.sub(r"\s+", " ", line.get_text()).strip()
                if not text or not chars:
                    continue
                symbol = bool(PDF_SYMBOL_FONT.search(chars[0].fontname))
                if symbol:
                    text = text[len(chars[0].get_text()):].strip()
                    chars = chars[1:]
                    if not text or not chars:
                        continue
                sizes = sorted(round(c.size * 2) / 2 for c in chars)
                bold = sum(1 for c in chars if PDF_BOLD.search(c.fontname)) > len(chars) / 2
                font = collections.Counter(c.fontname.split("+")[-1] for c in chars).most_common(1)[0][0]
                # In the top or bottom 12 % of the page: where running heads and feet live.
                edge = line.y1 > height * 0.88 or line.y0 < height * 0.12
                lines.append({"text": text, "size": sizes[len(sizes) // 2], "bold": bold, "n": len(chars),
                              "font": font, "bullet": symbol, "edge": edge})
            if lines:
                boxes.append(lines)
        pages.append(boxes)
    return pages


SOFT_HYPHEN = chr(0xAD)
SENTENCE_END = (".", "!", "?", ":", ";", "\u201c", '"', ")")


def _join(a: str, b: str) -> str:
    """Join two lines of one paragraph, undoing end-of-line hyphenation."""
    if not a:
        return b
    if a.endswith(SOFT_HYPHEN):
        return a[:-1] + b
    if a.endswith("-") and len(a) > 1 and a[-2].isalpha() and b[:1].islower():
        return a[:-1] + b
    return a + " " + b


def _heading_levels(lines: list[dict], body: float) -> dict[float, int]:
    """Map type sizes to heading levels. Sizes within 10 % of each other form one
    group; groups used at least three times are the document's heading levels (2, 3);
    rarer and larger groups (cover, title) are level 1."""
    counts = collections.Counter(ln["size"] for ln in lines if ln["size"] >= body * 1.12 and len(ln["text"]) < 150)
    groups: list[list[float]] = []
    for s in sorted(counts, reverse=True):
        if groups and groups[-1][-1] <= s * 1.1:
            groups[-1].append(s)
        else:
            groups.append([s])
    structural = [g for g in groups if sum(counts[s] for s in g) >= 3]
    top_structural = structural[0][0] if structural else 0
    level_of: dict[float, int] = {}
    for g in groups:
        if g in structural:
            lvl = min(structural.index(g) + 2, 3)
        else:
            lvl = 1 if g[0] > top_structural else 3
        for s in g:
            level_of[s] = lvl
    if not any(v == 1 for v in level_of.values()) and structural:
        # No separate title size: the largest structural group is level 1.
        for s in structural[0]:
            level_of[s] = 1
        for g in structural[1:]:
            for s in g:
                level_of[s] = min(structural.index(g) + 1, 3)
    return level_of


def _fix_split_letters(text: str) -> str:
    """Slovak and Czech PDFs set in fonts without the letters ľ ť ď Ľ often come out
    as l’ t’ d’ L’; a letter followed by an apostrophe and another letter is never
    right in these languages."""
    pairs = {"l": "ľ", "t": "ť", "d": "ď", "L": "Ľ", "T": "Ť", "D": "Ď"}
    return re.sub(r"([ltdLTD])[\u2019'](?=[a-záäčďéíĺľňóôŕšťúýž])", lambda m: pairs[m.group(1)], text)


def pdf_to_markdown(pages: list, lang: str = "sk") -> tuple[str, dict]:
    npages = len(pages)

    def key(t: str) -> str:
        return re.sub(r"\d+", "#", t.lower()).strip()

    # Running headers and footers: the same short line (digits ignored) at the top or
    # bottom edge of at least half of the pages, and of three pages at least. Lines
    # that repeat in the body of the page are content, however often they recur.
    per_page = collections.Counter()
    for boxes in pages:
        per_page.update({key(ln["text"]) for box in boxes for ln in box if ln["edge"] and len(ln["text"]) < 80})
    running = {k for k, c in per_page.items() if c >= max(3, npages / 2)}

    lines = [ln for boxes in pages for box in boxes for ln in box]
    weights, fonts = collections.Counter(), collections.Counter()
    for ln in lines:
        weights[ln["size"]] += ln["n"]
        fonts[ln["font"]] += ln["n"]
    body = weights.most_common(1)[0][0] if weights else 11.0
    level_of = _heading_levels(lines, body)
    bold_level = 3 if any(v == 2 for v in level_of.values()) else 2

    # A running line set as a heading on the first page is the cover title, not a
    # footer: that one occurrence stays.
    kept_title: set[str] = set()

    def keep(ln: dict, page_no: int) -> bool:
        k = key(ln["text"])
        if ln["edge"] and PDF_PAGE_NO.match(ln["text"]):
            return False
        if k not in running or not ln["edge"]:
            return True
        if page_no == 0 and ln["size"] in level_of and k not in kept_title:
            kept_title.add(k)
            return True
        return False

    # Blocks: ("h", level, text) | ("li", marker, text) | ("p", None, text)
    blocks: list[list] = []
    for page_no, boxes in enumerate(pages):
        for box in boxes:
            box = [ln for ln in box if keep(ln, page_no)]
            if not box:
                continue
            text = " ".join(ln["text"] for ln in box)
            sizes = {ln["size"] for ln in box}
            size = next(iter(sizes))
            letters = len(re.findall(r"[^\W\d_]", text))
            if letters < 3:
                continue  # a decorative initial, a single big letter in an illustration
            if len(sizes) == 1 and size in level_of and len(text) < 200 and not box[0]["bullet"]:
                blocks.append(["h", level_of[size], text])
                continue
            if (all(ln["bold"] for ln in box) and len(box) <= 2 and len(text) < 120
                    and not box[0]["bullet"] and not text.endswith((".", ",", ";"))):
                blocks.append(["h", bold_level, text.rstrip(":")])
                continue
            current = None
            for ln in box:
                m = None if ln["bullet"] else PDF_BULLET.match(ln["text"])
                if ln["bullet"] or m:
                    marker = "1." if m and m.group(2) else "-"
                    current = ["li", marker, ln["text"][m.end():] if m else ln["text"]]
                    blocks.append(current)
                elif current is not None:
                    current[2] = _join(current[2], ln["text"])
                else:
                    current = ["p", None, ln["text"]]
                    blocks.append(current)

    # A paragraph or item that stops mid-sentence continues in the next box when that
    # box starts in lower case (layouts with hanging indents split them).
    merged: list[list] = []
    for b in blocks:
        prev = merged[-1] if merged else None
        if (prev and b[0] == "p" and prev[0] in ("p", "li") and not prev[2].endswith(SENTENCE_END)
                and b[2][:1].islower()):
            prev[2] = _join(prev[2], b[2])
        else:
            merged.append(b)

    md = ""
    for i, (kind, extra, text) in enumerate(merged):
        if lang in ("sk", "cs"):
            text = _fix_split_letters(text)
        if kind == "h":
            chunk = "#" * extra + " " + text
        elif kind == "li":
            chunk = f"{extra} {text}"
        else:
            chunk = text
        tight = kind == "li" and i > 0 and merged[i - 1][0] == "li"
        md += ("\n" if tight else "\n\n") + chunk
    info = {
        "body_size_pt": body,
        "body_font": fonts.most_common(1)[0][0] if fonts else "",
        "heading_levels": {str(k): v for k, v in sorted(level_of.items(), reverse=True)},
        "running_lines_removed": sorted(running),
        "unmapped_glyphs": md.count("(cid:"),
    }
    return md.strip() + "\n", info


# Metadata titles that are job names rather than titles: file names, layout versions.
JUNK_TITLE = re.compile(r"_|\.(indd|docx?|pdf|qxp|qxd|odt|rtf)\b|layout|untitled|bez n[aá]zvu|microsoft word|^\s*\d", re.I)


def extract_pdf(source: str, work: Path, lang: str | None) -> dict:
    need(["pdfminer"], "PDF sources")
    src = Path(source)
    shutil.copy(src, work / "source.pdf")
    meta = _pdf_meta(src)
    pages = _pdf_lines(src)
    chars = sum(ln["n"] for boxes in pages for box in boxes for ln in box)
    if chars < MIN_CHARS_PER_PAGE * max(1, len(pages)):
        print(
            f"The PDF has almost no text layer ({chars} characters on {len(pages)} pages): it is a scan or "
            "an image. Run text recognition first (Adobe Acrobat: Scan & OCR, then save), or ask for the Word "
            "file or the web page, and extract again.",
            file=sys.stderr,
        )
        sys.exit(2)
    text_lang = base_lang(lang or meta["lang"] or "sk")
    md, info = pdf_to_markdown(pages, text_lang)
    write_text(work / "source.md", tidy_markdown(md))
    h1 = re.search(r"^#\s+(.+)$", md, re.M)
    meta_title = meta["title"] if meta["title"] and not JUNK_TITLE.search(meta["title"]) else ""
    title = meta_title or (h1.group(1).strip() if h1 else src.stem)
    pdf = {"pages": len(pages), "tagged": meta["tagged"], "doc_lang": meta["lang"], "producer": meta["producer"], **info}
    return {
        "type": "pdf",
        "source": str(src),
        "title": title,
        "lang": text_lang,
        "pdf": pdf,
        "input": {"kind": "pdf", "file": src.name, "size": src.stat().st_size, "title": title, "when": now(),
                  "pages": len(pages), "tagged": meta["tagged"], "doc_lang": meta["lang"]},
    }


# ---------------------------------------------------------------- text
def extract_text(source: str, work: Path, lang: str | None) -> dict:
    src = Path(source)
    md = read_text(src)
    write_text(work / "source.md", tidy_markdown(md))
    h1 = re.search(r"^#\s+(.+)$", md, re.M)
    title = h1.group(1).strip() if h1 else src.stem
    return {"type": "text", "source": str(src), "title": title, "lang": base_lang(lang or "sk"),
            "input": {"kind": "text", "file": src.name, "size": src.stat().st_size, "title": title, "when": now()}}


# ---------------------------------------------------------------- the report's input block
MONTHS = {
    "sk": "januára februára marca apríla mája júna júla augusta septembra októbra novembra decembra",
    "cs": "ledna února března dubna května června července srpna září října listopadu prosince",
    "en": "January February March April May June July August September October November December",
}
LABELS = {
    "sk": {
        "head": "Vstup", "type": "Typ vstupu", "url": "Adresa (URL)", "file": "Súbor", "title": "Názov",
        "fetched": "Stiahnuté", "received": "Spracované", "part": "Použitá časť", "orig": "Pôvodná adresa podľa stránky",
        "pdf": "PDF", "at": "o", "yes": "áno", "no": "nie", "none": "neuvedený",
        "kinds": {"url": "webová stránka", "html": "uložená webová stránka (HTML)", "docx": "dokument Word (DOCX)",
                  "pdf": "dokument PDF", "text": "text (Markdown alebo obyčajný text)"},
        "parts": {"url": "hlavný obsah stránky ({part}); navigácia, päta a stránky, na ktoré stránka odkazuje, do vstupu nepatria",
                  "docx": "celý text dokumentu; hlavička a päta dokumentu do vstupu nepatria",
                  "pdf": "text všetkých strán; opakované hlavičky, päty a čísla strán sú vynechané, obrázky tiež. "
                         "Nadpisy a zoznamy sú odhadnuté z veľkosti a hrúbky písma",
                  "text": "celý text"},
        "pdfinfo": "{pages} strán; tagované PDF: {tagged}; jazyk dokumentu: {lang}",
    },
    "cs": {
        "head": "Vstup", "type": "Typ vstupu", "url": "Adresa (URL)", "file": "Soubor", "title": "Název",
        "fetched": "Staženo", "received": "Zpracováno", "part": "Použitá část", "orig": "Původní adresa podle stránky",
        "pdf": "PDF", "at": "v", "yes": "ano", "no": "ne", "none": "neuveden",
        "kinds": {"url": "webová stránka", "html": "uložená webová stránka (HTML)", "docx": "dokument Word (DOCX)",
                  "pdf": "dokument PDF", "text": "text (Markdown nebo prostý text)"},
        "parts": {"url": "hlavní obsah stránky ({part}); navigace, patička a stránky, na které stránka odkazuje, do vstupu nepatří",
                  "docx": "celý text dokumentu; záhlaví a zápatí dokumentu do vstupu nepatří",
                  "pdf": "text všech stran; opakovaná záhlaví, zápatí a čísla stran jsou vynechána, obrázky také. "
                         "Nadpisy a seznamy jsou odhadnuty z velikosti a tloušťky písma",
                  "text": "celý text"},
        "pdfinfo": "{pages} stran; tagované PDF: {tagged}; jazyk dokumentu: {lang}",
    },
    "en": {
        "head": "Input", "type": "Type of input", "url": "Address (URL)", "file": "File", "title": "Title",
        "fetched": "Fetched", "received": "Processed", "part": "Part used", "orig": "Original address stated by the page",
        "pdf": "PDF", "at": "at", "yes": "yes", "no": "no", "none": "not set",
        "kinds": {"url": "web page", "html": "saved web page (HTML)", "docx": "Word document (DOCX)",
                  "pdf": "PDF document", "text": "text (Markdown or plain text)"},
        "parts": {"url": "the page's main content ({part}); navigation, footer and linked pages are not part of the input",
                  "docx": "the whole text of the document; its header and footer are not part of the input",
                  "pdf": "the text of every page; running headers, footers, page numbers and images left out. "
                         "Headings and lists are inferred from type size and weight",
                  "text": "the whole text"},
        "pdfinfo": "{pages} pages; tagged PDF: {tagged}; document language: {lang}",
    },
}


def human_date(iso: str, lang: str) -> str:
    d = dt.datetime.fromisoformat(iso)
    months = MONTHS.get(lang, MONTHS["en"]).split()
    lab = LABELS.get(lang, LABELS["en"])
    if lang in ("sk", "cs"):
        return f"{d.day}. {months[d.month - 1]} {d.year} {lab['at']} {d:%H:%M}"
    return f"{d.day} {months[d.month - 1]} {d.year} {lab['at']} {d:%H:%M}"


def human_size(n: int) -> str:
    return f"{n / 1024:.0f} kB" if n < 1024 * 1024 else f"{n / 1024 / 1024:.1f} MB".replace(".", ",")


def input_block(struct: dict) -> str:
    """The report's input block: every fact written out, the URL as visible text."""
    lang = struct.get("lang", "sk")
    lab = LABELS.get(lang, LABELS["en"])
    inp = struct["input"]
    kind = inp["kind"]
    rows = [(lab["type"], lab["kinds"][kind])]
    if inp.get("url"):
        rows.append((lab["url"], f"<{inp['url']}>"))
    if inp.get("file"):
        rows.append((lab["file"], f"`{inp['file']}` ({human_size(inp['size'])})"))
    if inp.get("original_url"):
        rows.append((lab["orig"], f"<{inp['original_url']}>"))
    if inp.get("title"):
        rows.append((lab["title"], inp["title"]))
    rows.append((lab["fetched"] if kind == "url" else lab["received"], human_date(inp["when"], lang)))
    if kind == "pdf":
        rows.append((lab["pdf"], lab["pdfinfo"].format(pages=inp["pages"], tagged=lab["yes"] if inp["tagged"] else lab["no"],
                                                       lang=inp["doc_lang"] or lab["none"])))
    part_key = "url" if kind in ("url", "html") else kind
    rows.append((lab["part"], lab["parts"][part_key].format(part=f"`{inp.get('part', '')}`")))
    return f"**{lab['head']}**\n\n" + "\n".join(f"- **{k}:** {v}" for k, v in rows) + "\n"


# ---------------------------------------------------------------- summary
def summary(struct: dict, work: Path) -> None:
    md = read_text(work / "source.md")
    words = len(re.findall(r"[\wÀ-ſ]+", md))
    heads = re.findall(r"^#{1,4}\s+.+$", md, re.M)
    print(f"source type : {struct['type']}")
    print(f"title       : {struct.get('title')}")
    print(f"language    : {struct.get('lang')}" + (f" (page says {struct['page_lang']!r})" if struct.get("page_lang") else ""))
    print(f"source.md   : {words} words, {len(heads)} headings")
    for h in heads[:20]:
        print("    " + h)
    if len(heads) > 20:
        print(f"    ... {len(heads) - 20} more")
    if struct["type"] == "web":
        print(f"main content: {struct['main_selector']}")
        print("class map (the page's markup, reused by build.py for the HTML fragment):")
        for tag, cls in struct["class_map"].items():
            print(f"    <{tag}{' class=' + json.dumps(cls) if cls else ''}>")
    if struct["type"] == "docx":
        print(f"source styles: {struct['source_styles']}")
    if struct["type"] == "pdf":
        p = struct["pdf"]
        print(f"pdf         : {p['pages']} pages, tagged {p['tagged']}, language {p['doc_lang'] or '-'}, "
              f"body text {p['body_font']} {p['body_size_pt']} pt, heading levels by size {p['heading_levels']}")
        if p["running_lines_removed"]:
            print(f"removed     : running headers/footers {p['running_lines_removed'][:5]}")
        if p["unmapped_glyphs"]:
            print(f"WARNING     : {p['unmapped_glyphs']} unreadable glyphs '(cid:..)': the PDF's fonts lack a "
                  "character map; ask for the Word file")
        print("NOTE        : headings and lists in source.md are guessed from type size and weight; "
              "check them against the PDF before relying on the structure")
    # abspath, not resolve(): resolve() turns a mapped drive into its target path.
    print(f"\nwork folder : {os.path.abspath(work)}")
    print("input block : work/input.md goes into section 1 of the companion report")
    print("next        : read source.md; write the easy text as easy.md (one sentence per line);"
          " run check.py; write report.md; run build.py")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="URL, .html, .docx, .pdf, .md or .txt")
    ap.add_argument("--work", default="work", help="work folder (default ./work)")
    ap.add_argument("--selector", help="CSS selector of the main content, when the guess is wrong")
    ap.add_argument("--lang", help="language of the text (sk, cs, en, ...); guessed when omitted")
    a = ap.parse_args()
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    src = a.source
    low = src.lower()
    if re.match(r"https?://", src, re.I) or low.endswith((".html", ".htm")):
        struct = extract_web(src, work, a.selector, a.lang)
    elif low.endswith(".docx"):
        struct = extract_docx(src, work, a.lang)
    elif low.endswith(".pdf"):
        struct = extract_pdf(src, work, a.lang)
    elif low.endswith((".md", ".txt", ".markdown")):
        struct = extract_text(src, work, a.lang)
    elif low.endswith(".doc"):
        print("Legacy .doc: open it in Word and save as .docx first.", file=sys.stderr)
        sys.exit(2)
    else:
        print("unknown source type; give a URL, .html, .docx, .pdf, .md or .txt", file=sys.stderr)
        sys.exit(2)
    write_text(work / "structure.json", json.dumps(struct, ensure_ascii=False, indent=2) + "\n")
    write_text(work / "input.md", input_block(struct))
    summary(struct, work)


if __name__ == "__main__":
    main()
