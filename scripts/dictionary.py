#!/usr/bin/env python3
"""Dictionaries of hard words for easy-to-read texts: look up, add, export, update.

    python dictionary.py lookup EASY.md [--lang sk] [--json OUT.json]
        words in the text that a dictionary already explains, plus long words without an entry
    python dictionary.py find TERM [--lang sk]          search every tier
    python dictionary.py add TERM --easy "..." [--forms a,b] [--example "..."] [--domain ...]
                            [--source URL] [--note "..."] [--lang sk]
    python dictionary.py remove TERM [--lang sk]
    python dictionary.py list [--tier user|public|global] [--lang sk]
    python dictionary.py export [--tier ...] [--format glossary|dl|json] [--terms a,b | --from EASY.md]
    python dictionary.py update [--force]               fetch newer public and global files
    python dictionary.py promote TERM [--issue]          propose a user entry to the shared repository
    python dictionary.py status

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
        s = re.sub(r"\[([^\]]*)\]\([^)]+\)", r"\1", raw)
        s = re.sub(r"\[(?:DOPLNIŤ|DOPLNIT|DOPLŇTE|ADD|TODO|OVERIŤ|OVĚŘIT|CHECK)[^\]]*\]", "", s, flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = s.lstrip("#>-*+ ").replace("**", "")
        for m in WORD.finditer(s):
            out.append((i, m.group(0)))
    return out


def find_in_text(md: str, tiers: list[dict]) -> list[dict]:
    """Entries whose term or forms occur in the text. One record per entry id, with the
    lines where it occurs and every tier that has it (best tier first)."""
    toks = text_tokens(md)
    words = [t for _, t in toks]
    hits: dict[str, dict] = {}
    for d in tiers:
        tier = d.get("tier", "global")
        for e in d.get("entries", []):
            lines: list[int] = []
            matched_key = None
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
                    if ok:
                        lines.append(toks[i][0])
                        matched_key = matched_key or key
            if not lines:
                continue
            lines = sorted(set(lines))
            rec = hits.setdefault(e["id"], {"id": e["id"], "term": e["term"], "lines": lines, "matched": matched_key, "tiers": []})
            rec["lines"] = sorted(set(rec["lines"]) | set(lines))
            rec["tiers"].append({"tier": tier, "file": Path(d["_path"]).name, "entry": e,
                                 "licence": (d.get("licence") or {}).get("name")})
    for rec in hits.values():
        rec["tiers"].sort(key=lambda t: TIER_ORDER.get(t["tier"], 9))
    return sorted(hits.values(), key=lambda r: (r["lines"][0], r["term"]))


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


def render_lookup(path: str, hits: list[dict], missing: list[tuple[int, str]], tiers: list[dict]) -> str:
    out = [f"# Dictionary lookup: {Path(path).name}", ""]
    names = ", ".join(f"{d.get('tier')} ({Path(d['_path']).name}, {len(d.get('entries', []))} entries)" for d in tiers)
    out.append(f"Dictionaries: {names or 'none'}")
    out.append("")
    out.append(f"## Words the dictionaries explain ({len(hits)})")
    out.append("")
    if not hits:
        out.append("- none")
    for h in hits:
        best = h["tiers"][0]
        e = best["entry"]
        others = ", ".join(t["tier"] for t in h["tiers"][1:])
        lines = ", ".join(str(x) for x in h["lines"][:8]) + (" ..." if len(h["lines"]) > 8 else "")
        status = e.get("status", "draft")
        flag = "" if status != "draft" else " · draft, check before reuse"
        lic = f" · {best['licence']}" if best.get("licence") else ""
        out.append(f"- **{e['term']}** · lines {lines} · {best['tier']}{lic}{flag}" + (f" · also in {others}" if others else ""))
        for ln in e["easy"].split("\n"):
            if ln.strip():
                out.append(f"    {ln}")
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
    out.append("Reuse an explanation only when it fits the reader and the context; a public or global entry is "
               "a starting point, not a reader-checked text. `dictionary.py add` saves your own explanation.")
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


# ---------------------------------------------------------------- commands
def cmd_lookup(a) -> None:
    lang = base_lang(a.lang)
    msg = update(quiet=True)
    if a.verbose:
        print(msg, file=sys.stderr)
    tiers = load_tiers(lang)
    md = read_text(a.easy)
    hits = find_in_text(md, tiers)
    missing = long_words_without_entry(md, hits)
    print(render_lookup(a.easy, hits, missing, tiers))
    if a.json:
        write_text(a.json, json.dumps({
            "lang": lang,
            "dictionaries": [{"tier": d.get("tier"), "file": Path(d["_path"]).name, "version": d.get("version"),
                              "entries": len(d.get("entries", [])), "licence": (d.get("licence") or {}).get("name")} for d in tiers],
            "found": [{"id": h["id"], "term": h["term"], "lines": h["lines"],
                       "tiers": [{"tier": t["tier"], "file": t["file"], "licence": t["licence"], "entry": t["entry"]} for t in h["tiers"]]} for h in hits],
            "long_words_without_entry": [{"line": ln, "word": w} for ln, w in missing],
        }, ensure_ascii=False, indent=2) + "\n")


def cmd_find(a) -> None:
    tiers = load_tiers(base_lang(a.lang))
    res = find_term(a.term, tiers)
    if not res:
        print(f"no entry for '{a.term}'")
        return
    for tier, d, e in res:
        print(f"## {e['term']} · {tier} · {Path(d['_path']).name} · {e.get('status', 'draft')}")
        if e.get("forms"):
            print("forms: " + ", ".join(e["forms"]))
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
    e["status"] = "draft"
    e["origin"] = "human"
    e["added"] = date.today().isoformat()
    existing = [x for x in d["entries"] if x["id"] == e["id"]]
    if existing and not a.replace:
        sys.exit(f"'{a.term}' is already in {p}; use --replace to overwrite it")
    d["entries"] = [x for x in d["entries"] if x["id"] != e["id"]] + [e]
    d["entries"].sort(key=lambda x: norm(x["term"]))
    warn = check_easy(easy)
    saved = save_user(d, lang)
    print(f"added '{e['term']}' to {saved} ({len(d['entries'])} entries)")
    for w in warn:
        print("  note: " + w)


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
    d["entries"] = [x for x in d["entries"] if x["id"] != slug(a.term) and norm(x["term"]) != norm(a.term)]
    if len(d["entries"]) == before:
        sys.exit(f"'{a.term}' is not in {p}")
    save_user(d, lang)
    print(f"removed '{a.term}' from {p}")


def cmd_list(a) -> None:
    tiers = load_tiers(base_lang(a.lang))
    for d in tiers:
        if a.tier and d.get("tier") != a.tier:
            continue
        print(f"## {d.get('name')} · {d.get('tier')} · version {d.get('version')} · {len(d.get('entries', []))} entries · {d['_path']}")
        for e in sorted(d.get("entries", []), key=lambda x: norm(x["term"])):
            first = e["easy"].split("\n")[0]
            print(f"- {e['term']} [{e.get('status', 'draft')}]: {first}")
        print()


def cmd_export(a) -> None:
    lang = base_lang(a.lang)
    tiers = load_tiers(lang)
    if a.tier:
        tiers = [d for d in tiers if d.get("tier") == a.tier]
    chosen: dict[str, dict] = {}
    if a.from_text:
        for h in find_in_text(read_text(a.from_text), tiers):
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

    s = sub.add_parser("lookup", help="terms in an easy text that a dictionary explains")
    s.add_argument("easy")
    s.add_argument("--lang")
    s.add_argument("--json")
    s.add_argument("--verbose", action="store_true", help="also print the update check result")
    s.set_defaults(fn=cmd_lookup)

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
    s.add_argument("--lang")
    s.add_argument("--replace", action="store_true")
    s.set_defaults(fn=cmd_add)

    s = sub.add_parser("remove", help="remove a term from your own dictionary")
    s.add_argument("term")
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
