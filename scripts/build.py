#!/usr/bin/env python3
"""Build the customer package from the easy text and the companion report.

    python build.py --easy easy.md --report report.md [--work work] [--out out]
                    [--format docx|html|pdf|md|all] [--reference source.docx]
                    [--lang sk] [--title "..."] [--no-nbsp]

What comes out depends on where the source came from (work/structure.json):
  Word file  -> easy.docx styled like the customer's document, plus easy.md
  web page   -> easy.fragment.html reusing the page's tags and classes,
                easy.preview.html to open in a browser, plus easy.md
  PDF        -> easy.pdf (tagged, PDF/UA-1, typeset by typst) and easy.docx to edit,
                plus easy.md
  text       -> easy.md and easy.docx (pandoc's default styles)
  --format all makes every one of them. The report always comes out as
  report.md and report.docx (same reference document, no easy-to-read overrides).

The Word output keeps the customer's styles, header, footer and page setup (pandoc's
--reference-doc) and then enforces what the standards require: body text at least
14 pt, a sans-serif face where the document used a serif one, left alignment, no
first-line indent, no automatic hyphenation, bold headings without italics. The
overrides are printed so the report can list them.

The PDF is A4, sans-serif 14 pt, left aligned, no hyphenation, one sentence per
line, pages numbered "strana 2 z 4" from page two, with the document title and
language set and a structure tree (PDF/UA-1, enforced by typst).

The report must state the input: build.py stops when the report does not show the
source URL written out (not only as link text) or the source file name. extract.py
writes the ready block to work/input.md.

Slovak and Czech outputs get a non-breaking space after one-letter words. The
canonical easy.md is copied untouched.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from etr_common import (  # noqa: E402
    WORD_LANG, base_lang, ensure_pandoc, ensure_typst, nbsp, read_text, run, simple_lang, write_text,
)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS = {"w": W, "a": A}
SERIF = {
    "times new roman", "times", "georgia", "cambria", "cambria math", "garamond", "eb garamond",
    "palatino linotype", "palatino", "book antiqua", "century", "century schoolbook", "constantia",
    "bookman old style", "baskerville", "libre baskerville", "calisto mt", "goudy old style",
    "perpetua", "sylfaen", "aptos serif", "lora", "merriweather", "minion pro", "adobe garamond pro",
    "liberation serif", "dejavu serif", "noto serif", "source serif pro", "pt serif",
}
SANS = "Arial"
BODY_STYLES = {"Normal", "BodyText", "FirstParagraph", "Compact", "ListParagraph", "BodyTextIndent",
               "NormalWeb", "Standard", "TextBody", "Textbody"}
HEADING_STYLES = re.compile(r"^(Heading\d|Title|Subtitle|berschrift\d|Nadpis\d|Nzov)$", re.I)
MIN_BODY_HALF_PT = 28   # 14 pt
MIN_HEADING_HALF_PT = 32  # 16 pt

PREVIEW_CSS = """
:root { color-scheme: light; }
body { margin: 0; padding: 2rem 1rem; background: #fff; color: #111; font-family: Arial, Helvetica, "Liberation Sans", sans-serif; font-size: 1.25rem; line-height: 1.6; }
main { max-width: 36rem; margin: 0 auto; }
h1, h2, h3 { font-weight: bold; line-height: 1.25; margin: 1.6em 0 0.5em; }
h1 { font-size: 2rem; } h2 { font-size: 1.5rem; } h3 { font-size: 1.25rem; }
p { margin: 0 0 1.2em; text-align: left; hyphens: none; -webkit-hyphens: none; }
ul, ol { margin: 0 0 1.2em; padding-left: 1.4em; }
li { margin: 0 0 0.5em; }
a { color: #0b4ea2; text-decoration: underline; text-underline-offset: 0.15em; }
a:focus-visible { outline: 3px solid #0b4ea2; outline-offset: 2px; }
img { max-width: 100%; height: auto; display: block; margin: 0 0 1em; }
.etr-note { font-size: 1rem; color: #444; border-top: 1px solid #ccc; margin-top: 3rem; padding-top: 1rem; }
"""


def pandoc_md_args(extra: list[str]) -> list[str]:
    # hard_line_breaks: every line inside a paragraph is a line break, which is how the
    # easy text is written (one sentence per line). -smart keeps quotes and dashes as typed.
    return ["-f", "markdown+hard_line_breaks-smart", "--wrap=none", *extra]


# ---------------------------------------------------------------- docx overrides
def _get(el, path):
    return el.find(path, NS)


def _ensure(el, tag):
    from lxml import etree
    child = el.find(f"w:{tag}", NS)
    if child is None:
        child = etree.SubElement(el, f"{{{W}}}{tag}")
    return child


def _font_name(rpr, theme_fonts: dict) -> str | None:
    if rpr is None:
        return None
    rf = _get(rpr, "w:rFonts")
    if rf is None:
        return None
    ascii_ = rf.get(f"{{{W}}}ascii")
    if ascii_:
        return ascii_
    th = rf.get(f"{{{W}}}asciiTheme")
    if th:
        return theme_fonts.get("minor" if "minor" in th else "major")
    return None


def _set_sans(rpr, changes: list[str], where: str) -> None:
    rf = _ensure(rpr, "rFonts")
    for attr in list(rf.attrib):
        if attr.endswith("Theme"):
            del rf.attrib[attr]
    for k in ("ascii", "hAnsi", "cs", "eastAsia"):
        rf.set(f"{{{W}}}{k}", SANS)
    changes.append(f"{where}: serif face replaced by {SANS}")


def _min_size(rpr, minimum: int, changes: list[str], where: str, force: bool) -> None:
    sz = _get(rpr, "w:sz")
    cur = int(sz.get(f"{{{W}}}val")) if sz is not None and sz.get(f"{{{W}}}val", "").isdigit() else None
    if cur is None and not force:
        return
    if cur is None or cur < minimum:
        _ensure(rpr, "sz").set(f"{{{W}}}val", str(minimum))
        _ensure(rpr, "szCs").set(f"{{{W}}}val", str(minimum))
        changes.append(f"{where}: size {cur / 2 if cur else '?'} pt -> {minimum / 2:g} pt")


def _drop_italics(rpr, changes: list[str], sid: str) -> None:
    dropped = False
    for tag in ("i", "iCs"):
        el = _get(rpr, f"w:{tag}")
        if el is not None:
            rpr.remove(el)
            dropped = True
    if dropped:
        changes.append(f"style {sid}: italics removed")


def apply_etr_styles(docx_path: Path, lang: str) -> list[str]:
    """Enforce the layout rules on the styles of a finished .docx. Returns the changes made."""
    from lxml import etree

    changes: list[str] = []
    with zipfile.ZipFile(docx_path) as z:
        names = z.namelist()
        styles = etree.fromstring(z.read("word/styles.xml"))
        settings = etree.fromstring(z.read("word/settings.xml")) if "word/settings.xml" in names else None
        theme = etree.fromstring(z.read("word/theme/theme1.xml")) if "word/theme/theme1.xml" in names else None
        others = {n: z.read(n) for n in names if n not in ("word/styles.xml", "word/settings.xml")}

    theme_fonts = {}
    if theme is not None:
        for which in ("minor", "major"):
            latin = theme.find(f".//a:{which}Font/a:latin", NS)
            if latin is not None:
                theme_fonts[which] = latin.get("typeface")

    # 1. document defaults
    rpr_default = styles.find("w:docDefaults/w:rPrDefault/w:rPr", NS)
    if rpr_default is None:
        dd = _ensure(styles, "docDefaults")
        rpr_default = _ensure(_ensure(dd, "rPrDefault"), "rPr")
    font = _font_name(rpr_default, theme_fonts)
    if font and font.lower() in SERIF:
        _set_sans(rpr_default, changes, f"document default font ({font})")
    _min_size(rpr_default, MIN_BODY_HALF_PT, changes, "document default", force=True)
    lang_el = _ensure(rpr_default, "lang")
    lang_el.set(f"{{{W}}}val", WORD_LANG.get(base_lang(lang), base_lang(lang)))

    # 2. paragraph styles
    for st in styles.findall("w:style", NS):
        sid = st.get(f"{{{W}}}styleId", "")
        stype = st.get(f"{{{W}}}type", "")
        if stype != "paragraph":
            continue
        rpr = _get(st, "w:rPr")
        ppr = _get(st, "w:pPr")
        is_body = sid in BODY_STYLES
        is_head = bool(HEADING_STYLES.match(sid))
        if not (is_body or is_head):
            continue
        if rpr is None:
            rpr = _ensure(st, "rPr")
        if ppr is None:
            ppr = _ensure(st, "pPr")
        font = _font_name(rpr, theme_fonts)
        if font and font.lower() in SERIF:
            _set_sans(rpr, changes, f"style {sid} ({font})")
        if is_body:
            _min_size(rpr, MIN_BODY_HALF_PT, changes, f"style {sid}", force=False)
            jc = _get(ppr, "w:jc")
            if jc is not None and jc.get(f"{{{W}}}val") in ("both", "distribute", "center", "right", "end"):
                ppr.remove(jc)
                changes.append(f"style {sid}: alignment set to left")
            ind = _get(ppr, "w:ind")
            if ind is not None and (ind.get(f"{{{W}}}firstLine") or ind.get(f"{{{W}}}hanging")) and sid != "ListParagraph":
                for k in ("firstLine", "hanging"):
                    ind.attrib.pop(f"{{{W}}}{k}", None)
                if not ind.attrib:
                    ppr.remove(ind)
                changes.append(f"style {sid}: first-line indent removed")
            if sid == "Normal" and _get(ppr, "w:suppressAutoHyphens") is None:
                _ensure(ppr, "suppressAutoHyphens")
            _drop_italics(rpr, changes, sid)
        if is_head:
            _min_size(rpr, MIN_HEADING_HALF_PT, changes, f"style {sid}", force=False)
            if _get(rpr, "w:b") is None:
                _ensure(rpr, "b")
                _ensure(rpr, "bCs")
                changes.append(f"style {sid}: made bold")
            _drop_italics(rpr, changes, sid)
            if _get(rpr, "w:caps") is not None:
                rpr.remove(_get(rpr, "w:caps"))
                changes.append(f"style {sid}: all-capitals removed")
            jc = _get(ppr, "w:jc") if ppr is not None else None
            if jc is not None and jc.get(f"{{{W}}}val") in ("both", "distribute", "right", "end"):
                ppr.remove(jc)
                changes.append(f"style {sid}: alignment set to left")

    # 3. settings: no automatic hyphenation
    if settings is not None:
        ah = _get(settings, "w:autoHyphenation")
        if ah is not None and ah.get(f"{{{W}}}val", "1") not in ("0", "false"):
            ah.set(f"{{{W}}}val", "0")
            changes.append("automatic hyphenation switched off")

    tmp = docx_path.with_suffix(".tmp.docx")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for n, data in others.items():
            z.writestr(n, data)
        z.writestr("word/styles.xml", etree.tostring(styles, xml_declaration=True, encoding="UTF-8", standalone=True))
        if settings is not None:
            z.writestr("word/settings.xml", etree.tostring(settings, xml_declaration=True, encoding="UTF-8", standalone=True))
    shutil.move(str(tmp), str(docx_path))
    return changes


# ---------------------------------------------------------------- html
def add_classes(fragment: str, cmap: dict[str, str], lang: str) -> str:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("beautifulsoup4 not installed: HTML fragment written without the page's classes", file=sys.stderr)
        return f'<div lang="{simple_lang(lang)}">\n{fragment}\n</div>\n'
    soup = BeautifulSoup(fragment, "html.parser")
    for tag, cls in cmap.items():
        if not cls:
            continue
        for el in soup.find_all(tag):
            el["class"] = cls.split()
    wrapper = soup.new_tag("div")
    wrapper["lang"] = simple_lang(lang)
    wrapper["class"] = ["easy-to-read"]
    for el in list(soup.contents):
        wrapper.append(el.extract())
    # No prettify: it would add whitespace around inline elements (a space before a full
    # stop after a link) and turn every accented letter into an entity.
    return str(wrapper).replace(" ", "&nbsp;") + "\n"


GLOSSARY_HEAD = re.compile(r"ťažk[eé] slov|slovn[ií][kč]|těžk[aá] slov|hard words|difficult words|glossary|word list", re.I)


def glossary_dl(fragment: str) -> str:
    """Turn the glossary section (the last `## Ťažké slová` heading) into a definition list:
    pandoc renders `**Term**` + sentences as <p><strong>Term</strong><br />...</p>; a <dl>
    with <dt>/<dd> is the semantics a page and a screen reader can use."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return fragment
    soup = BeautifulSoup(fragment, "html.parser")
    heads = [h for h in soup.find_all(["h2", "h3"]) if GLOSSARY_HEAD.search(h.get_text(" ", strip=True))]
    if not heads:
        return fragment
    head = heads[-1]
    dl = soup.new_tag("dl")
    dl["class"] = ["etr-glossary"]
    moved = 0
    for sib in list(head.find_next_siblings()):
        if sib.name in ("h1", "h2", "h3"):
            break
        if sib.name != "p" or not sib.contents or getattr(sib.contents[0], "name", None) != "strong":
            continue
        strong = sib.contents[0]
        dt = soup.new_tag("dt")
        dt.string = strong.get_text(" ", strip=True)
        dd = soup.new_tag("dd")
        rest = [c for c in list(sib.contents)[1:]]
        # drop the <br> and newline right after the term
        while rest and (getattr(rest[0], "name", None) == "br" or (isinstance(rest[0], str) and not rest[0].strip())):
            rest.pop(0)
        for c in rest:
            dd.append(c.extract())
        dl.append(dt)
        dl.append(dd)
        sib.decompose()
        moved += 1
    if moved:
        head.insert_after(dl)
    return str(soup)


def preview_html(fragment: str, title: str, lang: str, note: str) -> str:
    return (
        f'<!DOCTYPE html>\n<html lang="{simple_lang(lang)}">\n<head>\n<meta charset="utf-8">\n'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{title}</title>\n<style>{PREVIEW_CSS}</style>\n</head>\n<body>\n<main>\n"
        f"{fragment}\n<p class=\"etr-note\">{note}</p>\n</main>\n</body>\n</html>\n"
    )


# ---------------------------------------------------------------- pdf
# Typst preamble: the easy-to-read layout for print. @TITLE@, @LANG@ and @PAGE@ are
# filled in; @PAGE@ is the page label with #n and #total ("strana #n z #total").
TYPST_PREAMBLE = """#set document(title: @TITLE@)
#set text(lang: "@LANG@", font: ("Arial", "Liberation Sans", "Noto Sans", "DejaVu Sans"), size: 14pt,
  hyphenate: false, costs: (widow: 1000%, orphan: 1000%))
#set par(justify: false, leading: 0.75em, spacing: 1.5em, first-line-indent: 0pt)
#set page(paper: "a4", margin: (x: 25mm, top: 25mm, bottom: 30mm),
  footer: context {
    let n = counter(page).get().first()
    let total = counter(page).final().first()
    if n > 1 [#set text(size: 12pt); @PAGE@]
  })
#show heading: set text(weight: "bold", style: "normal")
#show heading.where(level: 1): set text(size: 22pt)
#show heading.where(level: 2): set text(size: 18pt)
#show heading.where(level: 3): set text(size: 16pt)
#show heading: set block(above: 1.8em, below: 0.9em)
#show heading: set par(leading: 0.5em)
#show link: underline
#set list(spacing: 0.9em, indent: 0.4em, body-indent: 0.6em)
#set enum(spacing: 0.9em, indent: 0.4em, body-indent: 0.6em)
#set strong(delta: 300)
#show emph: it => it.body

"""
PAGE_LABEL = {"sk": "strana #n z #total", "cs": "strana #n z #total", "en": "page #n of #total",
              "de": "Seite #n von #total", "pl": "strona #n z #total", "hu": "#n. oldal / #total"}


def typst_string(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_pdf(pandoc: str, md_path: Path, pdf_out: Path, title: str, lang: str) -> str:
    """Typeset the easy text as a tagged PDF/UA-1. Returns a status line for the log."""
    typst = ensure_typst()
    body = run([pandoc, str(md_path), *pandoc_md_args(["-t", "typst"])]).stdout
    preamble = (TYPST_PREAMBLE.replace("@TITLE@", typst_string(title)).replace("@LANG@", lang)
                .replace("@PAGE@", PAGE_LABEL.get(lang, PAGE_LABEL["en"])))
    typ = md_path.with_suffix(".typ")
    write_text(typ, preamble + body)
    base = [typst, "compile", "--root", str(typ.parent)]
    p = subprocess.run([*base, "--pdf-standard", "ua-1", str(typ), str(pdf_out)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode == 0:
        return f"{pdf_out.name}: tagged PDF, PDF/UA-1 conformance checked by typst"
    # Not conformant (e.g. an image without alternative text): still write the PDF,
    # but say so, so the report does not claim PDF/UA.
    run([*base, str(typ), str(pdf_out)])
    reason = " ".join(p.stderr.split())[:400]
    return f"WARNING {pdf_out.name}: tagged PDF, but NOT PDF/UA-1 conformant: {reason}"


# ---------------------------------------------------------------- report input check
def report_input_problems(report: str, struct: dict) -> list[str]:
    """What the report fails to state about the input: the URL written out as visible
    text (not only as a link target) and the source file name."""
    inp = struct.get("input") or {}
    source = struct.get("source", "")
    needed = []
    url = inp.get("url") or (source if re.match(r"https?://", source, re.I) else "")
    if url:
        needed.append(("the source URL, written out", url))
    name = inp.get("file") or ("" if url or not source else Path(source).name)
    if name:
        needed.append(("the source file name", name))
    visible = re.sub(r"\]\([^)]*\)", "]", report)
    return [f"{what}: {value}" for what, value in needed if value not in visible]


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--easy", required=True, help="the easy-to-read text (Markdown, one sentence per line)")
    ap.add_argument("--report", help="the companion report (Markdown)")
    ap.add_argument("--work", default="work", help="work folder with structure.json (default ./work)")
    ap.add_argument("--out", default="out", help="output folder (default ./out)")
    ap.add_argument("--format", action="append", choices=["docx", "html", "pdf", "md", "all"],
                    help="override the outputs chosen from the source type; repeatable")
    ap.add_argument("--reference", help="a .docx whose styles, header and footer the Word output copies")
    ap.add_argument("--lang", help="sk, cs, en ... (default from structure.json)")
    ap.add_argument("--title", help="document title (default from structure.json or the first heading)")
    ap.add_argument("--no-nbsp", action="store_true", help="do not insert non-breaking spaces (sk, cs)")
    a = ap.parse_args()

    work, out = Path(a.work), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    struct = json.loads(read_text(work / "structure.json")) if (work / "structure.json").exists() else {}
    stype = struct.get("type", "text")
    lang = base_lang(a.lang or struct.get("lang"))
    easy_md = read_text(a.easy)
    m = re.search(r"^#\s+(.+)$", easy_md, re.M)
    title = a.title or (m.group(1).strip() if m else struct.get("title") or Path(a.easy).stem)
    reference = Path(a.reference) if a.reference else (work / struct["reference"] if struct.get("reference") else None)
    if reference and not reference.exists():
        print(f"reference document not found: {reference}", file=sys.stderr)
        reference = None

    if a.report and struct:
        problems = report_input_problems(read_text(a.report), struct)
        if problems:
            print("The report does not state what was given as input. Missing:", file=sys.stderr)
            for pr in problems:
                print("  - " + pr, file=sys.stderr)
            block = work / "input.md"
            print(f"Put the input block into section 1 of the report ({block} has it ready):", file=sys.stderr)
            if block.exists():
                print(read_text(block), file=sys.stderr)
            sys.exit(2)

    formats = set(a.format or [])
    if "all" in formats:
        formats = {"docx", "html", "pdf", "md"}
    if not formats:
        by_type = {"docx": {"docx"}, "text": {"docx"}, "pdf": {"pdf", "docx"}, "web": {"html"}}
        formats = set(by_type.get(stype, {"html"}))
    formats.add("md")

    pandoc = ensure_pandoc()
    stem = Path(a.easy).stem
    text_for_output = easy_md if (a.no_nbsp or lang not in ("sk", "cs")) else nbsp(easy_md)
    # In Word the title is the Title paragraph (from metadata); a leading "# Title" would
    # repeat it as Heading 1, so it is dropped from the Word input only.
    docx_input = re.sub(r"\A(?:---\n.*?\n---\n\s*)?#\s+[^\n]+\n+", "", text_for_output, count=1, flags=re.S) \
        if m else text_for_output
    written = []
    with tempfile.TemporaryDirectory() as td:
        tmp_md = Path(td) / "easy.md"
        write_text(tmp_md, text_for_output)

        if "md" in formats:
            shutil.copy(a.easy, out / f"{stem}.md")
            written.append(out / f"{stem}.md")

        if "docx" in formats:
            docx_out = out / f"{stem}.docx"
            tmp_docx_md = Path(td) / "easy-docx.md"
            write_text(tmp_docx_md, docx_input)
            cmd = [pandoc, str(tmp_docx_md), *pandoc_md_args(["-t", "docx", "-o", str(docx_out),
                   f"--metadata=lang:{WORD_LANG.get(lang, lang)}", f"--metadata=title:{title}"])]
            if reference:
                cmd.append(f"--reference-doc={reference}")
            run(cmd)
            changes = apply_etr_styles(docx_out, lang)
            written.append(docx_out)
            print(f"Word overrides applied to {docx_out.name}:" if changes else f"{docx_out.name}: styles already met the rules")
            for c in changes:
                print("  - " + c)

        if "pdf" in formats:
            pdf_out = out / f"{stem}.pdf"
            status = build_pdf(pandoc, tmp_md, pdf_out, title, lang)
            written.append(pdf_out)
            print(status)

        if "html" in formats:
            p = run([pandoc, str(tmp_md), *pandoc_md_args(["-t", "html5"])])
            fragment = add_classes(glossary_dl(p.stdout), struct.get("class_map", {}), lang)
            frag_path = out / f"{stem}.fragment.html"
            write_text(frag_path, fragment)
            written.append(frag_path)
            notes = {
                "sk": "Náhľad ľahko čitateľnej verzie. Text ešte neoverili čitatelia s mentálnym znevýhodnením.",
                "cs": "Náhled verze pro snadné čtení. Text ještě neověřili čtenáři s mentálním postižením.",
                "en": "Preview of the easy-to-read version. Readers with intellectual disabilities have not yet checked this text.",
            }
            prev_path = out / f"{stem}.preview.html"
            write_text(prev_path, preview_html(fragment, title, lang, notes.get(lang, notes["en"])))
            written.append(prev_path)

        if a.report:
            rstem = Path(a.report).stem
            shutil.copy(a.report, out / f"{rstem}.md")
            written.append(out / f"{rstem}.md")
            rdocx = out / f"{rstem}.docx"
            cmd = [pandoc, a.report, "-f", "markdown-smart", "--wrap=none", "-t", "docx", "-o", str(rdocx),
                   f"--metadata=lang:{WORD_LANG.get(lang, lang)}"]
            if reference:
                cmd.append(f"--reference-doc={reference}")
            run(cmd)
            written.append(rdocx)

    print("\nwritten:")
    for w in written:
        print("  " + str(w))
    if stype == "web":
        print("\nThe fragment reuses these classes from the source page: "
              + ", ".join(f"<{t} class=\"{c}\">" for t, c in struct.get("class_map", {}).items() if c))


if __name__ == "__main__":
    main()
