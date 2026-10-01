#!/usr/bin/env python3
"""Check an easy-to-read Markdown text against the rules that a script can test.

    python check.py EASY.md [--lang sk|cs|en] [--json OUT.json] [--max-words N] [--max-sentences N]

Prints a Markdown report: statistics, open placeholders, findings with line numbers,
and the rules that passed. It never edits the text. The judgement rules (adult tone,
hard words explained, positive phrasing, order of information, pictures) stay with the
writer and the reader check; this script only catches what a regex can see.

Text conventions it expects: one sentence per line, a blank line between paragraphs,
`#` headings, `-` lists, `[text](url)` links, placeholders like [DOPLNIŤ: telefón].
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from etr_common import base_lang, read_text, write_text  # noqa: E402

LIMITS = {"sk": (15, 5), "cs": (15, 5), "en": (20, 5)}  # words per sentence, sentences per paragraph

ABBREV = {
    "sk": r"\b(?:napr|t\. ?j|tzv|resp|č|ods|písm|Z\. ?z|s\. ?r\. ?o|a\. ?s|atď|tel|str|zák|ust|príp|max|min|cca|mil|tis)\.",
    "cs": r"\b(?:např|tj|tzv|resp|č|odst|písm|Sb|s\. ?r\. ?o|a\. ?s|atd|tel|str|zák|příp|max|min|cca|mil|tis)\.",
    "en": r"\b(?:e\.g|i\.e|etc|vs|approx|no|incl|excl|dept|govt)\.",
}
ROMAN = {
    "sk": r"\b(?:I{1,3}|IV|VI{0,3}|IX|X{1,2})\.(?=\s)",
    "cs": r"\b(?:I{1,3}|IV|VI{0,3}|IX|X{1,2})\.(?=\s)",
    "en": r"\b(?:II|III|IV|VI|VII|VIII|IX|XI|XII)\b",
}
GLOSSARY_HEAD = re.compile(r"ťažk[eé] slov|slovn[ií][kč]|těžk[aá] slov|hard words|difficult words|glossary|word list", re.I)
PLACEHOLDER = re.compile(r"\[(?:DOPLNIŤ|DOPLNIT|DOPLŇTE|DOPLŇ|ADD|TODO|FILL IN|OVERIŤ|OVĚŘIT|CHECK)[^\]]*\]", re.I)
WORD = re.compile(r"[\wÀ-ſ]+(?:-[\wÀ-ſ]+)*")
# Explicit upper-case letters: a range like Á-Ž would also match accented lower-case letters.
UPPER = "A-ZÁÄČĎÉĚÍĹĽŇÓÔŔŘŠŤÚŮÝŽ"
SENT_SPLIT = re.compile(rf"(?<=[.!?])\s+(?=[\"„“(]?[{UPPER}0-9])")
CAPS = re.compile(rf"\b(?:[{UPPER}]{{2,6}}|[a-z][{UPPER}]{{2,5}})\b")
HTML_TAG = re.compile(r"<[^>]+>")
PASSIVE = {
    "sk": r"\b(?:je|sú|bol|bola|bolo|boli|bude|budú|byť|som|ste)\s+(?:\w+\s+)?\w+(?:ný|ná|né|ní|tý|tá|té|tí|ený|ená|ené|ení)\b",
    "cs": r"\b(?:je|jsou|byl|byla|bylo|byli|bude|budou|být|jsem|jste)\s+(?:\w+\s+)?\w+(?:ný|ná|né|ní|tý|tá|té|tí|ený|ená|ené|ení)\b",
    "en": r"\b(?:is|are|was|were|be|been|being|get|got)\s+(?:\w+ly\s+)?\w+(?:ed|en)\b",
}


def strip_inline(line: str) -> tuple[str, list[str]]:
    """Remove Markdown inline markup; return plain text and the link URLs found."""
    urls = re.findall(r"\]\(([^)]+)\)", line) + re.findall(r'href="([^"]+)"', line)
    line = re.sub(r"\[([^\]]*)\]\([^)]+\)", r"\1", line)
    line = HTML_TAG.sub("", line)
    line = re.sub(r"\*\*|__", "", line)
    line = re.sub(r"(?<!\w)[*_](\S[^*_]*?)[*_](?!\w)", r"\1", line)
    line = line.replace("\\", "")
    return line.strip(), urls


def analyse(md: str, lang: str, max_words: int, max_sent: int) -> dict:
    lines = md.split("\n")
    # Skip a YAML front matter block without losing the line numbering.
    skip_until = 0
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                skip_until = j + 1
                break
    findings, open_items = [], []
    stats = {"sentences": 0, "words": 0, "longest": 0, "longest_line": 0, "paragraphs": 0,
             "headings": 0, "list_items": 0, "links": 0}
    in_code = False
    para_sentences = 0
    para_start = 0
    has_glossary = False
    text_lines = []  # (lineno, plain text, kind)

    def close_para(upto: int):
        nonlocal para_sentences, para_start
        if para_sentences:
            stats["paragraphs"] += 1
            if para_sentences > max_sent:
                findings.append((para_start, "long paragraph", "warn",
                                 f"{para_sentences} sentences (limit {max_sent}); split by topic"))
        para_sentences = 0

    for i, raw in enumerate(lines, 1):
        if i <= skip_until:
            continue
        if raw.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        s = raw.rstrip()
        if not s.strip():
            close_para(i)
            continue
        if s.lstrip().startswith("#"):
            close_para(i)
            stats["headings"] += 1
            head = s.lstrip("# ").strip()
            if GLOSSARY_HEAD.search(head):
                has_glossary = True
            text_lines.append((i, strip_inline(head)[0], "heading"))
            continue
        for m in PLACEHOLDER.finditer(s):
            open_items.append((i, m.group(0)))
        s_clean = PLACEHOLDER.sub("", s)
        is_item = bool(re.match(r"\s*(?:[-*+]|\d+[.)])\s+", s_clean))
        body = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", s_clean) if is_item else s_clean
        if s_clean.startswith("|") or s_clean.startswith("<"):
            text_lines.append((i, s_clean, "other"))
            continue
        plain, urls = strip_inline(body)
        stats["links"] += len(urls)
        if not plain:
            continue
        if is_item:
            stats["list_items"] += 1
            if para_sentences == 0:
                para_start = i
        else:
            if para_sentences == 0:
                para_start = i
        sentences = [x for x in SENT_SPLIT.split(plain) if x.strip()]
        if len(sentences) > 1:
            findings.append((i, "two sentences on one line", "warn",
                             "start every sentence on a new line"))
        for sent in sentences:
            words = WORD.findall(sent)
            n = len(words)
            stats["sentences"] += 1
            stats["words"] += n
            if n > stats["longest"]:
                stats["longest"], stats["longest_line"] = n, i
            if n > max_words:
                findings.append((i, "long sentence", "warn", f"{n} words (limit {max_words}): {sent[:90]}"))
        para_sentences += len(sentences)
        text_lines.append((i, plain, "item" if is_item else "para"))
    close_para(len(lines))

    # Character-level rules over the plain text lines (headings included).
    abbrev = re.compile(ABBREV.get(lang, ABBREV["en"]), re.I)
    roman = re.compile(ROMAN.get(lang, ROMAN["en"]))
    passive = re.compile(PASSIVE.get(lang, PASSIVE["en"]), re.I)
    seen_caps = set()
    for i, plain, kind in text_lines:
        if kind == "other":
            continue
        if "%" in plain:
            findings.append((i, "percentage", "warn", "say 'few', 'many', 'most', or give the amount in euros"))
        for m in re.finditer(r"\b\d{1,3}(?:[ . ]\d{3})+\b|\b\d{5,}\b", plain):
            if not re.match(r"\d{4}$", m.group(0)):
                findings.append((i, "big number", "warn", f"{m.group(0)}: round it or say what it means"))
        for m in roman.finditer(plain):
            findings.append((i, "Roman numeral", "warn", f"{m.group(0).strip()} -> write the word (druhý, second)"))
        for m in abbrev.finditer(plain):
            findings.append((i, "abbreviation", "warn", f"{m.group(0)}: write the words out"))
        for m in CAPS.finditer(plain):
            tok = m.group(0)
            if re.fullmatch(r"[IVX]+", tok) or tok in seen_caps:
                continue
            seen_caps.add(tok)
            findings.append((i, "initials or capitals", "warn", f"{tok}: write the words out, or explain it where it first occurs"))
        for ch in re.findall(r"[§&#/;—–]|\(|\)|\[|\]", plain):
            findings.append((i, "special character", "warn", f"'{ch}': rewrite without it (no brackets, slashes, dashes, semicolons, §)"))
            break
        if lang == "en":
            for m in re.finditer(r"\b\d+(?:st|nd|rd|th)\b", plain):
                findings.append((i, "ordinal number", "warn", f"{m.group(0)}: write 'Tuesday 13 October', not '13th'"))
        if re.search(r"https?://|www\.", plain):
            findings.append((i, "visible web address", "warn", "hide the address behind words that say where the link goes"))
        if re.search(r"\[\^|\^\d", plain):
            findings.append((i, "footnote", "warn", "no footnotes; put the information in the text"))
        for m in WORD.finditer(plain):
            if len(m.group(0)) >= 14 and kind != "heading":
                findings.append((i, "long word", "info", f"{m.group(0)}: replace with a short word, or explain it"))
        if kind != "heading" and passive.search(plain):
            findings.append((i, "possible passive", "info", "say who does it: 'Úrad vám pošle list'"))

    stats["average"] = round(stats["words"] / stats["sentences"], 1) if stats["sentences"] else 0
    stats["glossary"] = has_glossary
    stats["placeholders"] = len(open_items)
    rules = ["long sentence", "long paragraph", "two sentences on one line", "percentage", "big number",
             "Roman numeral", "abbreviation", "initials or capitals", "special character", "visible web address",
             "footnote"]
    if lang == "en":
        rules.append("ordinal number")
    hit = {f[1] for f in findings}
    passed = [r for r in rules if r not in hit]
    findings.sort(key=lambda f: (f[0], f[1]))
    return {"lang": lang, "stats": stats, "open_items": open_items, "findings": findings, "passed": passed}


def add_dictionary_findings(md: str, lang: str, r: dict, easy: str = "", work: str | None = None,
                            scope: list[str] | None = None) -> None:
    """Findings for words that a dictionary (user, public, global) explains, once per term at
    its first occurrence. A match is lexical, so every hit needs a verdict for this text
    (dictionary.py decide): a hit without one is a warning, a decided hit is info."""
    try:
        from dictionary import decisions_path, find_in_text, job_scopes, load_decisions, load_tiers, verdict_for
    except ImportError:
        return
    try:
        tiers = load_tiers(lang)
    except Exception:  # noqa: BLE001
        return
    if not tiers:
        return
    hits = find_in_text(md, tiers, job_scopes(md, scope))
    if not hits:
        return
    decisions = load_decisions(decisions_path(easy or "easy.md", work), easy or None)["decisions"]
    undecided = 0
    for h in hits:
        best = h["tiers"][0]
        v = verdict_for(h, decisions)
        where = f"the {best['tier']} dictionary ({best['entry'].get('status', 'draft')})"
        if v:
            r["findings"].append((h["lines"][0], "dictionary", "info",
                                  f"'{h['term']}' in {where}: verdict {v['verdict']}"))
        else:
            undecided += 1
            r["findings"].append((h["lines"][0], "dictionary", "warn",
                                  f"'{h['term']}' matched '{h['occurrences'][0]['form']}' ({where}) and has no verdict: "
                                  "read it in its sentence, then dictionary.py decide TERM used|rewritten|wrong-match|other-sense"))
    r["findings"].sort(key=lambda f: (f[0], f[1]))
    r["stats"]["dictionary_terms"] = len(hits)
    r["stats"]["dictionary_without_verdict"] = undecided
    if not undecided:
        r["passed"].append("every dictionary hit has a verdict")


def render(path: str, r: dict) -> str:
    s = r["stats"]
    out = [f"# Easy-to-read check: {Path(path).name} ({r['lang']})", ""]
    out.append(f"Sentences {s['sentences']} · words {s['words']} · average {s['average']} words per sentence · "
               f"longest {s['longest']} words (line {s['longest_line']}) · paragraphs {s['paragraphs']} · "
               f"headings {s['headings']} · list items {s['list_items']} · links {s['links']} · "
               f"glossary {'yes' if s['glossary'] else 'no'}")
    out.append("")
    out.append(f"## Open items to fill in ({len(r['open_items'])})")
    out.append("")
    for ln, txt in r["open_items"] or []:
        out.append(f"- line {ln}: {txt}")
    if not r["open_items"]:
        out.append("- none")
    out.append("")
    warns = [f for f in r["findings"] if f[2] == "warn"]
    infos = [f for f in r["findings"] if f[2] == "info"]
    out.append(f"## Findings ({len(warns)} to fix, {len(infos)} to consider)")
    out.append("")
    for ln, rule, sev, msg in warns:
        out.append(f"- line {ln} · {rule}: {msg}")
    for ln, rule, sev, msg in infos:
        out.append(f"- line {ln} · ({rule}) {msg}")
    if not r["findings"]:
        out.append("- none")
    out.append("")
    out.append("## Passed")
    out.append("")
    out.append("- " + ", ".join(r["passed"]) if r["passed"] else "- nothing yet")
    out.append("")
    out.append("Not checked by this script (check by reading): adult tone, hard words explained where they occur, "
               "positive and active phrasing, the order of information, what the reader must do, pictures.")
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("easy", help="the easy-to-read Markdown file")
    ap.add_argument("--lang", help="sk, cs or en (default: from work/structure.json next to the file, else sk)")
    ap.add_argument("--json", help="also write the result as JSON to this path")
    ap.add_argument("--max-words", type=int, help="words per sentence (default sk/cs 15, en 20)")
    ap.add_argument("--max-sentences", type=int, help="sentences per paragraph (default 5)")
    ap.add_argument("--no-dictionary", action="store_true", help="do not look the text up in the dictionaries")
    ap.add_argument("--work", help="work folder with dictionary-decisions.json (default: work next to the text)")
    ap.add_argument("--scope", action="append", help="body or topic of the text, besides the source address")
    a = ap.parse_args()
    lang = a.lang
    if not lang:
        for cand in (Path(a.easy).parent / "work" / "structure.json", Path(a.easy).parent / "structure.json"):
            if cand.exists():
                lang = json.loads(read_text(cand)).get("lang")
                break
    lang = base_lang(lang)
    mw, ms = LIMITS.get(lang, LIMITS["en"])
    md = read_text(a.easy)
    r = analyse(md, lang, a.max_words or mw, a.max_sentences or ms)
    if not a.no_dictionary:
        add_dictionary_findings(md, lang, r, a.easy, a.work, a.scope)
    print(render(a.easy, r))
    if a.json:
        write_text(a.json, json.dumps({
            "lang": lang, "stats": r["stats"],
            "open_items": [{"line": ln, "text": t} for ln, t in r["open_items"]],
            "findings": [{"line": ln, "rule": ru, "severity": sv, "message": m} for ln, ru, sv, m in r["findings"]],
            "passed": r["passed"],
        }, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
