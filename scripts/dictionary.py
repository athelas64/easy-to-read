#!/usr/bin/env python3
"""Dictionaries of hard words for easy-to-read texts: look up, add, export, update.

    python dictionary.py lookup EASY.md [--lang sk] [--json OUT.json] [--scope S] [--work work]
        words in the text that a dictionary already explains, each with the sentence it stands in,
        plus long words without an entry
    python dictionary.py decide TERM VERDICT --text EASY.md [--form F] [--reason "..."] [--work work]
        record whether a dictionary hit fits this text:
        used | rewritten | not-explained | wrong-match | other-sense
    python dictionary.py verdicts --text EASY.md [--work work] [--markdown]
        every hit with its verdict; --markdown gives the table for the companion report
    python dictionary.py exclusions [--proposal] [--issue]
        your personal exclusions; --proposal drafts the note for the shared repository
    python dictionary.py find TERM [--lang sk]          search every tier
    python dictionary.py add TERM --easy "..." [--forms a,b] [--example "..."] [--domain ...]
                            [--scope minv.sk] [--source URL] [--note "..."] [--lang sk]
    python dictionary.py remove TERM [--scope S] [--lang sk]
    python dictionary.py list [--tier user|public|global] [--lang sk]
    python dictionary.py export [--tier ...] [--format glossary|dl|json] [--terms a,b | --from EASY.md]
    python dictionary.py update [--force]               fetch newer public and global files
    python dictionary.py promote TERM [--issue]          propose a user entry to the shared repository
    python dictionary.py status

Context. A match is lexical: it finds the word, not its meaning. Two things keep it honest.
Scope: an entry may name the bodies or topics it is meant for ("scope": ["minv.sk"]); it is
offered only when the text has the same scope, taken from the source address in the text's
front matter (www.minv.sk -> minv.sk), from a "scope:" line there, or from --scope. Entries
without a scope apply everywhere. Exclusions: word forms that look like the term but are a
different word ("práve" is not "práva"); an entry may list them in "exclude", and the user's
file keeps personal ones in "exclusions". Every hit in a text gets a verdict (decide), kept
in work/dictionary-decisions.json; check.py warns about hits without one.

Three tiers, looked up in this order:

  user    your own words, %LOCALAPPDATA%\\easy-to-read\\user-<lang>.json (or $ETR_USER_DICT);
          survives a reinstall of the skill
  public  the shared public-sector dictionary (GitHub, CC BY 4.0), shipped with the skill in
          dictionaries/ and refreshed into the cache by `update`
  global  the Hurraki-derived dictionary (CC BY-SA 3.0), same mechanism

All files share one schema (dictionaries/README.md). `easy` holds one sentence per line.
Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from etr_common import base_lang, cache_dir, read_text, write_text  # noqa: E402

SKILL = Path(__file__).resolve().parent.parent
SHIPPED = SKILL / "dictionaries"
TIER_ORDER = {"user": 0, "public": 1, "global": 2}
WORD = re.compile(r"[\wÀ-ſ]+(?:-[\wÀ-ſ]+)*")
UA = "easy-to-read-skill dictionary (+https://github.com/athelas64/etr-slovnik)"


# ---------------------------------------------------------------- paths and loading
def cached_dir() -> Path:
    d = cache_dir() / "dictionaries"
    d.mkdir(parents=True, exist_ok=True)
    return d


def user_path(lang: str) -> Path:
    env = os.environ.get("ETR_USER_DICT")
    if env:
        return Path(env)
    return cache_dir() / f"user-{lang}.json"


def sources() -> dict:
    p = SHIPPED / "sources.json"
    if p.exists():
        return json.loads(read_text(p))
    return {"repo": "athelas64/etr-slovnik", "branch": "main", "manifest": "manifest.json", "check_interval_hours": 24}


def _load(path: Path) -> dict | None:
    try:
        d = json.loads(read_text(path))
    except Exception as e:  # noqa: BLE001
        print(f"warning: {path} is not a valid dictionary: {e}", file=sys.stderr)
        return None
    d["_path"] = str(path)
    return d


def load_tiers(lang: str) -> list[dict]:
    """Dictionaries for `lang`, user first. A cached download wins over the shipped copy
    when its version is newer."""
    found: dict[str, dict] = {}
    for folder in (SHIPPED, cached_dir()):
        if not folder.exists():
            continue
        for p in sorted(folder.glob("*.json")):
            if p.name in ("sources.json", "manifest.json", "state.json"):
                continue
            d = _load(p)
            if not d or "entries" not in d or d.get("lang") != lang:
                continue
            prev = found.get(p.name)
            if prev is None or str(d.get("version", "")) >= str(prev.get("version", "")):
                found[p.name] = d
    tiers = list(found.values())
    up = user_path(lang)
    if up.exists():
        d = _load(up)
        if d:
            tiers.append(d)
    tiers.sort(key=lambda d: TIER_ORDER.get(d.get("tier", "global"), 9))
    return tiers


def new_user_file(lang: str) -> dict:
    return {
        "name": "Vlastný slovník" if lang == "sk" else "Personal dictionary",
        "description": "Ťažké slová a vysvetlenia, ktoré si používateľ ukladá pre vlastné texty.",
        "tier": "user", "lang": lang, "version": date.today().isoformat(), "updated": date.today().isoformat(),
        "entries": [],
    }


def save_user(d: dict, lang: str) -> Path:
    d = {k: v for k, v in d.items() if not k.startswith("_")}
    d["updated"] = date.today().isoformat()
    d["version"] = date.today().isoformat()
    p = user_path(lang)
    write_text(p, json.dumps(d, ensure_ascii=False, indent=2) + "\n")
    return p


# ---------------------------------------------------------------- matching
def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


# Inflectional endings of Slovak and Czech nouns, adjectives and a few verb forms, on
# normalised (diacritics-free) text. A text word matches a key word when both share the
# same stem and differ only by one of these endings.
ENDINGS = sorted({
    "", "a", "e", "i", "o", "u", "y", "ou", "om", "ov", "am", "ach", "och", "iach", "ami", "mi", "ia", "ie", "iu",
    "im", "ych", "ym", "ymi", "eho", "emu", "ej", "eho", "iho", "ieho", "iemu", "imi", "ovi", "ove", "ova", "ovo",
    "ovia", "ami", "ete", "ate", "ite", "ame", "ime", "at", "it", "ut", "ct", "st", "te", "me",
}, key=len, reverse=True)


def stem(tok: str) -> str:
    """Strip one inflectional ending from a normalised word, keeping at least 4 letters."""
    for end in ENDINGS:
        if end and tok.endswith(end) and len(tok) - len(end) >= 4:
            return tok[: -len(end)]
    return tok


def _same_word(text_tok: str, key_tok: str) -> bool:
    nt, nk = norm(text_tok), norm(key_tok)
    if nt == nk:
        return True
    if len(nk) < 4:
        return False
    sk = stem(nk)
    if not nt.startswith(sk):
        return False
    return nt[len(sk):] in ENDINGS


def entry_keys(e: dict) -> list[str]:
    keys = [e.get("term", "")] + list(e.get("forms") or [])
    return [k for k in keys if k]


def entry_synonyms(e: dict) -> list[str]:
    return [k for k in (e.get("same_words") or []) if k]


def _match_at(text_toks: list[str], i: int, key_toks: list[str], exact: bool) -> bool:
    if i + len(key_toks) > len(text_toks):
        return False
    for j, kt in enumerate(key_toks):
        tt = text_toks[i + j]
        if exact:
            if tt != kt:
                return False
            continue
        if not _same_word(tt, kt):
            return False
    return True


def _clean_line(raw: str) -> str:
    """A Markdown line as the reader sees it: link targets, placeholders and markup removed."""
    s = re.sub(r"\[([^\]]*)\]\([^)]+\)", r"\1", raw)
    s = re.sub(r"\[(?:DOPLNIŤ|DOPLNIT|DOPLŇTE|ADD|TODO|OVERIŤ|OVĚŘIT|CHECK)[^\]]*\]", "", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return s.lstrip("#>-*+ ").replace("**", "")


def text_tokens(md: str) -> list[tuple[int, str]]:
    """(line number, token) for the prose of a Markdown file; headings included, code and
    front matter skipped, link targets and placeholders removed."""
    out = []
    lines = md.split("\n")
    skip_until = 0
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                skip_until = j + 1
                break
    in_code = False
    for i, raw in enumerate(lines, 1):
        if i <= skip_until:
            continue
        if raw.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code or raw.lstrip().startswith("|") or raw.lstrip().startswith("<"):
            continue
        for m in WORD.finditer(_clean_line(raw)):
            out.append((i, m.group(0)))
    return out


# ---------------------------------------------------------------- context: scope and exclusions
VERDICTS = {"used": "použité", "rewritten": "prepísané", "not-explained": "nevysvetľujeme",
            "wrong-match": "nesúvisí", "other-sense": "iný význam"}


def front_matter(md: str) -> dict[str, str]:
    """The simple `key: value` lines of a Markdown front matter block."""
    lines = md.split("\n")
    out: dict[str, str] = {}
    if lines and lines[0].strip() == "---":
        for ln in lines[1:]:
            if ln.strip() == "---":
                break
            m = re.match(r"\s*([A-Za-z_][\w-]*)\s*:\s*(.*)$", ln)
            if m:
                out[m.group(1).lower()] = m.group(2).strip().strip("\"'")
    return out


def _scope_value(s: str) -> str:
    s = s.strip().strip("\"'").lower()
    if "://" in s:
        from urllib.parse import urlparse
        s = (urlparse(s).hostname or "").lower()
    return s[4:] if s.startswith("www.") else s


def job_scopes(md: str, extra: list[str] | None = None) -> list[str]:
    """Scopes of a text: the host of its source address (www.minv.sk -> minv.sk), a
    `scope:` line in the front matter, and --scope values. Order kept, duplicates dropped."""
    fm = front_matter(md)
    raw = []
    if fm.get("source", "").startswith("http"):
        raw.append(fm["source"])
    raw += re.split(r"[,\[\]]", fm.get("scope", ""))
    for x in extra or []:
        raw += x.split(",")
    out = [_scope_value(s) for s in raw if s and s.strip().strip("\"'")]
    return list(dict.fromkeys(s for s in out if s))


def entry_applies(e: dict, scopes: list[str]) -> bool:
    """An entry without a scope applies everywhere; a scoped entry only where the scopes meet."""
    sc = {_scope_value(s) for s in (e.get("scope") or [])}
    return not sc or bool(sc & set(scopes))


def personal_exclusions(tiers: list[dict]) -> dict[str, set[str]]:
    """Entry id -> normalised word forms that must not match it, from the user's file."""
    out: dict[str, set[str]] = {}
    for d in tiers:
        if d.get("tier") != "user":
            continue
        for x in d.get("exclusions") or []:
            if x.get("id") and x.get("form"):
                out.setdefault(x["id"], set()).add(" ".join(norm(w) for w in WORD.findall(x["form"])))
    return out


