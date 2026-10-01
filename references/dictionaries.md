# Dictionaries of hard words

Three dictionaries feed step 6 (hard words). `scripts/dictionary.py` reads them in a
fixed order, so a word the user explained once is explained the same way next time,
and a word the public sector already agreed on is explained the way the reader meets it
on other offices' texts.

| Tier | What it is | Who writes it | Licence |
|---|---|---|---|
| `user` | the user's own words, private | the user, or the agent when asked | the user's |
| `public` | the shared public-sector dictionary (`verejna-sprava-sk.json`) | public bodies and experts, through the repository | CC BY-NC-SA 4.0 (provisional, until MIRRI decides) |
| `global` | the Hurraki adaptation (`hurraki-sk.json`) and the Inclusion Europe glossary (`inclusion-europe-sk.json`) | translated, reviewed in the repository | CC BY-SA 3.0 (inherited from Hurraki); CC BY-NC-SA 4.0 (Inclusion Europe translation) |

## Where the files are

Three places are read. The first two hold the shared tiers, the third the user's own.

```
<skill>/dictionaries/                      shipped with the skill (read-only snapshot)
    verejna-sprava-sk.json                 public tier, Slovak
    hurraki-sk.json                        global tier, Slovak
    sources.json                           which repository `update` polls

%LOCALAPPDATA%\easy-to-read\dictionaries\  downloaded updates (Windows)
    verejna-sprava-sk.json                 newer copies of the shipped files, same names
    hurraki-sk.json
    state.json                             when the repository was last checked
    *.bak                                  the previous copy of each replaced file

%LOCALAPPDATA%\easy-to-read\               the user's own dictionaries
    user-sk.json                           user tier, Slovak
    user-cs.json, user-en.json             one file per language, created on first `add`
```

On macOS and Linux the last two folders are `$XDG_DATA_HOME/easy-to-read/`, which
defaults to `~/.local/share/easy-to-read/`. The offline Windows distribution uses the
same `%LOCALAPPDATA%` folders, so the user's words survive when the skill folder is
replaced by a new ZIP (the installer moves the old folder aside).

### How the files are picked up

1. Every `*.json` in the shipped folder and in the downloaded folder is opened, except
   `sources.json`, `manifest.json` and `state.json`. A file counts as a dictionary when
   it has an `entries` list and a `lang` that matches the text's language (`sk` for
   `sk-simple`). Files for other languages are ignored, not merged.
2. When the same file name exists in both folders, the one with the higher `version`
   string wins (versions are dates, `2026-09-29` or `2026-09-29.2`, so text order is
   date order). This is why a fresh skill install with a newer shipped snapshot beats
   an old download, and a fresh download beats the shipped snapshot.
3. The user file for the language is added if it exists.
4. The list is sorted by the `tier` field: `user`, then `public`, then `global`. A term
   found in several tiers is reported with all of them; the first one is the wording to
   prefer.

The language comes from `--lang`, or from `work/structure.json` next to the text when
`check.py` runs, and defaults to `sk`.

### Where to put the user dictionary

Nothing needs to be created by hand: the first `dictionary.py add` writes
`%LOCALAPPDATA%\easy-to-read\user-<lang>.json`. To keep the file somewhere else, for
example in a synced folder or in a project, set the environment variable
`ETR_USER_DICT` to the full path of the file; it then replaces the default for every
language, so use one variable per shell or project, not a global one, when several
languages are in play.

A hand-written user file must follow the schema below with `"tier": "user"` and the
right `"lang"`; a `licence` block is optional for the user tier. `dictionary.py list
--tier user` shows what was picked up, `dictionary.py status` shows the path it looked at.

### Adding an organisation's own dictionary

