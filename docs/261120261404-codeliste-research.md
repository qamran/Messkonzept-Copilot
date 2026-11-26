# Codeliste research: BDEW Lokationsbündelstrukturen

**Ticket:** MKC-12.1 (#117), part of MKC-12 (#12). **Researched:** 26.11.2026.

This note records where the repo's LBS reference data (`backend/data/lbs_structures.yaml`) comes from, and what we may and may not commit.

## Version

- **Document:** "Codeliste der Lokationsbündelstrukturen", author BDEW (edi@energy).
- **Edition used:** version 1.0, "Konsolidierte Lesefassung mit Fehlerkorrekturen", Stand 13.12.2024. First published 31.03.2023, applicable from 01.10.2024. 52 pages.
- **Why this edition is current (26.11.2026):**
  - The BDEW MaKo platform's document list (`https://bdew-mako.de/api/documents`) has it as entry 7713, valid from 13.12.2024 with no end date. Every older edition there has an end date.
  - Mitteilung Nr. 56 of the Bundesnetzagentur (01.04.2026) lists new code lists for 01.10.2026. This one is not among them.
  - Mitteilung Nr. 58 (01.10.2026) publishes no new code lists or decision trees.
- **Edition history (what changed the codes):**
  - Consultation draft, Stand 01.08.2022 (Mitteilung Nr. 32): 16 structures, including `9992 00000 009 2` "Verbrauch mit hinterschalteter Hinterschaltung".
  - Final 1.0, 31.03.2023 (Mitteilung Nr. 33): 15 structures. `009 2` dropped. "Pooling" renamed to "Summenmessung", "dynamisch" to "flexibel".
  - Corrected editions of 12.12.2023, 23.09.2024 and 13.12.2024: changes to text, footnotes and reference columns. The codes stay the same. The change history is in section 5 of the document.
- **What the Codeliste says about itself:** it shows the most common structures. A grid area need not use all of them, and structures outside the list are agreed bilaterally. Structures are exchanged in UTILMD.

## Source

- **Corrected edition (used):** <https://bdew-mako.de/pdf/Codeliste-Lokationsbu%CC%88ndelstrukturen_1_0_Fehlerkorrektur_20241213.pdf>
  - sha256 `0ae47f79bb719c48920fed9019657eec84659a7f7edbc11805444499dc11ac96`
- **BDEW MaKo platform:** <https://bdew-mako.de/> (the document list is the JSON at `/api/documents`; the site itself needs JavaScript)
- **Final 1.0 of 31.03.2023 (Mitteilung Nr. 33):** <https://data.bundesnetzagentur.de/Bundesnetzagentur/DE/Beschlusskammern/BK06/BK6_83_Zug_Mess/835_mitteilungen_datenformate/Mitteilung_33/Anlagen/codelistelokationsbuendelstrukturen_1_0_20230331.pdf>
- **Consultation draft (Mitteilung Nr. 32):** <https://www.bundesnetzagentur.de/DE/Beschlusskammern/BK06/BK6_83_Zug_Mess/835_mitteilungen_datenformate/Mitteilung_32/Mitteilung_Nr32.html>
- **Mitteilung Nr. 58:** <https://www.bundesnetzagentur.de/DE/Beschlusskammern/BK06/BK6_83_Zug_Mess/835_mitteilungen_datenformate/Mitteilung_58/Mitteilung_Nr_58.html>
- **Check-digit source:** BDEW Anwendungshilfe "Identifikatoren in der Marktkommunikation", version 1.2, 07.02.2025: <https://bdew.de/media/documents/AWH_Identifikatoren-in-der-Marktkommunikation_Version.1.2.pdf>
- **Operator use (Berlin):** Stromnetz Berlin, "Messkonzepte", Ausgabe September 2026, 33 pages: <https://www.stromnetz.berlin/files/globalassets/dokumente/anschluss/messkonzepte_09-2026.pdf>
  - sha256 `4e12c90faeb35383dafe86f9ae55ddad220dea50d827167f009d22fe27b29a18`
  - The undated URL `…/messkonzepte.pdf` returns "NotFound"; use the dated one. Recorded for MKC-21.

## Format

- **The document:** a PDF, which is the valid document, plus an "informatorische Lesefassung" in Word. BDEW reserves the right to charge for the Word file in future.
- **No machine-readable form:** no CSV, XML or API carries the codes. The MaKo platform's API only lists documents.
- **Contents:**
  - section 3: an overview table, one row per structure (code, Bezeichnung)
  - section 4: one table per structure (object code, Objekt, Richtung, Ebene, Flexibilität möglich, Anzahl Objekte; some add "Referenz Messlokation" and "Referenz Netzlokation") and a diagram
- **Codes:** 13 digits.
  - The spaces in `9992 00000 002 6` are only for reading; in data exchange codes have no spaces.
  - Structure codes are `9992 00000 0xx x`; object codes (positions of MeLo, MaLo, TR and NeLo in a structure) are `9992 00000 1xx x`.
  - Structure numbers 005 and 014 are not used.
- **Extraction:** pdfplumber reads the tables correctly. Plain `pdftotext -layout` shifts rows: a code gets the next row's name. This matches the Berlin spike of 24.11.2026.
- **The 15 structure codes (edition 13.12.2024):**

| Code | Bezeichnung |
|---|---|
| 9992 00000 001 8 | Verbrauch ohne Messlokation (Pauschal) |
| 9992 00000 002 6 | Verbrauch mit einer Messlokation (Standard) |
| 9992 00000 003 4 | Erzeugung mit einer Messlokation |
| 9992 00000 004 2 | Erzeugung ohne getrennt gemessene Erzeugung |
| 9992 00000 006 8 | Verbrauch mit flexibler Hinterschaltung ohne Erzeugung |
| 9992 00000 007 6 | Verbrauch mit flexibler Hinterschaltung und nicht getrennt gemessener Erzeugung |
| 9992 00000 008 4 | Verbrauch mit flexibler Hinterschaltung und getrennt gemessener flexibler Erzeugung |
| 9992 00000 010 9 | Summenmessung Verbrauch ohne Erzeugung |
| 9992 00000 011 7 | Summenmessung mit mindestens einer ungemessenen Erzeugung |
| 9992 00000 012 5 | Summenmessung mit mindestens einer separat gemessenen Erzeugung |
| 9992 00000 013 3 | Erzeugung mit getrennt gemessener Erzeugung |
| 9992 00000 015 9 | Erzeugungskaskade mit ungemessener Erzeugung |
| 9992 00000 016 7 | Erzeugungskaskade mit gemessener und ungemessener Erzeugung |
| 9992 00000 017 5 | Verbrauchskaskade mit ungemessenen TR (Wärmepumpenkaskade) |
| 9992 00000 018 3 | Verbrauchskaskade mit ungemessenem Verbrauch und gemessener Erzeugung |

- **Berlin:** Stromnetz Berlin's Messkonzepte 09-2026 (pages 6–7, "Code der LBS, Bezeichnung nach edi@energy") list all 15 codes with the same names, and the concept pages cite them ("LBS 9992 00000 013 3"). So the operator follows this edition.

## Licence and terms

- **No licence or copyright statement was found:**
  - none in the text of the three Codeliste editions (searched for Urheber, ©, Nachdruck, Vervielfältigung, Rechte)
  - none on the Bundesnetzagentur pages of Mitteilungen 32, 33, 56 and 58
  - none in the MaKo platform's document list; the site's own pages need JavaScript, and its imprint was not reachable from the command line
- **The MaKo platform marks the document free** (`isFree: true`). The Bundesnetzagentur publishes the editions as attachments to its Mitteilungen.
- **Not to be confused with:** the terms of use for BDEW-Codenummern (Energie Codes und Services GmbH). These cover the codes that identify market participants and the fees for them, not this code list.
- **Our position:** the document is BDEW's work and is treated as protected. The codes, their names and the structure of each bundle are facts that market participants must exchange; we record them as facts with a citation, and we commit nothing of the document itself.
- **Open:** if the MaKo platform's terms of use are found later (imprint or footer in a browser), add them here.

## What may be committed

- **Allowed** (`backend/data/lbs_structures.yaml`):
  - each structure's code, its Bezeichnung and the page it is on
  - per structure, its objects: object code, Objekt, Funktion of a MeLo, Richtung, Ebene, Flexibilität, Anzahl, and the object codes in the columns Referenz Messlokation and Referenz Netzlokation
  - a source block: title, publisher, version, edition, applicable-from date, URL, sha256, retrieval date
- **Not allowed:**
  - the PDF or the Word file, in any form
  - copied prose, footnotes, notes, the change history, diagrams or mini-models
  - any edi@energy or BDEW document
- **The build script** (`scripts/build_lbs_yaml.py`) reads a PDF that the user downloaded into a temp directory and writes only the YAML. It checks the PDF's sha256 against the edition above.
- **Tests** list Berlin's codes as facts (code and page), not text from Berlin's PDF.
- **Normalised, not copied:** the MeLo's Funktion (Netzübergabe, Hinterschaltung, Differenzmessung) stands in the Objekt column on some pages and in the Richtung column on others; the YAML keeps it in `funktion`. "--" becomes empty. Footnote marks are dropped; the footnotes' text is not committed.

## Check digit

- **The Codeliste does not define a check digit.** None of the three editions mentions one.
- **The method the codes follow:** every structure and object code fits the Lok- und Waggon-Kennzeichnungsverfahren, which BDEW uses for BDEW-Codenummern and the MaLo-ID (AWH "Identifikatoren in der Marktkommunikation" 1.2, section 8.1):
  1. Add the digits in odd positions (counted from the left, starting at 1).
  2. Add the digits in even positions and multiply the sum by 2.
  3. Add both results.
  4. The check digit is the difference to the next multiple of 10. If that difference is 10, the check digit is 0.
- **Example from the AWH:** MaLo-ID `4137355924` → 17 + 52 = 69 → check digit 1.
- **Example for LBS:** `999200000002` → odd positions 9+9+0+0+0+0 = 18, even positions (9+2+0+0+0+2) × 2 = 26, sum 44 → check digit 6 → `9992000000026`.
- **What we can claim:** all codes of the edition (15 structure codes, 27 object codes) pass. These codes have the same 13-digit format and method as BDEW-Codenummern, but they are not BDEW-Codenummern: those have 0–8 at position 3, and these have 9.
- **How we use it:** the loader rejects a code that fails the check. This catches typos in the YAML. It does not prove that a code is in the Codeliste; only the list itself does that.
