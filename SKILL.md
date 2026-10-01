---
name: easy-to-read
description: Write, convert or review text in Easy-to-Read (Slovak ľahko čitateľný text, Czech snadné čtení, UK Easy Read, German Leichte Sprache) for people with intellectual disabilities, following the Inclusion Europe "Information for all" standards and the Czech Easy-to-Read methodology, and hand it over as a customer package - the easy text returned in the source's own format (a Word file styled like theirs, an HTML fragment in their site's markup, or a tagged accessible PDF, plus Markdown) and a companion report that states the input (URL or file) and holds the source map, the information the customer still has to add, an image brief, a review guide and the reader-check protocol. Use this whenever the user mentions easy-to-read, easy read, ETR, ľahko čitateľný, ľahká verzia, snadné čtení, zjednodušený text, Leichte Sprache, comprehensibility or zrozumiteľnosť for people with intellectual or cognitive disabilities, or asks to simplify a web page, a PDF, a letter, a leaflet or a form's instructions for seniors or people who struggle with reading, even when they never say "easy-to-read".
---

# Easy-to-Read

Easy-to-Read is information written and laid out so that a person with an intellectual
disability can read and understand it alone: short sentences, one idea each, one
sentence per line, well-known words, hard words explained, pictures next to the text,
large sans-serif type. It is not plain language (which keeps all the information for lay
readers) and not an AI "simplify" rewrite. The European rules were written with people
with intellectual disabilities, and a text may only be called Easy-to-Read after such
readers have checked it. That check is the customer's job; the package makes it possible.

## What the customer gets

1. **The easy text**, in the form the source came in: a Word file that keeps their
   styles, header and footer; an HTML fragment in their site's own tags and classes
   with a preview page; a tagged PDF (PDF/UA) plus a Word file to edit it; and always
   the Markdown.
2. **A companion report** in their language: exactly what was given as input (the
   URL written out, or the file name, and when), what changed and why (the source map),
   the information they must add (never invented), the hard words, an image brief, how
   their expert should review, how to run the reader check, the layout rules for
   whoever publishes it, and what they may claim on the text.

`references/customer-package.md` is the template for both. Read it before writing the
report; skim it before writing the text so the source map is easy to fill.

## Modes and formats

