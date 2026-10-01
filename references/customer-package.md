# The customer package: what is handed over, and the companion report

The customer receives two things: the easy-to-read text in the format they gave us the
source in, and a companion report in their own language that tells them what was done,
what they still have to supply, which pictures to commission, how to review the text and
how to have it checked by readers. The report is the part that makes the text usable
without the writer in the room. Most of this file is the report's template.

## Files

```
<slug>-lahko-citatelna-verzia/          sk   (cs: <slug>-snadne-cteni/   en: <slug>-easy-read/)
  lahko-citatelny-text.md               the canonical text, always (cs: snadne-cteni.md, en: easy-read.md)
  lahko-citatelny-text.docx             when the source was a Word file (or on request)
  lahko-citatelny-text.fragment.html    when the source was a web page: paste into the CMS
  lahko-citatelny-text.preview.html     open in a browser to see the text as a page
  lahko-citatelny-text.pdf              when the source was a PDF (or on request): tagged, PDF/UA-1
  sprievodna-sprava.md + .docx          the companion report (cs: pruvodni-zprava, en: companion-report)
  zdroj/                                the source as received and source.md (copy of the work folder)
```

`scripts/build.py` writes the text files and the report from the Markdown files and the work folder;
copy the work folder to `zdroj/` by hand. Name the Markdown files in the customer's
language and build.py keeps the names.

## The text file

Front matter is optional; when present it holds only `title`, `lang` (`sk-simple`,
`cs-simple`, `en-simple`), `source` and `date`. The body follows the conventions in
`formats.md`: one sentence per line, a blank line between paragraphs, `#` and `##`
headings, `-` lists, `[words](url)` links, placeholders as `[DOPLNIŤ: …]`.

The first paragraph says what the reader is looking at, in easy language, and links the
standards page. Slovak wording that has been used:

```
Toto je ľahko čitateľná verzia stránky.
Text je napísaný podľa [európskych pravidiel pre ľahko čitateľné texty](https://www.inclusion.eu/european-standards-how-to-use-easy-to-read).
Bežná verzia stránky má viac podrobností.
```

