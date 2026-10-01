"""Shared helpers for the easy-to-read scripts: pandoc and typst lookup, non-breaking
spaces, language codes, small file utilities.

Standard library only, so a Word-only job runs on a plain Python 3.10+ install.
Web-page jobs additionally need beautifulsoup4, lxml and markdownify, PDF sources
pdfminer.six (requirements.txt); extract.py and build.py import those lazily, only
when they are really needed.
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

PANDOC_VERSION = "3.10"
TYPST_VERSION = "0.15.1"

# One-letter prepositions and conjunctions that Slovak and Czech typography never
# leave at the end of a line (a, i, k, o, s, u, v, z and their capitals).
_NBSP_RE = re.compile(r"(?<![\wÀ-ſ])([aiouvzskAIOUVZSK]) (?=\S)")

# Word language tags for the document language (spell-check, hyphenation dictionary).
WORD_LANG = {"sk": "sk-SK", "cs": "cs-CZ", "en": "en-GB", "de": "de-DE", "pl": "pl-PL", "hu": "hu-HU"}


def nbsp(text: str) -> str:
    """Put a non-breaking space after one-letter prepositions and conjunctions (sk, cs)."""
    return _NBSP_RE.sub(lambda m: m.group(1) + " ", text)


def base_lang(lang: str | None) -> str:
    """'sk-simple' -> 'sk'; None -> 'sk'."""
    return (lang or "sk").split("-")[0].lower()


def simple_lang(lang: str | None) -> str:
    """'sk' -> 'sk-simple'. The IANA variant subtag 'simple' is valid after any language."""
    return f"{base_lang(lang)}-simple"


def cache_dir() -> Path:
    if platform.system() == "Windows":
        root = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    d = root / "easy-to-read"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------- external tools
def _exe(name: str) -> str:
    return f"{name}.exe" if platform.system() == "Windows" else name


def _release_asset(tool: str) -> tuple[str, str]:
    """(download URL, archive kind) of the official release for this machine."""
    system, machine = platform.system(), platform.machine().lower()
    arm = machine in ("arm64", "aarch64")
    if tool == "pandoc":
        v = PANDOC_VERSION
        if system == "Windows":
            asset = f"pandoc-{v}-windows-x86_64.zip"
        elif system == "Darwin":
            asset = f"pandoc-{v}-{'arm64' if arm else 'x86_64'}-macOS.zip"
        else:
            asset = f"pandoc-{v}-linux-{'arm64' if arm else 'amd64'}.tar.gz"
        return f"https://github.com/jgm/pandoc/releases/download/{v}/{asset}", asset
    v = TYPST_VERSION
    if system == "Windows":
        asset = f"typst-{'aarch64' if arm else 'x86_64'}-pc-windows-msvc.zip"
    elif system == "Darwin":
        asset = f"typst-{'aarch64' if arm else 'x86_64'}-apple-darwin.tar.xz"
    else:
        asset = f"typst-{'aarch64' if arm else 'x86_64'}-unknown-linux-musl.tar.xz"
    return f"https://github.com/typst/typst/releases/download/v{v}/{asset}", asset


def _find_in(d: Path, exe: str) -> Path | None:
    if not d.exists():
        return None
    hits = [p for p in d.rglob(exe) if p.is_file()]
    return hits[0] if hits else None


def _missing(tool: str) -> None:
    hint = {
        "pandoc": "Install it from https://pandoc.org/installing.html (Windows: `choco install pandoc` "
                  "or the .msi; macOS: `brew install pandoc`; Linux: the distribution package)",
        "typst": "Install it from https://github.com/typst/typst/releases (Windows: `winget install "
                 "--id Typst.Typst`; macOS: `brew install typst`)",
    }[tool]
    print(f"{tool} is required. {hint}, or unpack a release into {cache_dir() / tool}", file=sys.stderr)
    sys.exit(2)


def ensure_tool(tool: str, auto_download: bool = True) -> str:
    """Return a path to pandoc or typst: the copy bundled with the skill (runtime/<tool>/),
    then PATH, then a portable copy in the cache dir.

    When nothing is found and auto_download is on, the official release archive (pandoc
    about 40 MB, typst about 20 MB, no admin rights needed) is unpacked into the cache
    dir. A failed download prints the manual hint and exits.
    """
    exe = _exe(tool)
    bundled = Path(__file__).resolve().parent.parent / "runtime" / tool / exe
    if bundled.is_file():
        return str(bundled)
    found = shutil.which(tool)
    if found:
        return found
    target = cache_dir() / tool
    portable = _find_in(target, exe)
    if portable:
        return str(portable)
    if not auto_download:
        _missing(tool)
    url, asset = _release_asset(tool)
    target.mkdir(parents=True, exist_ok=True)
    archive = target / asset
    print(f"{tool} not found; downloading a portable copy into {target} ...", file=sys.stderr)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "easy-to-read-skill"})
        with urllib.request.urlopen(req, timeout=180) as r, open(archive, "wb") as f:
            shutil.copyfileobj(r, f)
        if asset.endswith(".zip"):
            with zipfile.ZipFile(archive) as z:
                z.extractall(target)
        else:
            with tarfile.open(archive) as t:
                t.extractall(target)
        archive.unlink(missing_ok=True)
    except Exception as e:  # noqa: BLE001
        print(f"download failed: {e}", file=sys.stderr)
        _missing(tool)
    portable = _find_in(target, exe)
    if not portable:
        _missing(tool)
    if platform.system() != "Windows":
        portable.chmod(0o755)
    return str(portable)


def ensure_pandoc(auto_download: bool = True) -> str:
    return ensure_tool("pandoc", auto_download)


def ensure_typst(auto_download: bool = True) -> str:
    return ensure_tool("typst", auto_download)


# ---------------------------------------------------------------- small utilities
def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    """Run a command; on failure print its stderr and exit."""
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    if p.returncode != 0:
        print("command failed: " + " ".join(cmd), file=sys.stderr)
        print(p.stderr, file=sys.stderr)
        sys.exit(p.returncode)
    return p


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8", newline="\n")


def strip_front_matter(md: str) -> str:
    """Drop a leading YAML block (--- ... ---) if present."""
    if md.startswith("---"):
        end = md.find("\n---", 3)
        if end != -1:
            return md[end + 4 :].lstrip("\n")
    return md