def scoped_elsewhere(tiers: list[dict], scopes: list[str]) -> list[dict]:
    """Scoped entries that do not apply to this text (meant for other bodies or topics)."""
    return [e for d in tiers for e in d.get("entries", []) if e.get("scope") and not entry_applies(e, scopes)]


def find_in_text(md: str, tiers: list[dict], scopes: list[str] | None = None,
                 exclusions: dict[str, set[str]] | None = None) -> list[dict]:
    """Entries whose term or forms occur in the text. One record per entry id, with every
    occurrence (line, matched words, the sentence) and every tier that has it (best first).
    Scoped entries count only when the text has the same scope; word forms listed in an
    entry's `exclude` or in the user's personal exclusions are not matches."""
    scopes = scopes or []
    exclusions = exclusions if exclusions is not None else personal_exclusions(tiers)
    toks = text_tokens(md)
    words = [t for _, t in toks]
    src_lines = md.split("\n")
    hits: dict[str, dict] = {}
    for d in tiers:
        tier = d.get("tier", "global")
        for e in d.get("entries", []):
            if not entry_applies(e, scopes):
                continue
            excl = {" ".join(norm(w) for w in WORD.findall(x)) for x in (e.get("exclude") or [])} | exclusions.get(e["id"], set())
            spans: set[tuple[int, int]] = set()  # (first token, number of tokens) of each match
            skipped = 0
            # term and forms: inflection-aware; same_words (synonyms, abbreviations): exact words only
            candidates = [(k, False) for k in entry_keys(e)] + [(k, True) for k in entry_synonyms(e)]
            for key, syn in candidates:
                kt = WORD.findall(key)
                if not kt:
                    continue
                exact = syn or (len(kt) == 1 and kt[0].isupper() and len(kt[0]) <= 6)  # NPM, CRPD, DSS
                for i in range(len(words)):
                    if exact and syn:
                        ok = i + len(kt) <= len(words) and all(norm(words[i + j]) == norm(k) for j, k in enumerate(kt))
                    else:
                        ok = _match_at(words, i, kt, exact)
                    if not ok:
                        continue
                    if " ".join(norm(w) for w in words[i:i + len(kt)]) in excl:
                        skipped += 1
                        continue
                    spans.add((i, len(kt)))
            # a longer form and the bare word can match the same place ("na úrade", "úrade"): keep the longest
            spans = {(i, n) for i, n in spans if not any(j <= i and i + n <= j + m and (j, m) != (i, n) for j, m in spans)}
            if not spans:
                continue
            occurrences = []
            for i, n in sorted(spans):
                ln = toks[i][0]
                occurrences.append({"line": ln, "form": " ".join(words[i:i + n]),
                                    "sentence": _clean_line(src_lines[ln - 1]).strip()})
            rec = hits.setdefault(e["id"], {"id": e["id"], "term": e["term"], "lines": [], "occurrences": [],
                                            "matched": occurrences[0]["form"], "excluded": 0, "tiers": []})
            seen = {(o["line"], o["form"]) for o in rec["occurrences"]}
            rec["occurrences"] += [o for o in occurrences if (o["line"], o["form"]) not in seen]
            rec["occurrences"].sort(key=lambda o: (o["line"], o["form"]))
            rec["lines"] = sorted({o["line"] for o in rec["occurrences"]})
            rec["excluded"] += skipped
            rec["tiers"].append({"tier": tier, "file": Path(d["_path"]).name, "entry": e,
                                 "licence": (d.get("licence") or {}).get("name")})
    for rec in hits.values():
        # best tier first; within a tier, an entry scoped to this text before a general one
        rec["tiers"].sort(key=lambda t: (TIER_ORDER.get(t["tier"], 9), 0 if t["entry"].get("scope") else 1))
    return sorted(hits.values(), key=lambda r: (r["lines"][0], r["term"]))


