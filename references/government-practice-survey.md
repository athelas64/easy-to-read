# Easy-to-read on public-sector websites: what was verified on 2026-09-13

Every entry was checked on the live site (raw HTML, or the rendered DOM for JavaScript
sites). Use it to justify the switch pattern and the labels; re-verify before quoting a
site in public, sites change.

## The pattern to follow

- A **link to a separate URL**, never a button that swaps content in place. Every public
  site in the survey uses a link; the only in-page toggles are the Slovak Commissioner
  (hand-made, with `aria-pressed`, a class on `<html>`, a persisted choice and a
  `role="status"` announcement, but no URL of its own) and AI modules (Eye-Able on
  bensheim.de, no announcement at all).
- Placement: the header utility bar or the language menu, repeated in the footer; on a
  page that has an easy counterpart, a per-page switch near the title (DIN SPEC 33429
  draft: the sign on every subpage leading straight to the counterpart, and a way back).
- The current version marked with `aria-current="page"`; the other version a link.
- `<html lang>` keeps the base language; the IANA variant `simple` (`sk-simple`) is the
  valid way to say "easy version" (BMAS uses `hreflang="de-simple"`, which is invalid).
- The easy page links the standard page and says it is the easy version.
- Guidance that says "link, not toggle": DIN SPEC 33429 draft 7.2.2 (Germany), BIK
  Leitfaden (a visible link on the start page to a separate section), Selkokeskus (the
  easy section in the language menu), Kela and the German federal sites in practice.

## Sites

| Site | How it is reached | Label | Scope and markup facts |
|---|---|---|---|
| kela.fi (FI) | language menu, after Suomi / Svenska / English | Selkokieli, Lättläst | separate section; the menu marks easy/sign entries "unavailable" for the current page and sends to the hub; `<html lang="fi">`; Selkokeskus mark in the footer |
| hel.fi (Helsinki) | language block "Tietoa muilla kielillä", external link with hidden "(Linkki johtaa ulkoiseen palveluun)" | Selkosuomi | separate site selkokieli.hel.fi |
| suomi.fi, vero.fi (FI) | none | | vero.fi's old easy section returns 404 |
| riksdagen.se (SE) | header utility list, decorative "LL" glyph `alt=""` | Lättläst | separate section |
| forsakringskassan.se, skatteverket.se (SE) | none | | alternative formats on request |
| bundesregierung.de (DE) | meta nav, custom icon `aria-hidden`, repeated in flyout and footer | Leichte Sprache | separate section with the § 4 BITV items |
| bmas.de (DE) | header language switcher: English + Leichte Sprache | Leichte Sprache | `hreflang="de-simple"` (invalid) |
| deutsche-rentenversicherung.de (DE) | meta nav, opens a new window (`title` only) | Leichte Sprache | separate site branch |
| berlin.de (DE) | central section gone (410); a link-cloud entry | Meldungen in Leichter Sprache | departmental sub-sites keep sections |
| sozialministerium.gv.at (AT) | header icon link + menu + footer | Leichter Lesen | separate tree by capito, "LL A2" seal |
| parlament.gv.at (AT) | header accessibility bar | Leichte und einfache Sprache | two levels: Leichte Sprache A2, einfache Sprache B1 |
| europarl.europa.eu | "About Parliament" menu | Easy-to-read | one page per language |
| ombudsman.europa.eu | top utility bar next to text size and contrast; footer | Easy to read | one section, `/easy2read` |
| european-union.europa.eu/easy-read_sk | not linked from the home page | Ľahko čitateľná verzia | Inclusion Europe logo with attribution, hreflang for all languages |
| administracion.gob.es (ES) | content block "El Portal en Lectura Fácil" + footer | Lectura Fácil | 17 HTML pages + PDFs, links Inclusion Europe's dictionary; logo `alt=""` |
| comunidad.madrid (ES) | transparency portal | Lectura fácil | mostly PDFs, one HTML page |
| economie.gouv.fr, culture.gouv.fr, service-public.fr (FR) | ministry section; per-page PDF in "Voir aussi" | Facile à lire et à comprendre (FALC) | FALC logo = the Inclusion Europe logo |
| GOV.UK | separate "Easy read" publication pages | Easy Read | mostly PDFs flagged as not suitable for assistive technology; their research: users missed the links |
| ochrance.cz (CZ) | plain link from the home page block | Co dělá ombudsman? (Snadné čtení) | one page in the accessibility section |
| financnisprava.gov.cz, mzp.gov.cz, archiv.msmt.gov.cz (CZ) | accessibility / about pages | Snadné čtení | one page each; MŽP shows the ETR logo with `alt="Snadné čtení"` |
| mpsv.gov.cz, portal.gov.cz, praha.eu (CZ) | none | | |
| komisar.sk (SK) | accessibility toolbar button | Ľahko čitateľná verzia | in-page toggle, see above; story "Príbeh v jazyku Easy-to-read" |
| slovensko.sk, employment.gov.sk (SK) | none | | MPSVR's horizontal-principles site defines "ľahko čitateľný jazyk" as a reasonable accommodation |
| bensheim.de (DE, town) | header button (Eye-Able) + link to hand-written pages | Einfache Sprache / leichte Sprache | AI rewrite in place, `aria-busy` only |

## Terminology in institutional use

- Slovak: ľahko čitateľný text / jazyk; Ľahko čitateľná verzia; ľahko zrozumiteľné
  informácie. Not "ľahké čítanie".
- Czech: snadné čtení; Easy to read / ETR (government); Verze pro snadné čtení. Not
  "lehké čtení".
- English: Easy-to-read (EU); Easy Read (UK). Not "easy reading".
- German: Leichte Sprache (A2), Leichter Lesen (AT), einfache Sprache (B1, plain).
- Finnish: selkokieli, selkosuomi; Swedish: lättläst; Spanish: lectura fácil; French: FALC.

## Standards and legal hooks (short)

- Inclusion Europe "Information for all" (2009) and the 2020 checklist; logo free with
  the reader check and the attribution sentence.
- Czech Ministry of the Interior methodology (2018): 15 words / 5 sentences, Act
  365/2000 Sb., Decree 64/2008 Sb., Rule 15.
- BITV 2.0 § 4 (DE federal start pages); DIN SPEC 33429:2025 (Leichte Sprache, free);
  DIN 8581-1 and ISO 24495-1 (plain language); UNE 153101:2018 EX (ES).
- WCAG 2.2 SC 3.1.5 (AAA) and technique G86; W3C COGA 4.8.2, 4.5.1, 4.9.1.
- Slovakia: nothing beyond WCAG 2.1 AA (Decree 78/2020); Czechia: Rule 15 above.
- IANA: variant subtag `simple`, no prefix restriction.
