# dictionaries/

Shipped snapshots of the shared dictionaries of hard words, read by `scripts/dictionary.py`.

| File | Tier | Licence | Source |
|---|---|---|---|
| `verejna-sprava-sk.json` | public | CC BY-NC-SA 4.0 (provisional) | github.com/athelas64/etr-slovnik, baseline from komisar.sk |
| `hurraki-sk.json` | global | CC BY-SA 3.0 | Slovak adaptation of hurraki.de |
| `inclusion-europe-sk.json` | global | CC BY-NC-SA 4.0 | Slovak translation of the Inclusion Europe easy-to-read dictionary |
| `sources.json` | – | – | which repository `dictionary.py update` polls |

Do not edit these files here: edit them in the repository, then copy them back so the
next offline build ships the current snapshot. Newer copies downloaded by `update` live
in `%LOCALAPPDATA%\easy-to-read\dictionaries\` and win by `version`.

**The user's own dictionary is not in this folder.** It is
`%LOCALAPPDATA%\easy-to-read\user-<lang>.json` (Linux and macOS:
`~/.local/share/easy-to-read/user-<lang>.json`), created by the first
`dictionary.py add`, or the file named by the environment variable `ETR_USER_DICT`.
It lives outside the skill so that reinstalling the skill cannot delete it.

Full description: `references/dictionaries.md`.