# ---------------------------------------------------------------- verdicts for one text
def decisions_path(easy: str, work: str | None = None) -> Path:
    if work:
        return Path(work) / "dictionary-decisions.json"
    cand = Path(easy).resolve().parent / "work"
    return (cand if cand.is_dir() else Path("work")) / "dictionary-decisions.json"


def read_decisions_file(path: Path) -> dict:
    """{"texts": {"<file name>": {"scope": [...], "updated": ..., "decisions": [...]}}}: verdicts are
    kept per text, so two texts sharing a work folder never borrow each other's verdicts."""
    if path.exists():
        try:
            data = json.loads(read_text(path))
            if isinstance(data.get("texts"), dict):
                return data
        except Exception as e:  # noqa: BLE001
            print(f"warning: {path} is not readable ({e}); starting a new record", file=sys.stderr)
    return {"texts": {}}


def load_decisions(path: Path, easy: str | None = None) -> dict:
    """The verdicts recorded for one text (by file name); with no text, all of them."""
    data = read_decisions_file(path)
    if easy is None:
        return {"decisions": [x for t in data["texts"].values() for x in t.get("decisions", [])]}
    return data["texts"].get(Path(easy).name, {"decisions": []})


def verdict_for(hit: dict, decisions: list[dict]) -> dict | None:
    """The decision that covers a hit: the latest used/rewritten/other-sense for its id, or
    wrong-match decisions that cover every form still matched."""
    ds = [x for x in decisions if x.get("id") == hit["id"]]
    main = [x for x in ds if x.get("verdict") != "wrong-match"]
    if main:
        return main[-1]
    forms = {norm(o["form"]) for o in hit.get("occurrences", [])}
    wrong = {norm(x.get("form", "")) for x in ds if x.get("verdict") == "wrong-match"}
    if ds and forms and forms <= wrong:
        return ds[-1]
    return None


def long_words_without_entry(md: str, hits: list[dict], min_len: int = 12) -> list[tuple[int, str]]:
    covered_lines_words = set()
    for h in hits:
        for t in h["tiers"][:1]:
            for k in entry_keys(t["entry"]):
                for w in WORD.findall(k):
                    covered_lines_words.add(stem(norm(w)))
    seen, out = set(), []
    for ln, tok in text_tokens(md):
        if len(tok) < min_len or tok[0].isupper() and ln > 1:
            continue
        n = norm(tok)
        if stem(n) in covered_lines_words or n in seen:
            continue
        seen.add(n)
        out.append((ln, tok))
    return out


def find_term(term: str, tiers: list[dict]) -> list[tuple[str, dict, dict]]:
    q = norm(term)
    out = []
    for d in tiers:
        for e in d.get("entries", []):
            keys = [norm(k) for k in entry_keys(e)]
            if q in keys or e["id"] == slug(term) or any(q in k for k in keys):
                out.append((d.get("tier", "global"), d, e))
    return out


# ---------------------------------------------------------------- rendering
def glossary_md(entries: list[dict], fmt: str = "glossary") -> str:
    """The skill's glossary convention (**Term** then the sentences), or a pandoc
    definition list (`Term` / `:   sentence`), which renders as <dl> in HTML."""
    out = []
    for e in entries:
        lines = [ln for ln in e["easy"].split("\n") if ln.strip()]
        if e.get("example"):
            lines += [ln for ln in e["example"].split("\n") if ln.strip()]
        if fmt == "dl":
            out.append(e["term"])
            out.append(":   " + lines[0])
            out.extend("    " + ln for ln in lines[1:])
        else:
            out.append(f"**{e['term']}**")
            out.extend(lines)
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def render_lookup(path: str, hits: list[dict], missing: list[tuple[int, str]], tiers: list[dict],
                  scopes: list[str] | None = None, decisions: list[dict] | None = None, elsewhere: int = 0) -> str:
    out = [f"# Dictionary lookup: {Path(path).name}", ""]
    names = ", ".join(f"{d.get('tier')} ({Path(d['_path']).name}, {len(d.get('entries', []))} entries)" for d in tiers)
    out.append(f"Dictionaries: {names or 'none'}")
    out.append(f"Scope of this text: {', '.join(scopes) if scopes else 'none (scoped entries are not offered)'}"
               + (f" · {elsewhere} scoped entries are meant for other bodies or topics and were left out" if elsewhere else ""))
    out.append("")
    decisions = decisions or []
    open_n = sum(1 for h in hits if not verdict_for(h, decisions))
    out.append(f"## Words the dictionaries explain ({len(hits)}, {open_n} without a verdict)")
    out.append("")
    if not hits:
        out.append("- none")
    for h in hits:
        best = h["tiers"][0]
        e = best["entry"]
        others = ", ".join(t["tier"] for t in h["tiers"][1:])
        status = e.get("status", "draft")
        flag = "" if status != "draft" else " · draft, check before reuse"
        lic = f" · {best['licence']}" if best.get("licence") else ""
        sc = f" · scope {', '.join(e['scope'])}" if e.get("scope") else ""
        v = verdict_for(h, decisions)
        verdict = f" · verdict: {v['verdict']}" if v else " · NO VERDICT YET"
        out.append(f"- **{e['term']}** · id {h['id']} · {best['tier']}{lic}{sc}{flag}" + (f" · also in {others}" if others else "") + verdict)
        out.append("    In the text:")
        for o in h["occurrences"][:4]:
            out.append(f"      line {o['line']} ({o['form']}): {o['sentence']}")
        if len(h["occurrences"]) > 4:
            out.append(f"      ... {len(h['occurrences']) - 4} more")
        if h.get("excluded"):
            out.append(f"    {h['excluded']} occurrence(s) skipped as excluded word forms")
        out.append("    Dictionary explanation:")
        for ln in e["easy"].split("\n"):
            if ln.strip():
                out.append(f"      {ln}")
        if e.get("note"):
            out.append(f"    Note for the writer: {e['note']}")
    out.append("")
    out.append(f"## Long words without an entry ({len(missing)})")
    out.append("")
    if not missing:
        out.append("- none")
    for ln, w in missing[:40]:
        out.append(f"- line {ln}: {w}")
    out.append("")
    out.append("Read each hit in its sentence and decide whether the dictionary's word is the word in the text, "
               "and whether its explanation fits this body and this reader. Record it:")
    out.append("  dictionary.py decide TERM used|rewritten|not-explained|wrong-match|other-sense --text EASY.md [--form F] --reason \"...\"")
    out.append("used = explanation reused · rewritten = right term, own wording · not-explained = right term, deliberately left unexplained (an everyday word, an official name, an analogy) · wrong-match = not this word at all "
               "(saves a personal exclusion) · other-sense = this term, but it means something else at this body. "
               "A public or global entry is a starting point, not a reader-checked text.")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- update
