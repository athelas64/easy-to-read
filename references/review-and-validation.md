# Reviewing the text, and checking it with readers

A text becomes Easy-to-Read through three checks, in this order:

1. **The writer's self-check**: `scripts/check.py` plus the Inclusion Europe checklist.
   Done before anything is handed over.
2. **The customer's expert review**: is it true, is it complete enough, does it use the
   words the reader will meet on the form and at the counter?
3. **The reader check**: do people from the target group understand it? Required before
   the text may be called Easy-to-Read and before any logo goes on it.

The companion report carries sections 2 and 3 in the customer's language; this file is
the writer's source for them.

## 2. The expert review: what to look for

Give the customer's subject expert the easy text, the source map from the report, and
these questions. They read as the reader's advocate, not as the author of the original.

**Truth.** Every number, date, fee, deadline, office name, form name, address, phone
number and web address: right, and current on the day of publishing? The easy text will
be believed literally; "about a month" must really be about a month.

**Nothing essential lost.** Go through every "dropped" row of the source map and ask:
can a reader who follows only the easy text end up in trouble, at the wrong counter,
without a document, past a deadline, or paying for nothing? If yes, the information comes
back, in easy style. If the dropped part concerns rare cases only, the easy text says
so: "Niekedy platia iné pravidlá. Spýtajte sa nás."

**Nothing wrong by simplification.** "Everybody can" is not the same as "some people
can". The conditions that decide whether this reader qualifies stay in; exceptions that
change the outcome for a few people are replaced by a pointer to help, never silently
dropped. Watch for absolutes the source never made ("vždy", "nikdy", "všetci").

**The words the reader will meet.** The form says "žiadosť", the counter says
"podateľňa", the letter says "rozhodnutie". The easy text uses those same words,
explained, rather than friendlier synonyms; otherwise the reader cannot match the text
to the real thing. The reviewer confirms the terms match the organisation's own forms and
signage.

**Placeholders.** Every `[DOPLNIŤ: …]` in the text is a question for the reviewer:
answer each one; the writer puts the answer into easy sentences. Nothing is published
with a placeholder left in.

**Links and pointers.** Each link goes where its words say and the target is usable for
this reader (a link that lands on a forty-page PDF is not; say so and find the page or
the phone number instead).

**Tone.** Adult, respectful, direct. No diminutives, no "we know this is hard for you",
no exclamation marks of encouragement.

**What not to do.** Do not put the paragraphs back. Do not add the legal safety clause.
Do not merge sentences or restore the official term because it is "more precise". Do
not swap "peniaze" for "finančné prostriedky". Do not change the layout: type size,
alignment, line breaks and spacing are part of the format, not house style. Send
comments (Word comments, notes with line numbers, an email), not a rewritten text; the
writer folds the comments in and runs the checks again.

## 3. The reader check: the protocol

**Who.** At least one adult with an intellectual disability who reads at least a little
(the Inclusion Europe minimum); two or three is better, because one reader's habits
are not the group's. Not the writer's colleagues, not carers reading on someone's
behalf. People are found through self-advocacy groups and organisations of people with
intellectual disabilities and their families: in Slovakia ZPMP v SR and its local
associations, sheltered workshops and day centres; in Czechia SPMP ČR, Rytmus and
similar; in the United Kingdom Mencap and CHANGE; anywhere, the Inclusion Europe
member list. Readers are experts and are paid like experts.

**Where and with what.** A quiet room, no time pressure, the text in the layout it will
be published in (printed, or on the screen where it will live), with the pictures if
there will be pictures. The person reads alone at their own pace, or with the support
they normally use.

**How.** After reading, open questions only, no leading, no yes-or-no:
"O čom to je?" "Čo máte urobiť?" "Kam máte ísť?" "Čo si máte vziať so sebou?"
"Ktoré slovo bolo ťažké?" "Kde ste sa zastavili?" For instructions, ask the person to
show the steps with the real form or on the real website. Mark every sentence where the
reader slowed down, read twice, skipped or asked. Silence and a nod are not
understanding; only their own words are.

**Fix and repeat.** Rewrite the marked sentences, then test again, with the same reader
or another, until the answers show understanding. Most texts need two rounds.

**Record.** Date, how many readers and how they were found (names only with consent,
roles are enough), who led the session, which sentences changed. The record stays with
the customer; it is the evidence behind the label.

**Then, and only then**, the text may carry the sentence "Tento text prečítali a
skontrolovali ľudia s mentálnym znevýhodnením" with the month and year, and, if the
customer wants it, the European easy-to-read logo with its attribution sentence.

**If no reader check is possible now**, the text stays labelled "napísaný podľa
európskych pravidiel pre ľahko čitateľné texty", says so where it is published, and
the check is planned. Never claim a check that did not happen.

## 4. The delivery format, before publishing

- **Web page**: headings in order and none skipped; the easy version linked from the
  standard page and back, as a link to its own URL, never a script toggle; `lang` set
  (`sk-simple`, `cs-simple`, `en-simple`); link text that says where it goes; text and
  pictures usable at 200 % zoom and on a phone; an automated check (axe or similar) run
  on the page.
- **Word file**: paragraph styles, not hand formatting; alternative text on every
  picture; the document language set; no text boxes; tables only when simple, with a
  header row.
- **PDF**: exported from Word with "document structure tags for accessibility", never
  "print to PDF" and never a scan; reading order and alternative texts checked in
  Acrobat; the file title set.
- **Print**: page numbers "strana 2 z 4" from page two; the mark on the cover; matte
  paper; nothing printed over a picture or a tint.

## Record sheet template

```
Overenie s čitateľmi / Reader check
Text:                      (title, version, date)
Dátum overenia / Date:
Čitatelia / Readers:       (number; how recruited; roles, names only with consent)
Viedol / Led by:
Otázky / Questions asked:  O čom to je? Čo máte urobiť? Kam máte ísť? Čo si máte vziať? Ktoré slovo bolo ťažké?
Miesta, kde čitatelia váhali / Where readers hesitated:
    riadok / line …: …
Čo sme zmenili / What we changed:
Ďalšie kolo / Next round:  (date, or "not needed: readers retold the text correctly")
Výsledok / Result:         text môže niesť označenie ľahko čitateľný text: áno / nie
```