- **Convert** an existing text (a web page, a Word document, a PDF, a letter, a
  form's instructions). The usual job.
- **Write** a new easy-to-read text from a brief. Same procedure from step 2, the source
  map replaced by a short "what this covers" list.
- **Review** a text someone else wrote against the rules, with concrete fixes, using
  `scripts/check.py` and the checklist. The report shrinks to findings and fixes.

The output format follows the input: see the table at the top of
`references/formats.md`. If the text is for a site with its own conventions and a
separate skill for it, that skill says how the page is built; the writing rules below
still apply.

Ask only what changes the text: who the readers are, what they must know or do, the
language, and where it will live. Then work; the report is where open questions go.

## Procedure

`python` below means the skill's own interpreter when it has one:
`<skill>/runtime/python/python.exe` in the offline Windows distribution, which also
carries pandoc and the Python packages. Otherwise the system Python 3.10+.

### 1. Bring the source in

```
python <skill>/scripts/extract.py <URL | file.docx | file.pdf | file.html | file.md> --work work
```

Read `work/source.md` whole, not only the headings: the exceptions and conditions buried
in the third paragraph are what the easy text must decide about. The summary names the
container it picked; if it lists news teasers or a menu, rerun with `--selector`.
`work/structure.json` remembers the source type, the page's class map or the Word
file's styles, so `build.py` can return the same format. `work/input.md` is the input
block for the report (step 9).

A PDF is read from its text layer. Headings and lists in `source.md` are guessed from
type size, weight and bullet glyphs, and running headers, footers and page numbers are
removed; open the PDF itself (the Read tool shows its pages) when the structure matters.
A scan without a text layer stops with a message: ask for the Word file or the web
page, or for the PDF after text recognition; never retype a scan from the images.

### 2. Readers and purpose

Write down, one line each: who reads it (adults with intellectual disabilities first;
seniors, people learning the language and people under stress benefit too), what they
must know or do after reading, and where the text will live. Adults get adult language.
The reader knows little about the subject and nothing about the institution; assume
nothing, explain the office, the form and the word "žiadosť" as if for the first time.

### 3. Select and order

- Keep what the reader needs to understand the point or to act. Cut the rest: legal
  references, history, the institution's internal reasons, rare exceptions.
- Order: what this is, what you do, what you bring, where and when, what happens next,
  what happens if you do nothing. The rule before its exceptions. Everything about one
  topic together. The most important information first, repeated at the end when the
  text is long.
- Rare exceptions do not vanish silently. They become one sentence and a place to ask:
  "Niekedy platia iné pravidlá. Spýtajte sa nás." That sentence needs a real phone
  number or counter; if the source has none, it becomes a placeholder.
- **Never invent facts.** The source rarely says where to phone, what it costs, how long
  it takes or what to bring in the words on the documents. Write `[DOPLNIŤ: telefónne
  číslo]`, `[DOPLNIT: poplatek]`, `[ADD: opening hours]` and log each one in the
  report as a question. A made-up fee or deadline in an easy-to-read text is worse than
  none: the reader will act on it.
- Keep a running source map while you work (source section, easy section, kept /
  shortened / dropped, why). Writing it afterwards from memory loses the reasons.

### 4. Write the sentences

| Rule | Check |
|---|---|
| One idea per sentence | A full stop where the source has a comma or "and" |
| Short sentences | Slovak and Czech: at most 15 words; English: one or two lines |
| Every sentence on a new line | The Markdown convention: one sentence per line, blank line between paragraphs |
| Speak to the reader | "vy", "you"; the organisation is "my", "we" |
| Positive, not negative | "Prineste rodný list", not "Bez rodného listu vám preukaz nevydáme" |
| Active, not passive | "Úrad vám pošle list", not "list vám bude zaslaný" |
| Present tense where possible | |
| Well-known words, the same word for the same thing | No synonyms for variety; the word on the form is the word in the text |
| Explain every hard word where it first occurs | An example from everyday life; explain again later if needed; glossary at the end when there are several |
| No metaphors, idioms or irony | Say what you mean |
| No foreign words, abbreviations or initials | Write them out; if initials must stay (a form's name), explain them |
| Numbers as digits; no percentages, no big numbers, no ordinals, no Roman numerals | "few", "many", "most"; "druhý pilier", not "II. pilier"; dates in words |
| Simple punctuation | No brackets, dashes, slashes, semicolons; no §, &, /, #; no footnotes |
| Clear pronouns | If it is not obvious who "he" or "it" is, repeat the name |
| Paragraphs of at most 5 sentences | One topic per paragraph; space between paragraphs |

### 5. Structure

Headings that say what the section is about, few levels, bold. Bullet lists instead of
lists in a sentence. No tables: a table becomes a list or one short paragraph per row.
Links on words that say where they lead. The layout rules (type, alignment, spacing)
are enforced by `build.py` in Word output and handed to the customer in the report;
you do not format, you write.

### 6. Hard words

Explain a hard word in the sentence where it first appears, with an everyday example.
When the text has several, add the glossary as the last section (`## Ťažké slová`,
`## Těžká slova`, `## Hard words`). The term the reader will meet on the form or at the
counter is the one to keep and explain; a friendlier synonym would leave the reader
unable to match the text to the real form.

Before you write an explanation, ask the dictionaries:

```
python <skill>/scripts/dictionary.py lookup easy.md
```

It lists the words in your text that a dictionary already explains (the user's own
dictionary first, then the shared public-sector dictionary, then the global ones), each
with the sentence it stands in, and the long words nobody has explained yet. The match
is lexical: it finds a word, not its meaning. So read every hit in its sentence and
record a verdict for this text:

```
python <skill>/scripts/dictionary.py decide "<term>" used|rewritten|wrong-match|other-sense --text easy.md --reason "..."
```

- `used`: the dictionary's explanation fits; reuse it (in your own words for a Hurraki
  entry, whose licence would otherwise travel into the customer's text).
- `rewritten`: the right term, but you explain it in your own words for this reader.
- `wrong-match`: the word in the text is not the term at all ("kde práve ste" is not
  "práva"). Name the word with `--form` when several matched. This also saves a personal
  exclusion in the user's dictionary and writes `work/dictionary-proposals.md`, a note
  proposing the same exclusion to the shared repository. A shared exclusion would be a
  global change, and for some bodies the match may still be right, so tell the user about
  the proposal at the end and never submit it unasked.
- `other-sense`: the term is right, but this body uses it in another sense. Write your
  own explanation. With the user's agreement it can be kept for this body only:
  `dictionary.py add "<term>" --easy "..." --scope minv.sk`.

A text's scope is the host of its source address (`source:` in the front matter,
www.minv.sk becomes minv.sk), plus any `scope:` line there or `--scope`. Entries with a
scope are offered only to texts with the same scope; entries without one apply
everywhere. When two entries share a term, decide each by the id the lookup shows. An
entry marked `draft` is a proposal, not a reader-checked text.
`dictionary.py export --from easy.md` drafts the glossary section from the entries found
and leaves out the ones judged `wrong-match` or `other-sense`.
When the user says "zapamätaj si toto vysvetlenie", "pridaj do slovníka" or asks you to
remember a word, save it with `dictionary.py add "<term>" --easy "<sentence>
<sentence>"`;
`dictionary.py promote <term> --issue` proposes it to the shared repository.
`references/dictionaries.md` has the files, the schema and the licences.

### 7. Pictures

Write the image brief even though you cannot supply the pictures: which paragraphs get
one, what it shows, photo or symbol, where it can come from, its alternative text.
`references/images.md` says what helps (the actual entrance, the actual form, an adult
doing the action), what harms (metaphors, clip art, children, clutter) and where
pictures come from with their licences. The customer's own photographs come first.

### 8. Self-check

```
python <skill>/scripts/check.py easy.md --json work/check.json
```

Fix what is real. Keep what is deliberate (an official name that is a Roman numeral, a
term the reader will meet) and say why in the report. A dictionary hit without a verdict
is a warning: go back to step 6 and decide it. Then run the Inclusion Europe
checklist (`references/easy-to-read-checklist-en.md`) by reading: is the main
information easy to find, is each paragraph one topic, are examples used, are hard words
explained every time, is it clear who "he" or "she" is. Read the text aloud in your
head: every sentence in one breath.

### 9. Write the companion report

Follow the section list in `references/customer-package.md`. Section 1 opens with the
input block from `work/input.md`: the type of input, the URL written out in full (as
visible text, not hidden behind link words) or the file name as received, the title,
when it was fetched or processed, and which part was used. `build.py` refuses a report
that does not show the URL or the file name. The source map and the
open questions come from your notes in step 3; the hard-words section carries the verdict
table from `dictionary.py verdicts --text easy.md --markdown`; the image brief from step 7; the review
guide and the reader-check protocol from `references/review-and-validation.md`,
rendered in the customer's language and naming the organisations in their country;
the layout section repeats the Word overrides that `build.py` prints. The report is
ordinary professional prose for the customer's staff, not easy-to-read.

### 10. Build and finish

```
python <skill>/scripts/build.py --easy <text>.md --report <report>.md --work work --out out
```

A PDF source comes back as a tagged PDF (PDF/UA-1, typeset by typst: 14 pt sans-serif,
left aligned, no hyphenation, "strana 2 z 4") plus a Word file to edit; `--format pdf`
adds the PDF to any other source. If build.py warns that the PDF is not PDF/UA
conformant, say so in the report and do not claim PDF/UA.

Copy the work folder into `out/zdroj/`. Then tell the user, in a few lines: where the
package is, which formats it holds, how many open questions the report lists and the
three most important, and that the text may not be labelled easy-to-read before the
reader check. If `work/dictionary-proposals.md` exists, add one line: which shared
entries matched words they are not, that a personal exclusion was saved, and that a
shared exclusion would be a global change the user may propose (`dictionary.py exclusions
--proposal`, or `--issue`) but which some bodies might not want. Do not paste the whole
text into the chat unless asked.

## Language notes

- **Slovak.** "ľahko čitateľný text", "ľahko čitateľná verzia"; not "ľahké čítanie".
  "Vy" form. "ľudia s mentálnym znevýhodnením" unless the customer's organisation uses
  another term (ZPMP's translation of the standards says "ľudia s mentálnym
  postihnutím"); follow the people's own organisation over the customer. A screen
  reader is "čítač obrazovky", never "čítačka". Dates in words: "v utorok 13. októbra
  2026". Non-breaking spaces after one-letter words are added by `build.py`.
- **Czech.** "snadné čtení" (government texts also "Easy to Read", "ETR"); not "lehké
  čtení". The Interior Ministry's numbers: at most 15 words per sentence, 5 sentences
  per paragraph, each essential sentence on its own line, "vy" and "my". The four
  annexes in `references/cz-metodika-easy-to-read-priklady.md` are finished official
  texts; imitate their tone. "odečítač obrazovky" for screen reader.
- **English.** "Easy-to-read" (EU) or "Easy Read" (UK, capitalised). Write out
  contractions (does not, was not); dates "Tuesday 13 October 2026"; no "7th".
- **Any language.** The page or fragment language is the base language with the
  `-simple` variant (`sk-simple`, `cs-simple`, `en-simple`; the IANA subtag `simple`
  has no prefix restriction). Never claim a reader check that did not happen.

## References

- `references/customer-package.md`: files, the text's first paragraph and placeholders,
  the companion report section by section, how to end the conversation.
- `references/formats.md`: input and output formats (web, Word, PDF, text), the three scripts, the canonical
  Markdown conventions, typesetting rules for the customer, the version link on a
  website, troubleshooting.
- `references/images.md`: what to picture, style, sources and licences, alt text, the
  image-brief table, the easy-to-read mark.
- `references/review-and-validation.md`: the expert review, the reader-check protocol,
  the delivery-format checks, the record sheet.
- `references/dictionaries.md`: the three dictionaries of hard words (user, public
  sector, Hurraki), `scripts/dictionary.py`, the entry schema, updates and licences.
- `references/information-for-all-en.md`, `-sk.md`, `-cs.md`: the European standards
  (Inclusion Europe, "Information for all"), machine-converted from the PDFs; the
  numbered rules are authoritative, the layout of the conversion is not.
- `references/easy-to-read-checklist-en.md`: the Inclusion Europe checklist.
- `references/cz-metodika-easy-to-read.md`: the Czech Ministry of the Interior
  methodology (plain language part I, Easy to Read part II with the numeric limits).
- `references/cz-metodika-easy-to-read-priklady.md`: four official Czech example texts.
- `references/government-practice-survey.md`: how public-sector sites in Europe present
  easy-to-read content, verified 2026-09-13, with the link-not-toggle pattern.
- Standards page to link wherever Easy-to-Read is mentioned (the HTML page, never the
  PDFs): https://www.inclusion.eu/european-standards-how-to-use-easy-to-read
- Logo rules: https://easy-to-read.inclusion-europe.eu/european-logo/