def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _token() -> str | None:
    for var in ("ETR_SLOVNIK_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(var):
            return os.environ[var]
    gh = shutil.which("gh")
    if gh:
        try:
            p = subprocess.run([gh, "auth", "token"], capture_output=True, text=True, timeout=20)
            if p.returncode == 0 and p.stdout.strip():
                return p.stdout.strip()
        except Exception:  # noqa: BLE001
            pass
    return None


def _fetch(repo: str, branch: str, path: str, token: str | None, etag: str | None = None) -> tuple[int, bytes, str | None]:
    """GET a repository file: the raw URL first (public repo), then the API with a token
    (private repo). Returns (status, body, etag); 304 means unchanged."""
    urls = [(f"https://raw.githubusercontent.com/{repo}/{branch}/{path}", {})]
    if token:
        urls.append((f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}",
                     {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.raw+json",
                      "X-GitHub-Api-Version": "2022-11-28"}))
    last = (0, b"", None)
    for url, headers in urls:
        h = {"User-Agent": UA, **headers}
        if etag:
            h["If-None-Match"] = etag
        req = urllib.request.Request(url, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read(), r.headers.get("ETag")
        except urllib.error.HTTPError as e:
            if e.code == 304:
                return 304, b"", etag
            last = (e.code, b"", None)
            if e.code in (401, 403, 404) and token:
                continue
            return last
        except Exception:  # noqa: BLE001
            return (0, b"", None)
    return last


def update(force: bool = False, quiet: bool = False) -> str:
    src = sources()
    state_p = cached_dir() / "state.json"
    state = json.loads(read_text(state_p)) if state_p.exists() else {}
    now = datetime.now(timezone.utc)
    if not force and state.get("checked"):
        try:
            last = datetime.fromisoformat(state["checked"])
            hours = (now - last).total_seconds() / 3600
            if hours < float(src.get("check_interval_hours", 24)):
                return f"dictionaries checked {hours:.0f} h ago; next check after {src.get('check_interval_hours', 24)} h (--force to check now)"
        except ValueError:
            pass
    token = _token()
    status, body, etag = _fetch(src["repo"], src["branch"], src["manifest"], token, None if force else state.get("etag"))
    if status == 304:
        state["checked"] = now.isoformat()
        write_text(state_p, json.dumps(state, indent=2))
        return "dictionaries are current (manifest unchanged)"
    if status != 200:
        why = {0: "no network", 401: "not authorised", 403: "not authorised", 404: "not found (private repository without a token?)"}.get(status, f"HTTP {status}")
        return f"dictionary update skipped: {why}; using the local copies"
    try:
        manifest = json.loads(body.decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        return f"dictionary update skipped: manifest unreadable ({e})"
    changed = []
    for rel, meta in manifest.get("files", {}).items():
        name = Path(rel).name
        local = cached_dir() / name
        shipped = SHIPPED / name
        have = local if local.exists() else shipped if shipped.exists() else None
        if have and _sha(have.read_bytes()) == meta.get("sha256"):
            continue
        st, data, _ = _fetch(src["repo"], src["branch"], rel, token)
        if st != 200:
            if not quiet:
                print(f"  {name}: download failed (HTTP {st})", file=sys.stderr)
            continue
        if _sha(data) != meta.get("sha256"):
            if not quiet:
                print(f"  {name}: checksum mismatch, kept the old copy", file=sys.stderr)
            continue
        try:
            json.loads(data.decode("utf-8"))
        except Exception:  # noqa: BLE001
            continue
        tmp = local.with_suffix(".part")
        tmp.write_bytes(data)
        if local.exists():
            shutil.copyfile(local, local.with_suffix(".bak"))
        os.replace(tmp, local)
        changed.append(f"{name} ({meta.get('entries')} entries, version {meta.get('version')})")
    state.update({"checked": now.isoformat(), "etag": etag, "manifest_version": manifest.get("version"),
                  "manifest_updated": manifest.get("updated")})
    write_text(state_p, json.dumps(state, indent=2))
    if changed:
        return "dictionaries updated: " + "; ".join(changed)
    return f"dictionaries are current (manifest version {manifest.get('version')})"


# ---------------------------------------------------------------- personal exclusions and proposals
TIER_SK = {"user": "vlastný", "public": "verejná správa", "global": "globálny"}

PROPOSAL_CAVEAT = (
    "> Upozornenie: vylúčenie v spoločnom slovníku je globálna zmena. Platí pre všetky úrady a všetky texty,\n"
    "> ktoré slovník používajú. Pre niektoré orgány môže byť kontext stále správny: ten istý tvar môže v ich\n"
    "> textoch naozaj znamenať heslo zo slovníka. Pred zlúčením posúďte, či nestačí osobné vylúčenie\n"
    "> autora alebo obmedzenie hesla rozsahom (scope) na konkrétny úrad či tému.\n")


def add_personal_exclusion(lang: str, rec: dict) -> tuple[Path, bool]:
    """Save a word form that is not the given entry into the user's file. Returns (path, added)."""
    p = user_path(lang)
    d = (_load(p) if p.exists() else None) or new_user_file(lang)
    ex = d.setdefault("exclusions", [])
    if any(x.get("id") == rec["id"] and norm(x.get("form", "")) == norm(rec["form"]) for x in ex):
        return p, False
    ex.append(rec)
    ex.sort(key=lambda x: (norm(x.get("term", "")), norm(x.get("form", ""))))
    save_user(d, lang)
    return p, True


def proposal_md(items: list[dict]) -> str:
    """The note proposing exclusions to the shared repository, with the caveat that it is a global change."""
    out = ["# Návrh vylúčení pre spoločný slovník etr-slovnik", "",
           "Pri tvorbe ľahko čitateľného textu slovník označil slovo, ktoré nie je heslom zo slovníka.",
           "Autor si tvar vylúčil vo vlastnom slovníku. Navrhuje zvážiť rovnaké vylúčenie v spoločnom slovníku.", "",
           PROPOSAL_CAVEAT]
    for x in items:
        out.append(f"## {x.get('term')} · heslo `{x.get('id')}` · {x.get('file', '?')}")
        out.append("")
        out.append(f"- Vylúčiť tvar: **{x.get('form')}**")
        if x.get("sentence"):
            out.append(f"- Veta z textu: {x['sentence']}")
        if x.get("reason"):
            out.append(f"- Dôvod: {x['reason']}")
        if x.get("scope"):
            out.append(f"- Zistené v texte pre: {', '.join(x['scope'])}")
        out.append(f"- Navrhovaná zmena hesla: `\"exclude\": [\"{x.get('form')}\"]`")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def write_job_proposals(dp: Path) -> Path | None:
    """work/dictionary-proposals.md: wrong matches of shared entries from the texts in this work folder."""
    items = [dict(x, scope=t.get("scope", [])) for t in read_decisions_file(dp)["texts"].values()
             for x in t.get("decisions", []) if x.get("verdict") == "wrong-match" and x.get("tier") in ("public", "global")]
    target = dp.parent / "dictionary-proposals.md"
    if not items:
        if target.exists():
            target.unlink()
        return None
    write_text(target, proposal_md(items))
    return target


# ---------------------------------------------------------------- commands
def _hits_for(easy: str, lang: str, scope_args: list[str] | None):
    tiers = load_tiers(lang)
    md = read_text(easy)
    scopes = job_scopes(md, scope_args)
    return tiers, md, scopes, find_in_text(md, tiers, scopes)


def cmd_lookup(a) -> None:
    lang = base_lang(a.lang)
    msg = update(quiet=True)
    if a.verbose:
        print(msg, file=sys.stderr)
    tiers, md, scopes, hits = _hits_for(a.easy, lang, a.scope)
    decisions = load_decisions(decisions_path(a.easy, a.work), a.easy)["decisions"]
    missing = long_words_without_entry(md, hits)
    print(render_lookup(a.easy, hits, missing, tiers, scopes, decisions, len(scoped_elsewhere(tiers, scopes))))
    if a.json:
        write_text(a.json, json.dumps({
            "lang": lang,
            "scope": scopes,
            "dictionaries": [{"tier": d.get("tier"), "file": Path(d["_path"]).name, "version": d.get("version"),
                              "entries": len(d.get("entries", [])), "licence": (d.get("licence") or {}).get("name")} for d in tiers],
            "found": [{"id": h["id"], "term": h["term"], "lines": h["lines"], "occurrences": h["occurrences"],
                       "excluded": h["excluded"], "verdict": (verdict_for(h, decisions) or {}).get("verdict"),
                       "tiers": [{"tier": t["tier"], "file": t["file"], "licence": t["licence"], "entry": t["entry"]} for t in h["tiers"]]} for h in hits],
            "long_words_without_entry": [{"line": ln, "word": w} for ln, w in missing],
        }, ensure_ascii=False, indent=2) + "\n")


def _match_hit(term: str, hits: list[dict]) -> dict | None:
    q = norm(term.strip())
    for h in hits:
        if h["id"] == slug(term) or norm(h["term"]) == q:
            return h
    for h in hits:
        if any(norm(o["form"]) == q for o in h["occurrences"]):
            return h
    return None


def cmd_decide(a) -> None:
    lang = base_lang(a.lang)
    tiers, md, scopes, hits = _hits_for(a.text, lang, a.scope)
    h = _match_hit(a.term, hits)
    if not h:
        sys.exit(f"'{a.term}' is not a dictionary hit in {a.text}. Hits: " + (", ".join(x["term"] for x in hits) or "none"))
    if a.verdict in ("not-explained", "wrong-match", "other-sense") and not a.reason:
        sys.exit("say why with --reason: what the word means in this sentence, or why it needs no explanation")
    best = h["tiers"][0]
    e = best["entry"]
    occ = h["occurrences"]
    form = None
    if a.verdict == "wrong-match":
        forms = list(dict.fromkeys(o["form"] for o in occ))
        if a.form:
            if norm(a.form) not in {norm(f) for f in forms}:
                sys.exit(f"'{a.form}' is not among the matched words: {', '.join(forms)}")
            form = next(f for f in forms if norm(f) == norm(a.form))
        elif len(forms) == 1:
            form = forms[0]
        else:
            sys.exit(f"several words matched ({', '.join(forms)}); name the wrong one with --form")
        occ = [o for o in occ if norm(o["form"]) == norm(form)]
    if a.line:
        occ = [o for o in occ if o["line"] == a.line] or occ
    rec = {"id": h["id"], "term": h["term"], "verdict": a.verdict, "verdict_sk": VERDICTS[a.verdict],
           "lines": [o["line"] for o in occ], "sentence": occ[0]["sentence"], "tier": best["tier"], "file": best["file"],
           "status": e.get("status", "draft"), "reason": a.reason or "", "date": date.today().isoformat()}
    if form:
        rec["form"] = form
    if e.get("scope"):
        rec["entry_scope"] = e["scope"]
    dp = decisions_path(a.text, a.work)
    all_data = read_decisions_file(dp)
    data = all_data["texts"].setdefault(Path(a.text).name, {"decisions": []})

    def replaced(x: dict) -> bool:
        if x.get("id") != h["id"]:
            return False
        if a.verdict == "wrong-match":
            return x.get("verdict") == "wrong-match" and norm(x.get("form", "")) == norm(form)
        return x.get("verdict") != "wrong-match"

    data["decisions"] = [x for x in data.get("decisions", []) if not replaced(x)] + [rec]
    data.update({"scope": scopes, "updated": datetime.now().isoformat(timespec="seconds")})
    dp.parent.mkdir(parents=True, exist_ok=True)
    write_text(dp, json.dumps(all_data, ensure_ascii=False, indent=2) + "\n")
    print(f"{h['term']}: {a.verdict} ({VERDICTS[a.verdict]}) recorded in {dp}")
    if a.verdict == "wrong-match":
        if not a.no_exclude:
            up, added = add_personal_exclusion(lang, {
                "id": h["id"], "term": h["term"], "form": form, "reason": a.reason, "sentence": rec["sentence"],
                "scope": scopes, "text": Path(a.text).name, "added": date.today().isoformat()})
            print(f"  personal exclusion {'saved' if added else 'already there'}: '{form}' is not '{h['term']}' ({up})")
        prop = write_job_proposals(dp)
        if prop:
            print(f"  proposal for the shared dictionary written to {prop} (a global change; tell the user, do not submit unasked)")
    elif a.verdict == "other-sense":
        sc = scopes[0] if scopes else "<body or topic>"
        print(f"  write your own explanation in the text; to reuse it for this body next time:\n"
              f"  dictionary.py add \"{h['term']}\" --easy \"...\" --scope {sc}   (only when the user agrees)")


def cmd_verdicts(a) -> None:
    lang = base_lang(a.lang)
    tiers, md, scopes, hits = _hits_for(a.text, lang, a.scope)
    decs = load_decisions(decisions_path(a.text, a.work), a.text)["decisions"]
    rows = []
    for h in hits:
        v = verdict_for(h, decs)
        best = h["tiers"][0]
        rows.append({"id": h["id"], "term": h["term"], "lines": h["lines"], "tier": best["tier"], "file": best["file"],
                     "verdict": v["verdict"] if v else None, "reason": (v or {}).get("reason", ""), "form": None})
    hit_ids = {h["id"] for h in hits}
    for x in decs:  # wrong matches no longer show up as hits once excluded; list them anyway
        if x.get("verdict") == "wrong-match" and not (x["id"] in hit_ids and any(r["term"] == x["term"] and r["verdict"] == "wrong-match" for r in rows)):
            rows.append({"id": x["id"], "term": x["term"], "lines": x.get("lines", []), "tier": x.get("tier"), "file": x.get("file"),
                         "verdict": "wrong-match", "reason": x.get("reason", ""), "form": x.get("form")})
    rows.sort(key=lambda r: (r["lines"][0] if r["lines"] else 0, r["term"]))
    open_n = sum(1 for r in rows if not r["verdict"])
    # two entries can share a term (one per dictionary); then the id tells them apart
    dup = {t for t in (r["term"] for r in rows) if sum(1 for x in rows if x["term"] == t and not x["form"]) > 1}
    for r in rows:
        r["label"] = f"{r['term']} ({r['id']})" if r["term"] in dup and not r["form"] else r["term"]
    if a.markdown:
        print("| Slovo v texte | Riadok | Slovník | Rozhodnutie | Dôvod |")
        print("|---|---|---|---|---|")
        for r in rows:
            word = f"{r['form']} (nie heslo {r['term']})" if r["form"] else r["label"]
            lines = ", ".join(str(x) for x in r["lines"][:6])
            verdict = VERDICTS.get(r["verdict"], "bez rozhodnutia") if r["verdict"] else "**bez rozhodnutia**"
            print(f"| {word} | {lines} | {TIER_SK.get(r['tier'], r['tier'])} | {verdict} | {r['reason'].replace('|', '/')} |")
        return
    print(f"# Verdicts for {Path(a.text).name} · scope {', '.join(scopes) or 'none'} · {len(rows)} hits, {open_n} without a verdict")
    for r in rows:
        word = f"{r['form']} -> not '{r['term']}'" if r["form"] else r["label"]
        print(f"- {word} · lines {', '.join(str(x) for x in r['lines'][:6])} · {r['tier']} · {r['verdict'] or 'NO VERDICT'}"
              + (f" · {r['reason']}" if r["reason"] else ""))


def cmd_exclusions(a) -> None:
    lang = base_lang(a.lang)
    p = user_path(lang)
    d = _load(p) if p.exists() else None
    ex = (d or {}).get("exclusions") or []
    if a.remove:
        if not d:
            sys.exit(f"no user dictionary at {p}")
        keep = [x for x in ex if not (norm(x.get("form", "")) == norm(a.remove) and (not a.term or x.get("id") == slug(a.term) or norm(x.get("term", "")) == norm(a.term)))]
        if len(keep) == len(ex):
            sys.exit(f"no personal exclusion '{a.remove}'" + (f" for '{a.term}'" if a.term else ""))
        d["exclusions"] = keep
        save_user(d, lang)
        print(f"removed {len(ex) - len(keep)} personal exclusion(s) '{a.remove}' from {p}")
        return
    if not ex:
        print(f"no personal exclusions in {p}")
        return
    shared = {e["id"]: Path(t["_path"]).name for t in load_tiers(lang) if t.get("tier") in ("public", "global")
              for e in t.get("entries", [])}
    if not (a.proposal or a.issue):
        print(f"# Personal exclusions ({len(ex)}) · {p}")
        for x in ex:
            where = shared.get(x["id"], "your own entry")
            print(f"- '{x.get('form')}' is not '{x.get('term')}' ({where}) · {x.get('reason', '')} · {x.get('text', '')} {x.get('added', '')}")
        return
    items = [dict(x, file=shared[x["id"]]) for x in ex if x.get("id") in shared]
    if not items:
        print("no personal exclusion concerns a shared entry; nothing to propose")
        return
    body = proposal_md(items)
    print(body)
    if a.issue:
        src = sources()
        gh = shutil.which("gh")
        if not gh:
            sys.exit("gh (GitHub CLI) is not installed; paste the text above into a new issue at https://github.com/" + src["repo"] + "/issues/new")
        tmp = cache_dir() / "exclusion-proposal.md"
        write_text(tmp, body)
        title = f"Návrh vylúčenia: {items[0]['form']} (heslo {items[0]['term']})" if len(items) == 1 else f"Návrh vylúčení zo slovníka ({len(items)})"
        r = subprocess.run([gh, "issue", "create", "--repo", src["repo"], "--title", title, "--body-file", str(tmp),
                            "--label", "návrh vylúčenia"], capture_output=True, text=True)
        if r.returncode != 0 and "not found" in (r.stderr or "").lower():
            r = subprocess.run([gh, "issue", "create", "--repo", src["repo"], "--title", title, "--body-file", str(tmp)],
                               capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr.strip())


def cmd_find(a) -> None:
    tiers = load_tiers(base_lang(a.lang))
    res = find_term(a.term, tiers)
    if not res:
        print(f"no entry for '{a.term}'")
        return
    for tier, d, e in res:
        sc = f" · scope {', '.join(e['scope'])}" if e.get("scope") else ""
        print(f"## {e['term']} · {tier} · {Path(d['_path']).name} · {e.get('status', 'draft')}{sc}")
        if e.get("forms"):
            print("forms: " + ", ".join(e["forms"]))
        if e.get("exclude"):
            print("not these words: " + ", ".join(e["exclude"]))
        print(e["easy"])
        if e.get("example"):
            print("Example:\n" + e["example"])
        if e.get("note"):
            print("Note: " + e["note"])
        if e.get("source", {}).get("url"):
            print("Source: " + e["source"]["url"])
        print()


def cmd_add(a) -> None:
    lang = base_lang(a.lang)
    p = user_path(lang)
    d = _load(p) if p.exists() else new_user_file(lang)
    d = d or new_user_file(lang)
    easy = a.easy.replace("\\n", "\n").strip()
    e = {"id": slug(a.term), "term": a.term.strip()}
    if a.forms:
        e["forms"] = [f.strip() for f in a.forms.split(",") if f.strip()]
    e["easy"] = easy
    if a.example:
        e["example"] = a.example.replace("\\n", "\n").strip()
    if a.domain:
        e["domain"] = a.domain
    if a.note:
        e["note"] = a.note
    if a.source:
        e["source"] = {"url": a.source} if a.source.startswith("http") else {"name": a.source}
    scope = _scope_list(a.scope)
    if scope:
        e["scope"] = scope
    e["status"] = "draft"
    e["origin"] = "human"
    e["added"] = date.today().isoformat()
    # one entry per term and scope: the same term may have a general entry and entries for particular bodies
    same = lambda x: x["id"] == e["id"] and _scope_key(x) == _scope_key(e)  # noqa: E731
    if any(same(x) for x in d["entries"]) and not a.replace:
        sys.exit(f"'{a.term}'{' for ' + ', '.join(scope) if scope else ''} is already in {p}; use --replace to overwrite it")
    d["entries"] = [x for x in d["entries"] if not same(x)] + [e]
    d["entries"].sort(key=lambda x: (norm(x["term"]), _scope_key(x)))
    warn = check_easy(easy)
    saved = save_user(d, lang)
    print(f"added '{e['term']}'{' for ' + ', '.join(scope) if scope else ''} to {saved} ({len(d['entries'])} entries)")
    for w in warn:
        print("  note: " + w)


def _scope_list(raw: str | None) -> list[str]:
    return list(dict.fromkeys(_scope_value(s) for s in (raw or "").split(",") if s.strip()))


def _scope_key(e: dict) -> tuple:
    return tuple(sorted(_scope_value(s) for s in (e.get("scope") or [])))


def check_easy(easy: str) -> list[str]:
    out = []
    for ln in easy.split("\n"):
        n = len(WORD.findall(ln))
        if n > 15:
            out.append(f"{n} words in one sentence (limit 15): {ln[:60]}")
        if re.search(r"[()\[\]/;§&#—–%]", ln):
            out.append(f"special character in: {ln[:60]}")
        if re.search(r"[.!?]\s+[A-ZÁÄČĎÉÍĹĽŇÓÔŔŠŤÚÝŽ]", ln):
            out.append(f"two sentences on one line: {ln[:60]}")
    return out


def cmd_remove(a) -> None:
    lang = base_lang(a.lang)
    p = user_path(lang)
    d = _load(p) if p.exists() else None
    if not d:
        sys.exit(f"no user dictionary at {p}")
    before = len(d["entries"])
    scope = tuple(sorted(_scope_list(a.scope)))

    def target(x: dict) -> bool:
        if x["id"] != slug(a.term) and norm(x["term"]) != norm(a.term):
            return False
        return a.scope is None or _scope_key(x) == scope

    d["entries"] = [x for x in d["entries"] if not target(x)]
    if len(d["entries"]) == before:
        sys.exit(f"'{a.term}'{' for ' + a.scope if a.scope else ''} is not in {p}")
    save_user(d, lang)
    print(f"removed {before - len(d['entries'])} entry/entries '{a.term}' from {p}")


def cmd_list(a) -> None:
    tiers = load_tiers(base_lang(a.lang))
    for d in tiers:
        if a.tier and d.get("tier") != a.tier:
            continue
        print(f"## {d.get('name')} · {d.get('tier')} · version {d.get('version')} · {len(d.get('entries', []))} entries · {d['_path']}")
        for e in sorted(d.get("entries", []), key=lambda x: norm(x["term"])):
            first = e["easy"].split("\n")[0]
            sc = f" (scope {', '.join(e['scope'])})" if e.get("scope") else ""
            print(f"- {e['term']}{sc} [{e.get('status', 'draft')}]: {first}")
        if d.get("exclusions"):
            print(f"  personal exclusions: {len(d['exclusions'])} (dictionary.py exclusions)")
        print()


def cmd_export(a) -> None:
    lang = base_lang(a.lang)
    tiers = load_tiers(lang)
    if a.tier:
        tiers = [d for d in tiers if d.get("tier") == a.tier]
    chosen: dict[str, dict] = {}
    if a.from_text:
        md = read_text(a.from_text)
        decs = load_decisions(decisions_path(a.from_text, a.work), a.from_text)["decisions"]
        for h in find_in_text(md, tiers, job_scopes(md, a.scope)):
            v = verdict_for(h, decs)
            if v and v.get("verdict") in ("not-explained", "wrong-match", "other-sense"):
                print(f"skipped '{h['term']}': verdict {v['verdict']}", file=sys.stderr)
                continue
            chosen[h["id"]] = h["tiers"][0]["entry"]
    elif a.terms:
        for t in a.terms.split(","):
            res = find_term(t.strip(), tiers)
            if res:
                chosen[res[0][2]["id"]] = res[0][2]
            else:
                print(f"warning: no entry for '{t.strip()}'", file=sys.stderr)
    else:
        for d in tiers:  # user first, so the user's wording wins
            for e in d.get("entries", []):
                chosen.setdefault(e["id"], e)
    entries = sorted(chosen.values(), key=lambda e: norm(e["term"]))
    if a.format == "json":
        out = json.dumps(entries, ensure_ascii=False, indent=2) + "\n"
    else:
        out = glossary_md(entries, a.format)
    if a.out:
        write_text(a.out, out)
        print(f"{len(entries)} entries -> {a.out}")
    else:
        sys.stdout.write(out)


def cmd_update(a) -> None:
    print(update(force=a.force))


def cmd_promote(a) -> None:
    lang = base_lang(a.lang)
    p = user_path(lang)
    d = _load(p) if p.exists() else None
    if not d:
        sys.exit(f"no user dictionary at {p}")
    hits = [e for e in d["entries"] if e["id"] == slug(a.term) or norm(e["term"]) == norm(a.term)]
    if not hits:
        sys.exit(f"'{a.term}' is not in {p}")
    e = dict(hits[0])
    e["status"] = "draft"
    e.setdefault("origin", "human")
    who = os.environ.get("ETR_CONTRIBUTOR")
    if not who and shutil.which("git"):
        r = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True)
        who = r.stdout.strip() or None
    if who:
        e["contributor"] = who
    src = sources()
    body = ("Návrh nového slova do slovníka.\n\n```json\n" + json.dumps(e, ensure_ascii=False, indent=2) + "\n```\n\n"
            "Zdroj vysvetlenia: " + (e.get("source", {}).get("url") or e.get("source", {}).get("name") or "vlastný text") + "\n")
    print(body)
    if a.issue:
        gh = shutil.which("gh")
        if not gh:
            sys.exit("gh (GitHub CLI) is not installed; paste the JSON above into a new issue at https://github.com/" + src["repo"] + "/issues/new")
        tmp = cache_dir() / "promote-body.md"
        write_text(tmp, body)
        r = subprocess.run([gh, "issue", "create", "--repo", src["repo"], "--title", f"Návrh slova: {e['term']}",
                            "--body-file", str(tmp), "--label", "návrh slova"], capture_output=True, text=True)
        if r.returncode != 0 and "not found" in (r.stderr or "").lower():
            r = subprocess.run([gh, "issue", "create", "--repo", src["repo"], "--title", f"Návrh slova: {e['term']}",
                                "--body-file", str(tmp)], capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr.strip())


def cmd_status(a) -> None:
    lang = base_lang(a.lang)
    src = sources()
    print(f"skill:      {SKILL}")
    print(f"shipped:    {SHIPPED}")
    print(f"cache:      {cached_dir()}")
    print(f"user file:  {user_path(lang)} ({'exists' if user_path(lang).exists() else 'not created yet'})")
    print(f"repository: https://github.com/{src['repo']} (branch {src['branch']}, checked every {src.get('check_interval_hours', 24)} h)")
    state_p = cached_dir() / "state.json"
    if state_p.exists():
        st = json.loads(read_text(state_p))
        print(f"last check: {st.get('checked')} · manifest version {st.get('manifest_version')}")
    print()
    for d in load_tiers(lang):
        lic = (d.get("licence") or {}).get("name", "")
        print(f"- {d.get('tier'):6s} {Path(d['_path']).name:28s} version {d.get('version')}  {len(d.get('entries', [])):4d} entries  {lic}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("lookup", help="terms in an easy text that a dictionary explains, with their sentences")
    s.add_argument("easy")
    s.add_argument("--lang")
    s.add_argument("--json")
    s.add_argument("--scope", action="append", help="body or topic of the text, besides the source address (repeatable)")
    s.add_argument("--work", help="work folder with dictionary-decisions.json (default: work next to the text)")
    s.add_argument("--verbose", action="store_true", help="also print the update check result")
    s.set_defaults(fn=cmd_lookup)

    s = sub.add_parser("decide", help="record whether a dictionary hit fits this text")
    s.add_argument("term", help="the dictionary term (or the word as it stands in the text)")
    s.add_argument("verdict", choices=list(VERDICTS))
    s.add_argument("--text", required=True, help="the easy-to-read Markdown file")
    s.add_argument("--form", help="for wrong-match: the word in the text that is not the term")
    s.add_argument("--line", type=int, help="the line the verdict is about, when it matters")
    s.add_argument("--reason", help="why; required for not-explained, wrong-match and other-sense")
    s.add_argument("--scope", action="append")
    s.add_argument("--work")
    s.add_argument("--no-exclude", action="store_true", help="wrong-match without saving a personal exclusion")
    s.add_argument("--lang")
    s.set_defaults(fn=cmd_decide)

    s = sub.add_parser("verdicts", help="every hit in a text with its verdict")
    s.add_argument("--text", required=True)
    s.add_argument("--markdown", action="store_true", help="the table for the companion report (Slovak headings)")
    s.add_argument("--scope", action="append")
    s.add_argument("--work")
    s.add_argument("--lang")
    s.set_defaults(fn=cmd_verdicts)

    s = sub.add_parser("exclusions", help="your personal exclusions; propose them to the shared repository")
    s.add_argument("--proposal", action="store_true", help="draft the note for the shared repository (a global change)")
    s.add_argument("--issue", action="store_true", help="open a GitHub issue with the proposal (gh)")
    s.add_argument("--remove", metavar="FORM", help="delete a personal exclusion")
    s.add_argument("--term", help="with --remove: only for this term")
    s.add_argument("--lang")
    s.set_defaults(fn=cmd_exclusions)

    s = sub.add_parser("find", help="search all tiers for a term")
    s.add_argument("term")
    s.add_argument("--lang")
    s.set_defaults(fn=cmd_find)

    s = sub.add_parser("add", help="add a term to your own dictionary")
    s.add_argument("term")
    s.add_argument("--easy", required=True, help="the explanation, one sentence per line (\\n allowed)")
    s.add_argument("--forms", help="comma-separated other forms")
    s.add_argument("--example")
    s.add_argument("--domain")
    s.add_argument("--source", help="URL or name of where the explanation comes from")
    s.add_argument("--note")
    s.add_argument("--scope", help="comma-separated bodies or topics this explanation is meant for (e.g. minv.sk)")
    s.add_argument("--lang")
    s.add_argument("--replace", action="store_true")
    s.set_defaults(fn=cmd_add)

    s = sub.add_parser("remove", help="remove a term from your own dictionary")
    s.add_argument("term")
    s.add_argument("--scope", help="only the entry with exactly this scope ('' for the general one)")
    s.add_argument("--lang")
    s.set_defaults(fn=cmd_remove)

    s = sub.add_parser("list", help="list the dictionaries and their terms")
    s.add_argument("--tier", choices=["user", "public", "global"])
    s.add_argument("--lang")
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("export", help="a glossary in Markdown (skill convention or pandoc definition list) or JSON")
    s.add_argument("--tier", choices=["user", "public", "global"])
    s.add_argument("--format", choices=["glossary", "dl", "json"], default="glossary")
    s.add_argument("--terms", help="comma-separated terms to export")
    s.add_argument("--from", dest="from_text", help="export only the terms found in this easy text")
    s.add_argument("--scope", action="append", help="with --from: body or topic of the text")
    s.add_argument("--work", help="with --from: work folder with the verdicts (not-explained, wrong-match and other-sense are left out)")
    s.add_argument("--out")
    s.add_argument("--lang")
    s.set_defaults(fn=cmd_export)

    s = sub.add_parser("update", help="fetch newer public and global dictionaries from the repository")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_update)

    s = sub.add_parser("promote", help="propose one of your own entries to the shared repository")
    s.add_argument("term")
    s.add_argument("--issue", action="store_true", help="open a GitHub issue with gh")
    s.add_argument("--lang")
    s.set_defaults(fn=cmd_promote)

    s = sub.add_parser("status", help="where the files are and what is loaded")
    s.add_argument("--lang")
    s.set_defaults(fn=cmd_status)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
