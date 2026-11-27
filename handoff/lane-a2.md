# Lane A2: SachsenNetze and gold

**Last updated:** 27.11.2026, 23:10

Only this lane's agents write this file; the coordinator keeps `HANDOFF.md` (decision 61). Times are local time (CET) from git and GitHub, never estimated.

- **Tickets, in order:** `MKC-27` → `MKC-24` (MKC-24 waits on lane A's MKC-23)
- **Branch and worktree:** `mkc-27-sachsen-segment`
- **Owns:** `mkc/extraction/sachsen*.py`, its tests and fixtures, the gold tooling. Lane A changes allowed by the coordinator for this wave: the `sachsennetze` line (and its import) in `SEGMENTERS` in `segment.py`, and the `sachsennetze` entry in `backend/data/operators.yaml`.
- **Decision numbers:** 74–75

## In progress

- `MKC-27` (`#27`): the test agent's red acceptance tests are written (see "Red tests" below). The development agent has not started.

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

1. The ticket's "11 items" means the 11 numbered concepts; the placeholder `13 / Nr. (tbd)` is not an item. If the coordinator wants 12 regions (placeholder included), two tests and the live test change.
2. `number_hint` is without the colon.
3. A lane A test breaks when `SEGMENTERS` gains `sachsennetze`: `test_segment_document_refuses_an_operator_without_a_segmenter` in `tests/extraction/test_segment_rules.py` uses `operator_id="sachsennetze"` as the operator without a segmenter. It must move to another id (for example `"unknown-operator"`). That file is lane A's: the coordinator grants the one-line change, or lane A makes it.
4. The Berlin-style `ConceptRegion.bbox` convention (top-left origin) applies.

### Not covered by red tests

- Which split method is chosen (by design, see above) and the quality of its reason in the plan doc.
- A catalogue whose halves are not at the page middle (not in the real PDF).
- The `operators.yaml` comment about "not checked yet" (the URL is correct: it is for the development agent to update the comment).
- Mutation pass: not yet run (after the development agent's code).

## Next steps

1. Coordinator: confirm the assumptions above (the 11 vs 12 and the lane A test change).
2. Development agent: build `mkc/extraction/sachsen.py`, wire `SEGMENTERS`, write the plan doc, update the `operators.yaml` comment, make the red tests green, run `scripts/pre_pr.sh`.
3. Test agent: mutation pass on that code.
4. MKC-24 waits on lane A's MKC-23.

## Recent log

- **27.11.2026 23:10** Test agent: red tests for MKC-27 written; real PDF studied (9 landscape pages, 12 halves, 11 concepts plus one `Nr. (tbd)` placeholder).