An office that keeps its own agreed explanations, not yet in the public repository, can
drop a file into the downloaded folder (`%LOCALAPPDATA%\easy-to-read\dictionaries\`)
under a name that is **not** in the repository's manifest, for example
`mesto-trnava-sk.json`, with `"tier": "public"` (or `"user"`). It is loaded like the
others and never overwritten by `update`, which touches only the file names the
manifest lists. The same file can later be proposed to the repository as a whole.

## Updates from the repository

`dictionaries/sources.json` names the repository (`athelas64/etr-slovnik`, branch
`main`) and the check interval (24 hours). `dictionary.py update`:

1. fetches `manifest.json`, first from the raw GitHub address (works once the
   repository is public), then through the GitHub API with a token when the raw
   address answers 404 (private repository). The token comes from `ETR_SLOVNIK_TOKEN`,
   `GITHUB_TOKEN`, `GH_TOKEN`, or from a logged-in `gh` CLI (`gh auth token`);
2. compares each listed file's `sha256` with the local copy (downloaded, else shipped)
   and downloads only the files that differ;
3. verifies the hash and that the file parses, keeps the old copy as `.bak`, and
   replaces the file atomically;
4. records the check in `state.json` with the manifest's ETag, so an unchanged
   repository costs one request that answers 304.

`lookup` runs this check itself, silently, at most once a day; `update --force` runs
it now. Offline, or without a token for a private repository, the local copies are
used and one line says so. The check never blocks or fails a job.

After a dictionary is edited in the repository, copy the file into the skill's
`dictionaries/` as well, so the next offline ZIP ships the current snapshot; the
version comparison makes the two copies interchangeable.

## Commands

```
python <skill>/scripts/dictionary.py lookup easy.md [--json work/dictionary.json]
python <skill>/scripts/dictionary.py find "spôsobilosť na právne úkony"
python <skill>/scripts/dictionary.py add "posudkový lekár" --easy "Posudkový lekár je lekár úradu.\nPozrie sa na správy od vašich lekárov." --forms "posudkoví lekári,posudková lekárka" --domain "sociálne služby" --source https://…
python <skill>/scripts/dictionary.py export --from easy.md                 # glossary in the skill's Markdown form
python <skill>/scripts/dictionary.py export --from easy.md --format dl     # pandoc definition list -> <dl>
python <skill>/scripts/dictionary.py list --tier user
python <skill>/scripts/dictionary.py remove "posudkový lekár"
python <skill>/scripts/dictionary.py promote "posudkový lekár" --issue     # proposes it to the shared repository
python <skill>/scripts/dictionary.py update --force
python <skill>/scripts/dictionary.py status
```

`check.py` adds an info finding for every term a dictionary explains (turn it off with
`--no-dictionary`). Matching works in two ways:

- `term` and `forms` are matched with a light stemmer: one Slovak or Czech inflectional
  ending may differ, so "podnetu" and "podnety" find "podnet" and "na úrade" finds
  "úrad". `forms` therefore holds only inflections and fixed variants of the headword,
  and the repository validator rejects a form that does not share the first four
  letters of a headword word ("zákonný" is not a form of "zákon").
- `same_words` are matched as exact words only, for synonyms and abbreviations
  ("penzia", "ŤZP", "CRPD"). Related or broader words do not belong there: "dieťa"
  under "maloletý" would fire on every child in a text.

When a user entry is added, give it the forms the reader will meet in the text (plural,
the cases that occur, the abbreviation in `same_words`).

## What to do with a hit

- **A user entry** is the user's own wording. Use it as it stands unless the reader or
  the context differs; then say so in the report.
- **A public entry** marked `reviewed` or `reader-checked` is how the public sector
  explains the word; keep the wording so the reader meets the same explanation
  everywhere. `draft` is a proposal: check it against the source text and the reader.
- **A global (Hurraki) entry** was written for German readers and translated by a
  machine (`origin: machine-translated`) until a person reviews it. Use it to
  understand the concept and to see how short it can be said, then write the sentence
  yourself. Do not paste it word for word into a customer text: CC BY-SA would make the
  customer's document a derivative that has to carry the same licence.
- **No hit, long word**: explain it, and if the explanation will be useful again,
  `add` it. The customer's approved wording is the best candidate for `promote`.

When the user says "zapamätaj si toto vysvetlenie", "pridaj do slovníka" or asks the
agent to remember a word, the agent runs `add` with the wording from the text.

## File schema (all tiers)

```json
{
  "name": "Vlastný slovník",
  "tier": "user",
  "lang": "sk",
  "version": "2026-09-29",
  "updated": "2026-09-29",
  "licence": {"name": "CC BY-NC-SA 4.0", "url": "https://creativecommons.org/licenses/by-nc-sa/4.0/", "attribution": "…"},
  "entries": [
    {
      "id": "sposobilost-na-pravne-ukony",
      "term": "spôsobilosť na právne úkony",
      "forms": ["pozbavenie spôsobilosti na právne úkony", "obmedzenie spôsobilosti na právne úkony"],
      "easy": "Niektorým ľuďom súd obmedzí rozhodovanie o vlastných veciach.\nZnamená to, že nemôžu sami podpisovať dôležité zmluvy.",
      "example": "…",
      "same_words": ["…"],
      "domain": "právo",
      "note": "for the writer, not the reader",
      "source": {"name": "…", "url": "…", "title": "…", "revision": 123, "fetched": "2026-09-29", "licence": "…"},
      "status": "draft | reviewed | reader-checked",
      "origin": "human | adapted | machine-translated",
      "added": "2026-09-29",
      "contributor": "…"
    }
  ]
}
```

Required: `name`, `tier`, `lang`, `version`, `entries`; `licence` for the public and
global tiers. In an entry: `id` (ASCII slug, unique in the file), `term`, `easy`.
`easy` follows the writing rules of this skill: one sentence per line, at most 15
words, no brackets, slashes, dashes, semicolons or paragraph signs, no abbreviations.
The repository validates this on every pull request (`scripts/validate.py` there) and
refuses a `machine-translated` entry marked `reviewed`. The full JSON Schema is
`schema/slovnik.schema.json` in the repository.

## Licences, in one place

- Public-sector dictionary: CC BY-NC-SA 4.0, attribution "Slovník ťažkých slov verejnej
  správy, github.com/athelas64/etr-slovnik". Provisional; MIRRI may choose CC0 or
  another licence, and the file's `licence` block is the authority.
- Hurraki adaptation: Hurraki is CC BY-SA 3.0 (DE); the Slovak file is a derivative
  and stays CC BY-SA 3.0, with Hurraki named in its `licence.attribution`. Each entry
  keeps the source article URL and revision.
- Inclusion Europe glossary: the English source is © Inclusion Europe (an EU-funded
  organisation, cited at every entry); the Slovak machine translation is CC BY-NC-SA 4.0.
  The repository is a research project published for evaluation; takedown contact
  milan.regec@uniba.sk.
- The user file carries no licence unless the user adds one; `promote` submits an
  entry under the licence of the target file, and the issue form asks for consent.
- The offline installer copies `dictionaries/` and names both licences in
  `LICENSES/NOTICES.txt`.