(Czech: "Toto je verze pro snadné čtení. Text je napsaný podle evropských pravidel pro
snadné čtení. Běžná verze má více podrobností." English: "This is the easy-to-read
version. It follows the European easy-to-read standards. The standard version has more
detail.") The last line becomes a link once the standard page's address is known.

Placeholders stand for facts the writer does not have: `[DOPLNIŤ: telefónne číslo]`,
`[DOPLNIT: adresa úřadu]`, `[ADD: opening hours]`. Never invent a phone number, a fee, a
deadline, an address or an office name to make a sentence complete; the placeholder is
the honest sentence, and check.py lists every one so none is forgotten.

## The companion report

Written in the customer's language, in ordinary professional prose (it is for the
customer's staff, not for the easy-to-read readers). Headings below are given in Slovak,
Czech and English; use one set. Keep each section short; the tables carry the detail.

### 1. O tomto balíku · O tomto balíčku · About this package

**It opens with the input block, and the block is mandatory.** The reader of the
report must see exactly what was converted, without opening anything:

- the type of input (web page, saved web page, Word document, PDF, text),
- **the URL written out in full** as visible text, not hidden behind link words
  (`<https://www.example.sk/stranka>`); for a file, the file name as received and its
  size; for a saved page, also the address the page states as its own,
- the title of the page or document,
- when it was fetched (web) or processed (file), date and time,
- which part was used: the page's main content without navigation and linked pages,
  the whole Word text without header and footer, all PDF pages without running heads
  and images; for a PDF also the page count, whether it is tagged, its language.

`extract.py` writes this block to `work/input.md` in the text's language; paste it and
correct it if the work changed (a second source, a `--selector`). `build.py` refuses a
report that does not show the URL or the file name. When the text draws on more than
one source, list every one in the block.

Then four or five lines: what was delivered (files and formats), the language, and the
status line:

> Text je napísaný podľa európskych pravidiel pre ľahko čitateľné texty (Inclusion
> Europe, „Informácie pre všetkých") a českej metodiky Easy to Read. Čitatelia s
> mentálnym znevýhodnením ho zatiaľ neoverili; kým sa tak nestane, text sa nesmie
> označiť ako ľahko čitateľný ani niesť európske logo.

### 2. Pre koho a načo · Pro koho a k čemu · Readers and purpose

Three lines: who reads it (adults with intellectual disabilities as the primary group,
and who else benefits: seniors, people learning the language, people in a stressful
situation), what they must know or do after reading, and where the text will live
(a page on the site next to the standard one, a leaflet at the counter, an insert in
the letter).

### 3. Čo sme zmenili · Co jsme změnili · What changed

The source map. One row per section or paragraph of the source, in source order, so
the expert can see at a glance what was kept, shortened, moved or dropped and why.
Dropped rows are the ones the expert must sign off.

| Zdroj (časť) | Ľahko čitateľný text (časť) | Čo sa stalo | Prečo |
|---|---|---|---|
| Doklady k žiadosti: rodný list, doklad o rodnom čísle, výpis z osobitnej matriky | Čo si vziať so sebou | zachované, skrátené | výpis z osobitnej matriky presunutý do vety „Ak ste sa narodili v zahraničí, spýtajte sa nás" |
| Zápis titulu: zákon 131/2002, zmluva SR–ČR z 28. 3. 2015 | Ak chcete v preukaze titul | skrátené na jednu podmienku | právne odkazy čitateľ nepotrebuje na to, aby priniesol správny doklad |
| Doklady sa nevyžadujú, ak je údaj v informačnom systéme | – | vynechané | čitateľ nevie, čo je v systéme; bezpečnejšie je priniesť doklad |

Below the table, one sentence on the order of the easy text if it differs from the
source ("the reader's steps come first, the conditions after").

### 4. Čo treba doplniť · Co je třeba doplnit · Information to add

The reader needs some things the source never says because the source assumed them.
List every gap as a question, say why the reader needs it, and quote the placeholder in
the text that waits for the answer. The usual gaps:

- **Contact and help**: who to ask, a phone number, an email, a counter; "Ak niečomu
  nerozumiete, zavolajte nám" needs a number.
- **Place and time**: the address as people say it, the entrance, opening hours, how
  long the visit takes.
- **Cost**: the fee in euros, where and how to pay, whether cash is accepted.
- **Deadline and duration**: by when, and how long until the result comes.
- **What to bring**: the exact documents, in the words on the documents.
- **What happens next**: how the reader learns the result (a letter, a text message,
  a call), what the letter looks like.
- **What happens if the reader does nothing** (the Czech rule): the consequence, in one
  sentence, without threat.
- **Ways to do it**: in person, online, by post; if online needs an eID and a signature,
  say so, and give the in-person way as the default.
- **Who this is for**: which groups the source's exceptions concern, so the text can say
  "Niekedy platia iné pravidlá. Spýtajte sa nás." with a real place to ask.

Format:

| Otázka pre vás | Prečo to čitateľ potrebuje | Kde v texte |
|---|---|---|
| Aké je telefónne číslo, na ktoré má čitateľ zavolať, keď niečomu nerozumie? | Ľahko čitateľný text má vždy povedať, kde je pomoc. | [DOPLNIŤ: telefónne číslo], časť „Kde vám pomôžu" |
| Koľko stojí vydanie preukazu a kde sa platí? | Poplatok je pre čitateľa dôležitý údaj; zdroj ho neuvádza. | [DOPLNIŤ: poplatok], časť „Koľko to stojí" |

### 5. Ťažké slová · Těžká slova · Hard words

The glossary as it stands in the text, plus a note on the terms the expert should
confirm: the words that appear on the form, the letter, the door sign. If the customer
prefers another term for something, it must be the term the reader will meet, not the
nicer one. Say which explanations follow the shared public-sector dictionary (so the
customer knows other offices explain the word the same way) and which are new; a new
explanation the customer approves can go back into the dictionary
(`dictionary.py add`, then `promote`).

Then the verdict table: paste the output of `dictionary.py verdicts --text <text>.md
--markdown` with one sentence before it saying that the dictionary finds words, not
meanings, so every word it found was read in its sentence and judged. The table shows the
word, its lines, the dictionary, the verdict (použité, prepísané, nevysvetľujeme,
nesúvisí, iný význam) and the reason. A word judged "iný význam" is explained in the
text in the sense this office uses; ask the expert to confirm that sense. For words
judged "nevysvetľujeme", ask the expert to confirm the reader needs no explanation, and
add them to the questions of the reader check. Do not put the proposal for the shared
dictionary here: it concerns the dictionary's maintainers, not the customer.

### 6. Obrázky · Obrázky · Pictures

The image brief from `images.md`: the style line, the number of pictures, who supplies
what by when, the table (section, what it shows, type, source suggestion, alt text,
notes), the picture dictionary, and the sentence that the text works without pictures so
they never delay publishing.

### 7. Ako text skontrolovať · Jak text zkontrolovat · How to review the text

The expert-review guidance from `review-and-validation.md`, section 2, in the customer's
language: what to look for (truth, nothing essential lost, nothing wrong by
simplification, the words the reader will meet, placeholders, links, tone) and what not
to do (no details back, no legal clause, no merged sentences, no layout changes; send
comments, not a rewrite).

### 8. Overenie s čitateľmi · Ověření se čtenáři · Reader check

The protocol from `review-and-validation.md`, section 3: who (at least one adult with
an intellectual disability, better two or three; where to find them; paid), the setting,
the open questions, what to note, fix and repeat, the record, and what may be claimed
after it. Include the record sheet. Name the organisations that fit the customer's
country and region.

### 9. Úprava a zverejnenie · Úprava a zveřejnění · Layout and publishing

What the customer's designer, web editor or clerk must keep, per format (from
`formats.md`):

- **Every format**: sans-serif type at 14 pt or larger (screen: at least 18 px), one
  typeface, left aligned, no justification, no hyphenation, no first-line indent, every
  sentence on its own line, space between paragraphs, headings bold, no italics, no
  words in capitals, underline only links, pictures next to their paragraph, nothing
  printed or drawn behind text.
- **Word file**: the styles are already set this way; edit the text, not the formatting;
  add pictures with alternative text; keep the document language.
- **Web page**: paste the fragment into the content area; the page gets its own URL; the
  standard page links to it with the label "Ľahko čitateľná verzia" (cs "Snadné
  čtení", en "Easy-to-read version") as a link, not a script toggle, near the title and
  again in the footer or the language menu; the easy page links back; `lang` on the
  page (or on the fragment's wrapper) is `sk-simple`; the site's stylesheet may need a
  rule for `.easy-to-read` (larger type, wider line spacing, narrower measure).
- **PDF**: the delivered PDF is tagged and PDF/UA-1 conformant (unless build.py warned
  otherwise); if it is edited, edit the Word file and export again with document
  structure tags (Word: Save as PDF, Options, "Document structure tags for
  accessibility"), then check it in Acrobat (Accessibility Checker) or PAC; page
  numbers "strana 2 z 4"; the mark on the first page after the reader check; never a
  scan.
- **Print**: A4 or A5, wide margins, matte paper; the mark on the cover.

List here the Word overrides build.py printed (font, size, alignment, indent,
hyphenation), so the customer knows why the easy version looks different from their
template and does not "fix" it back.

### 10. Označenie · Označení · Labelling

What the customer may say now and later:

- Now: "Text je napísaný podľa európskych pravidiel pre ľahko čitateľné texty" with the
  link to the standards page (the HTML page, never the PDFs).
- After the reader check: "Text prečítali a skontrolovali ľudia s mentálnym
  znevýhodnením (mesiac rok)". Only then the European easy-to-read logo, with the
  attribution "© European Easy-to-Read Logo: Inclusion Europe. More information at
  www.easy-to-read.eu", the logo in its colour (#333399) and at least 15 mm wide. The
  logo is free and needs no application; Inclusion Europe may withdraw it.
- Never: "easy-to-read" as a marketing word for a text that was not checked, or a claim
  that an AI "simplify" feature produces easy-to-read text.

### 11. Výsledok kontroly · Výsledek kontroly · Check results

The output of `scripts/check.py` in short: the statistics line, the open items, the
findings that were left on purpose with the reason (a term the reader will meet, an
official name that is a Roman numeral in the source), and the Inclusion Europe
checklist items that needed judgement.

## Ending the conversation with the user

After the files are written, tell the user in a few lines: where the package is, which
formats it contains, how many open questions the report holds and the three most
important ones, and that the text is not to be labelled easy-to-read before the reader
check. Do not paste the whole text into the chat unless asked.
