# Lane A2: SachsenNetze and gold

**Last updated:** 27.11.2026, 23:42

Only this lane's agents write this file; the coordinator keeps `HANDOFF.md` (decision 61). Times are local time (CET) from git and GitHub, never estimated.

- **Tickets, in order:** `MKC-27` → `MKC-24` (MKC-24 waits on lane A's MKC-23)
- **Branch and worktree:** `mkc-27-sachsen-segment`
- **Owns:** `mkc/extraction/sachsen*.py`, its tests and fixtures, the gold tooling. Lane A changes allowed by the coordinator for this wave: the `sachsennetze` line (and its import) in `SEGMENTERS` in `segment.py`, and the `sachsennetze` entry in `backend/data/operators.yaml`.
- **Decision numbers:** 74–75

## In progress

- `MKC-27` (`#27`): the test agent's red acceptance tests are written (see "Red tests" below). Built and mutation-tested: sub-issues `MKC-27.1` (`#201`, segmenter and dispatch) and `MKC-27.2` (`#202`, plan doc, docs and live check). The coordinator accepted the 9 mutation survivors (near-equivalent or not pinned on purpose; listed in the PR body). The PR is being opened.
- Coordinator answers (27.11.2026): assumption 1, 11 regions, the `13 / Nr. (tbd)` half is not an item; assumption 3, the coordinator grants the one-line change in lane A's `test_segment_rules.py` (`"sachsennetze"` → `"unknown-operator"`) and the `NoSegmenter` docstring in `segment.py`.

### Real SachsenNetze layout (studied 27.11.2026, one fetch, no model call)

- `Standard-Messkonzepte.pdf`: HTTP 200, `application/pdf`, 469403 bytes. "Standard-Messkonzepte in Niederspannung", 09/2025, 9 pages, all landscape 960 x 540 pt. The URL and host in `operators.yaml` are correct.
- Page 1 cover, page 2 introduction (no concept), pages 3 to 8 two-up, page 9 legend.
- Each half opens with `Messkonzept <number>:` on its first line (glyph top about 28 to 30 pt): left half at x = 11 pt, right half at x = 499 pt. Title on the line below. Frames: left 4 to 474, divider 474 to 491, right 491 to 956; they end at y about 421 to 487. The footer (`<page> | Standard-Messkonzepte ...`) sits at y about 509 pt, outside the frames.
- Numbers in order: p3 `2-1` | `2-1a`; p4 `2-2` | `2-2a`; p5 `2-3` | `2-3a`; p6 `2-3b` | `2-5a`; p7 `3-1` | `3-2`; p8 `3-5` | `13`.
- That is 12 halves, but page 8 right (`Messkonzept 13:`, title `Nr. (tbd)`, no figure) is a placeholder. 11 numbered concepts match the design (11) and the ticket. The red tests treat the placeholder as not a concept.
- Numbers are not Berlin-style: `2-1a` has a dash, so lane A's `NUMBER` pattern does not match them.

### Pinned interfaces (MKC-27)

- `mkc/extraction/sachsen.py`: `segment_sachsen(pdf: bytes) -> list[ConceptRegion]`, with `ConceptRegion` from `mkc.extraction.segment` (lane A's pinned type).
- `SEGMENTERS["sachsennetze"] is segment_sachsen` (import it in `segment.py`; no other change to that file except the item below).
- Order: pages ascending, left half before right half.
- `number_hint`: the number without the colon (`"2-1"`, `"2-1a"`).
- `bbox` `(x0, top, x1, bottom)` in PDF points, origin top left (the Berlin convention): left region `x1 <= width/2`, right region `x0 >= width/2`; each starts at its heading (top 20 to 35 pt), reaches the last body line (bottom >= 440), and stays above the footer (bottom < 509).
- No region for: cover, contents, legend, a half whose heading is not on the first line of the half (a body line that cites `Messkonzept 2-1:` is not a heading), and a placeholder half (title `Nr. (tbd)`, no figure).
- The split method (detected layout or half page) is the development agent's choice. The tests accept both: the synthetic halves are exactly at x = 11 and x = 499 on a 960 pt page.
- Plan doc: `docs/superpowers/plans/<ddMMyyyyHHmm>-mkc-27-sachsen-segmentation.md`, one file, naming the method (`detected layout` or `half page`) and a reason (`because` or `reason`). Pinned by `test_sachsen_plan.py`; the quality of the reason stays a review item.

### Red tests (MKC-27)

- `backend/tests/extraction/sachsen_pdf.py`: fixtures (`sachsen_pages`, `half`, `make_landscape_pdf`).
- `backend/tests/extraction/test_sachsen.py`, `test_sachsen_plan.py`: acceptance tests. `test_live_sachsen.py`: live (11 concepts, hints and pages as studied), deselected by default.

### Assumptions (for the coordinator to confirm)

1. (Confirmed by the coordinator: 11.) The ticket's "11 items" means the 11 numbered concepts; the placeholder `13 / Nr. (tbd)` is not an item. If the coordinator wants 12 regions (placeholder included), two tests and the live test change.
2. `number_hint` is without the colon.
3. (Granted by the coordinator; done in `18662d9`.) A lane A test breaks when `SEGMENTERS` gains `sachsennetze`: `test_segment_document_refuses_an_operator_without_a_segmenter` in `tests/extraction/test_segment_rules.py` uses `operator_id="sachsennetze"` as the operator without a segmenter. It must move to another id (for example `"unknown-operator"`). That file is lane A's: the coordinator grants the one-line change, or lane A makes it.
4. The Berlin-style `ConceptRegion.bbox` convention (top-left origin) applies.

### Not covered by red tests

- Which split method is chosen (by design, see above) and the quality of its reason in the plan doc.
- A catalogue whose halves are not at the page middle (not in the real PDF).
- The `operators.yaml` comment about "not checked yet" (the URL is correct: it is for the development agent to update the comment).
- Mutation pass: done, see "Mutation pass" below.
- Development agent's own tests: `tests/extraction/test_sachsen_layout.py` (the real page furniture, the heading form, the placeholder by title, any page width).

### Mutation pass (test agent, 27.11.2026, head `5b7b8b9`)

- Method: one hand-written mutant at a time (exact string replacement, checked as applied), `__pycache__` cleared, then `pytest tests/extraction -q -x` (non-live), file restored after each. No mutant was committed. Base run: `89 passed, 3 deselected`.
- Result: 73 mutants listed, 72 applied (one string did not match and was dropped), 47 killed, 25 survived.
- New acceptance tests in `test_sachsen_rules.py` (fixture items `Line`, `Curve`, `Image` added to `sachsen_pdf.py`) kill 16 of the 25 survivors. Final: 72 applied, 63 killed, 9 survived. With them: `107 passed, 3 deselected`.
- Killed by the new tests: heading words 2 pt off the line (`LINE_TOLERANCE` 0), a heading word alone on its line (`len(lines[0]) < 1`), `2.1:` as a number, `NUMBER.match` instead of `fullmatch`, a placeholder as the only second line (`len(lines) > 2`), `PLACEHOLDER.search`, `nr\.` without the optional dot, a frame at 21 pt above the heading (`top - 40`, `0 <=`), `<= footer` on words, a divider crossing the middle (`x0 - 30`), rounding to 0 decimals, lines, curves and images dropped from the graphics, and a half boundary at `width - 1`.
- Already killed (first run): footer band 0.95, 0.80, 1.0 and 0.90, wrong heading word, heading check removed, `len(lines[0]) < 3`, `if not lines` removed, number regex without the dash part, without the letter, without the colon, `group(0)`, title taken from the last line, placeholder never matched, no `IGNORECASE`, `nr(tbd`, first-line top taken from the last line, footer bound dropped for graphics, x1 `+ 30`, `and` to `or`, either half edge dropped, `_inside` dropped for words and graphics, halves swapped, cut at a third, one half only, page numbers from 0 or reversed, `None` regions kept, line sort without top or by x, words in a line sorted by `-x0`, each bbox min/max flipped, content words only or graphics only, rects dropped, footer taken from the width, and both dispatch mutants in `segment.py` (to Berlin, or removed) plus Berlin pointed at `segment_sachsen`.
- Survivors (9):
  1. `sachsen.py:34` `FOOTER_BAND` 0.92 (496.8 pt instead of 491.4 pt): near-equivalent. The real page has nothing between 486 pt (frame bottoms) and 498 pt (logo); only an object in that gap would differ.
  2. `sachsen.py:37` number part `\d{1,3}` instead of `\d{1,2}`: a three-digit concept number is not in the real catalogue; not pinned on purpose.
  3. `sachsen.py:37` letter suffix `[a-z]*` instead of `[a-z]?`: `2-1ab:` is not in the real catalogue; not pinned on purpose.
  4. `sachsen.py:87` graphics lower bound `top + LINE_TOLERANCE`: near-equivalent. Only a graphic that starts within 3 pt of the heading's top differs.
  5. `sachsen.py:87` graphics lower bound `top` instead of `top - LINE_TOLERANCE`: same.
  6. `sachsen.py:87` `< footer` as `<= footer` on graphics: equivalent unless a graphic starts at exactly 491.4 pt.
  7. `sachsen.py:55` `x0 > x0` instead of `>=` (half edge): equivalent unless a graphic starts at exactly the half's edge and is the leftmost content; the heading is always further left.
  8. `sachsen.py:55` `x1 < x1` instead of `<=`: equivalent unless a graphic ends at exactly the half's edge and is the rightmost content.
  9. `sachsen.py:62` line grouping compares with the last word of the line instead of the first: equivalent for the two-word headings in the catalogue; it differs only when a line drifts by more than 3 pt over several words.
- Not mutated: `PLACEHOLDER` allowing other titles, the exact `Nr. (tbd)` wording of other editions (not in the PDF), and the `from __future__` and type-only import lines.

## Next steps

1. Development agent: `scripts/pre_pr.sh` on the final head, PR, `#27`, `#201` and `#202` to `Testing`.
2. Coordinator: review agent once `gh pr checks` is green.
3. MKC-24 waits on lane A's MKC-23.

## Recent log

- **27.11.2026 23:42** Development agent: coordinator ruling: the 9 survivors are accepted, no code change. Preparing the PR.
- **27.11.2026 23:40** Test agent: mutation pass on head `5b7b8b9`: 72 mutants applied, 47 killed, 25 survived; new tests `test_sachsen_rules.py` kill 16 more (63 killed, 9 survived, all near-equivalent or not pinned on purpose); `107 passed, 3 deselected`.
- **27.11.2026 23:24** Development agent: decision 74 (2) now states only what the PDF shows for the placeholder (title `Nr. (tbd)`, no image, `Anwendungen: -`); the design's open question on the split method is marked answered. No ADR describes segmentation (ADR 003 is the database), so no ADR change.
- **27.11.2026 23:24** Development agent: test `test_the_footer_band_keeps_a_frame_line_a_little_lower_than_page_8s` pins `FOOTER_BAND` (0.91): with 0.9 it fails (`1 failed, 5 passed`), with 0.91 `6 passed`.
- **27.11.2026 23:19** Development agent: decision 74 (design section 18), the status doc's Lane A2 section, the backlog's MKC-27 "As built" note and the `operators.yaml` comment (09/2025, 9 pages, 11 concepts). Decision 75 is left for MKC-24.
- **27.11.2026 23:19** Development agent: plan doc `docs/superpowers/plans/271120262318-mkc-27-sachsen-segmentation.md` (half page, with the reasons). The two log lines below had times written by hand; corrected to the commit times from git (23:15 and 23:18).
- **27.11.2026 23:18** Development agent: `mkc/extraction/sachsen.py` (half page split, heading `Messkonzept <n>:` on the half's first line, placeholder by its `Nr. (tbd)` title, footer band at 0.91 of the height) and `SEGMENTERS["sachsennetze"]`. `tests/extraction`: `1 failed, 87 passed, 3 deselected` (only the plan doc test is left). Live run (coordinator's go, no model call): `1 passed in 1.48s`, 11 regions on pages 3 to 8.
- **27.11.2026 23:15** Development agent: own red tests `test_sachsen_layout.py` (5 tests, the real page furniture: background, divider, frames, rule, logo; heading form; placeholder by title; any page width), red: `5 failed`.
- **27.11.2026 23:15** Development agent: sub-issues `#201` and `#202` created; the coordinator-granted edits in lane A's files (the test's operator id and the `NoSegmenter` docstring) done.
- **27.11.2026 23:10** Test agent: red tests for MKC-27 written; real PDF studied (9 landscape pages, 12 halves, 11 concepts plus one `Nr. (tbd)` placeholder).
