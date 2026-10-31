# easy-to-read

Nástroj (skill pre Claude Code) na tvorbu, prevod a posudzovanie ľahko čitateľných textov
(ľahko čitateľný text, Easy-to-Read, snadné čtení, Leichte Sprache) pre ľudí s mentálnym
znevýhodnením podľa európskych pravidiel Inclusion Europe a českej metodiky Easy to Read.
Postup v desiatich krokoch je v `SKILL.md`; skripty `extract`, `dictionary`, `check` a `build`
v `scripts/` spracúvajú zdroj, hľadajú ťažké slová v trojvrstvovom slovníku, kontrolujú
merateľné pravidlá a zostavujú výstupný balík. Spoločný slovník ťažkých slov je
v repozitári [etr-slovnik](https://github.com/athelas64/etr-slovnik).

A skill for Claude Code that writes, converts and reviews easy-to-read texts for people with
intellectual disabilities, following the Inclusion Europe standards and the Czech Easy to Read
methodology. The ten-step procedure is `SKILL.md`; the scripts in `scripts/` process the source,
look up hard words in a three-tier dictionary, check the measurable rules and build the output
package. The shared dictionary of hard words lives in
[etr-slovnik](https://github.com/athelas64/etr-slovnik).

Výskumný prototyp zverejnený na účel hodnotenia. Licencie: pozri `LICENSE` (vlastné dielo
CC BY-NC-SA 4.0; prevzaté referenčné texty podľa podmienok pôvodcov). / A research prototype
published for evaluation; licences in `LICENSE`.

Citujte / cite as: Regec, M. (2026). *easy-to-read: nástroj na tvorbu ľahko čitateľných textov
s podporou jazykového modelu.* https://github.com/athelas64/easy-to-read
