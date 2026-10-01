# Formats: getting the source in, and the easy text out

The rule is simple: the customer gets the easy text back in the form they gave us the
source. A Word file comes back as a Word file that looks like theirs. A web page comes
back as an HTML fragment in their site's own markup, with a preview page and the
Markdown. A PDF comes back as a tagged, accessible PDF and a Word file to edit it.
Pasted or plain text comes back as Markdown and a Word file. The scripts do
the conversions so that nobody needs to know pandoc.

| Source | What you run | What the customer gets |
|---|---|---|
| a URL or a saved `.html` | `extract.py URL` | `.md`, `.fragment.html` (their tags and classes), `.preview.html` |
| a `.docx` | `extract.py file.docx` | `.md`, `.docx` styled like theirs (their styles, header, footer, page size) |
| pasted text, `.md`, `.txt` | `extract.py file.md` or just write `easy.md` | `.md`, `.docx` (pandoc's plain styles) |
| a PDF with a text layer | `extract.py file.pdf` (ask for the Word file too when they have it: it keeps their styles) | `.md`, `.pdf` (tagged, PDF/UA-1), `.docx` |
| a scanned PDF | text recognition first (Acrobat: Scan & OCR), or the Word file or the page; extract.py stops on a PDF without text | as PDF |
| a `.doc` | open in Word, save as `.docx` | as Word |
| a page behind a login | save the page from the browser as HTML, then `extract.py saved.html` | as web |
| a print leaflet to be typeset by their designer | as text or Word; the report's layout section carries the typesetting rules | `.md`, `.docx` |

Add `--format all` to build.py when the customer wants every format, `--format pdf`
to add a print-ready PDF to any source (a leaflet made from a web page).

## The scripts

All three live in `scripts/` and are run with Python 3.10 or newer from the job folder.
Word conversions need pandoc and PDF output needs typst; `etr_common.ensure_tool()`
uses the copy bundled in `runtime/` (offline distribution), else the one on PATH, else
downloads a portable copy into a local cache on first use (pandoc about 40 MB, typst
about 20 MB, no admin rights). Web sources need three small Python packages and PDF
sources pdfminer.six: `python -m pip install -r scripts/requirements.txt`.

### extract.py: source in

```
python <skill>/scripts/extract.py "https://www.example.sk/page" --work work
python <skill>/scripts/extract.py "Usmernenie.docx" --work work
python <skill>/scripts/extract.py "saved-page.html" --work work --selector "#content"
python <skill>/scripts/extract.py "Letak.pdf" --work work
```

It writes `work/source.md` (the source text as Markdown, the thing to read and to
quote in the source map), `work/structure.json` (source type, title, language, the
page's tag and class map or the Word file's font and size, the reference document), and
keeps the original (`source.docx`, `source.pdf`, `source.html` plus `url.txt`). For a
web page it also writes `source-content.html`, the cleaned main content. Every source
also gets `input.md`: the report's input block, with the URL written out or the file
name, its size, the title, when it was fetched or processed, and which part was used
(for a PDF also the page count, whether it is tagged and its language).

**PDF sources.** The text layer is read with pdfminer.six. Lines at the top or bottom
edge that repeat on at least half of the pages (running heads, feet) and page numbers
are removed; headings come from type size (sizes used three times or more are the
heading levels, a larger rarer size is the title) and from short bold lines; Wingdings
and Dingbats bullets and lines starting with •, –, 1. become list items; a paragraph cut
by the layout mid-sentence is joined again; in Slovak and Czech "l’" "t’" "d’" before a
letter become ľ ť ď (a common font-encoding fault). This is a best guess: check
`source.md` against the PDF. A PDF with almost no text (a scan) stops with a message;
so does a password-protected one; "(cid:..)" in the text means the PDF's fonts carry no
character map and the Word file is needed.

The main content is guessed from `[role=main]`, `article`, `#main-content`, `main` and
the like, after removing navigation, breadcrumbs, side menus, cookie bars, footers and
visually hidden labels. The summary prints which element was picked and the headings
found; if they are the wrong ones (news teasers, a menu), run it again with
`--selector` and the CSS selector of the right container.

### check.py: rules a script can test

```
python <skill>/scripts/check.py easy.md            # language from work/structure.json
python <skill>/scripts/check.py easy.md --lang cs --json check.json
```

Reports sentence length (Slovak and Czech 15 words, English 20), paragraphs over five
sentences, two sentences on one line, percentages, big numbers, Roman numerals,
abbreviations, initials and capitals, special characters, visible web addresses,
footnotes, English ordinals; and as things to consider, long words and possible
passives. It lists every placeholder as an open item. It never edits the text, and it
does not judge tone, order, explanations or pictures: those are the writer's and the
readers'. Run it, fix what is real, keep what is deliberate and say why in the report.

### build.py: package out

```
python <skill>/scripts/build.py --easy lahko-citatelny-text.md --report sprievodna-sprava.md --work work --out out
python <skill>/scripts/build.py --easy easy.md --report report.md --format all
python <skill>/scripts/build.py --easy easy.md --reference "their-template.docx" --format docx
```

From `work/structure.json` it knows the source type and picks the outputs. Slovak and
Czech outputs get a non-breaking space after one-letter words (`--no-nbsp` to skip);
the canonical `.md` is copied untouched. The report always comes out as `.md` and
`.docx`, built with the same reference document as the text so it carries the
customer's look, but without the easy-to-read overrides.

**Word output.** pandoc builds the document on the customer's own file as the reference
(`--reference-doc`), which copies their styles, header, footer, logo, margins and page
size and ignores their text. Then the script enforces on the styles what the standards
require and prints every change: body text at least 14 pt; a sans-serif face (Arial)
wherever the document used a serif one (Times New Roman, Georgia, Cambria, Garamond
and the like); left alignment instead of justified; no first-line indent; no automatic
hyphenation; headings bold, never italic, never in capitals; the document language set.
Each sentence is a line break inside its paragraph (Shift+Enter in Word), paragraphs
are separated by the style's spacing. List the printed changes in the report so the
customer's designer does not restore the template.

**PDF output.** pandoc renders the Markdown to typst markup and typst typesets it:
A4, Arial (or Liberation Sans, Noto Sans) 14 pt, headings bold at 22, 18 and 16 pt,
left aligned, no hyphenation, no first-line indent, every sentence on its own line,
generous paragraph spacing, links underlined, pages numbered "strana 2 z 4" from page
two, widows and orphans avoided. The PDF is tagged (structure tree, reading order,
running footers as artifacts), carries the document title (shown in the title bar)
and language, and typst enforces PDF/UA-1. If conformance fails (in practice, an
image without alternative text added later), build.py still writes the PDF and prints
a WARNING with the reason; the report must then not claim PDF/UA.

**Report input check.** build.py stops before writing anything when the report does
not show, as visible text, the source URL (a Markdown link's target does not count;
`<https://…>` does) or the source file name, and prints the block from `input.md`.

**Web output.** pandoc renders the Markdown to an HTML fragment; the script then puts
the source page's own classes on the same tags (`<p class="govuk-body">`, `<h2
class="govuk-heading-l">`, `<ul class="govuk-list govuk-list--bullet">` and so on,
whatever `extract.py` found), wraps it in `<div lang="sk-simple" class="easy-to-read">`
and writes it as `.fragment.html` for pasting into the CMS. `.preview.html` is the same
fragment inside a plain page with easy-to-read typography, for anyone to open in a
browser. Line breaks between sentences are `<br>` inside the paragraph. The fragment
starts with the `<h1>`; when the CMS prints the page title itself, the editor deletes
that first heading.

## Writing the canonical Markdown

The `.md` is the text the customer keeps and edits; every other format is generated
from it. Its conventions are the easy-to-read rules made visible:

- `# Title` once; `## Section` headings that say what follows; `###` only when a
  section really has parts. No deeper.
- **One sentence per line.** A blank line between paragraphs. Nothing else marks a
  line break: no `<br>`, no trailing spaces, no backslash (build.py treats every line
  inside a paragraph as a line break).
- Lists as `- item` lines, one item per line. Slovak and Czech list items are lower
  case, end with a comma and the last with a full stop, as in the official Czech
  examples; English items start with a capital and have no end punctuation.
- Links as `[words that say where it goes](https://…)`. Never a bare address in the
  text. The standards page is linked wherever Easy-to-Read is mentioned.
- Bold only for a heading-like lead in a glossary entry (`**Referenčná suma**` on its
  own line, the explanation on the next) or to make one important word stand out.
  No italics, no capitals, no underline (underline is for links and the formats add it).
- Numbers as digits; dates in words: `v utorok 13. októbra 2026`, `v úterý 13. října
  2026`, `Tuesday 13 October 2026`.
- Placeholders as `[DOPLNIŤ: čo]`, `[DOPLNIT: co]`, `[ADD: what]`. Also
  `[OVERIŤ: …]` for a fact the writer is not sure of.
- The glossary is the last section, headed `## Ťažké slová` / `## Těžká slova` /
  `## Hard words`, one entry per term in the form above. In the HTML fragment
  `build.py` turns it into a definition list (`<dl class="etr-glossary">`, `<dt>` term,
  `<dd>` explanation); `dictionary.py export --from easy.md` drafts it from the
  dictionaries.
- No tables (a table becomes a list or a short paragraph per row), no footnotes, no
  images in the Markdown; pictures are described in the report's image brief and
  added by the customer in the final format.
- Non-breaking spaces are not typed; build.py inserts them.

## Typesetting rules to hand to the customer

Whatever the format, the person laying the text out keeps these (they come from the
Inclusion Europe standards and the Czech methodology, and the report repeats them):

- Sans-serif type, at least 14 pt in print and 18 px on screen; one typeface; regular
  weight for text, bold for headings; no italics, no words in capitals, no thin or
  condensed cuts, no letter-spacing tricks.
- Left aligned, never justified; no hyphenation; no first-line indents; no columns.
- Every sentence on its own line; a clear space between paragraphs; a line length that
  fits the sentences without wrapping where possible (on screen a measure of about 35
  em; A4 with wide margins; A5 with the type at 14 pt).
- Headings bold, each saying what the part is about; few levels.
- Pictures next to the paragraph they explain, one or two per paragraph, never behind
  text, never as the only link.
- Black or very dark text on a plain light background; colour only where the contrast
  stays high; no text on a pattern or a photo.
- Print: pages numbered "strana 2 z 4" from the second page; the easy-to-read mark on
  the cover or first page; A4 or A5; matte paper that photocopies well.
- Web: little text per screen; a table of contents at the top when the page scrolls; a
  "back to top" link after long sections; no pop-ups, no animation, no autoplay; the
  standard version linked, and the home page one click away.

## The version link on a website

Every public-sector site in the 2026 survey (`government-practice-survey.md`) reaches
its easy content through a plain link to a separate URL; none uses an in-page toggle
that swaps the text, because a toggle has no URL to bookmark or share, confuses
screen-reader users and violates the expectation that content changes only on the
user's request (W3C COGA). The pattern to recommend:

- The easy version is its own page at its own address.
- The standard page carries a link near its title and again in the footer or the
  language menu: "Ľahko čitateľná verzia" (cs "Snadné čtení", en "Easy-to-read
  version"); the easy page carries "Bežná verzia" back. When both are shown as a pair,
  the current one is marked with `aria-current="page"`.
- `<html lang>` on the easy page is `sk-simple` (`cs-simple`, `en-simple`): the IANA
  variant subtag `simple` is valid after any language. Never `sk-easy` or a made-up tag.
- The two pages point at each other with `<link rel="alternate" hreflang="sk">` and
  `hreflang="sk-simple"` when the site can add head elements.
- Label the link with words, not only an icon; if an icon is used it is decorative
  (`alt=""` or `aria-hidden="true"`).

## Troubleshooting

- The summary lists news headlines or a menu: the wrong container was picked; rerun
  extract.py with `--selector` (look at `source.html` for the content wrapper's id or
  class).
- `source.md` has stray `\*\*` or numbers on their own lines: the source's own
  formatting; read past it, it does not enter the easy text.
- The Word output looks nothing like the customer's document: their file was not used
  as the reference (a `.doc`, or the source was pasted text); pass `--reference
  their.docx` if they have any Word file with their template.
- The Word output shows squares instead of letters: their template names a font that is
  not installed on the viewing machine; the customer's machines have it.
- pandoc is missing and the download failed (no network): install pandoc from
  pandoc.org, or copy a release into the cache folder the message names.
- A PDF summary lists "WARNING … (cid:..)" or the headings are nonsense: the PDF's
  text layer is poor; ask for the Word file, or extract a PDF exported from it.
- extract.py stops with "almost no text layer": the PDF is a scan; text recognition
  first, or the Word file.
- The PDF output shows boxes or a different typeface: none of Arial, Liberation Sans,
  Noto Sans, DejaVu Sans is installed; install one of them.
- The page needs JavaScript to show its text: save the rendered page from the browser
  (Ctrl+S, "web page, complete") and extract the saved file.
