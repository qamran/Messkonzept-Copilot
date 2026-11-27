# MKC-27 plan: SachsenNetze segmentation

**Ticket:** MKC-27 (#27), sub-issues MKC-27.1 (#201) and MKC-27.2 (#202). **Branch:** `mkc-27-sachsen-segment` (lane A2).

**Goal:** two concepts per landscape page become two items.

**Spec:** design feature 37; backlog entry MKC-27; MKC-21's segmenter (`mkc/extraction/segment.py`, decision 64); the test agent's pinned interfaces in `handoff/lane-a2.md`.

## The catalogue

"Standard-Messkonzepte in Niederspannung", 09/2025, 9 landscape pages of 960 x 540 pt (studied 27.11.2026, one fetch, no model call):

- page 1 cover, page 2 introduction, page 9 legend: no concept
- pages 3 to 8: two concepts side by side, 12 halves
- each half opens with `Messkonzept <number>:` (left at x = 11 pt, right at x = 499 pt, top 27.8 pt), the title on the line below
- frames: left 3.7 to 474.3, a divider box 474.3 to 491.3 across the middle (480), right 491.3 to 956.3; their bottom lines lie at 479.8 to 485.8 pt
- below the frames: a page-wide rule at 483.2 pt, the logo from 498 pt (right half), the footer text from 509 pt
- page 8 right is `Messkonzept 13:` with the title `Nr. (tbd)` and no figure: a placeholder, so 11 concepts

## Split method: half page

The method chosen is **half page**: each page is cut at the middle of its width, and each half is read on its own. The other option, a detected layout (finding the frames or the gutter and cutting there), was not chosen, for these reasons:

- The layout is fixed. All six two-up pages have the same frames at the same positions, so a detected cut would land at the same place as the middle every time.
- The middle is always in the gutter: the divider box (474.3 to 491.3) holds the middle (480) on every concept page, so no concept content crosses it.
- Detection would add failure modes and nothing to detect in tests: the frames are drawn as rectangles and lines that also include a page background and a divider that spans both halves, so a detector would need its own rules for which boxes count; the synthetic fixtures of the acceptance tests have no frames at all.
- A new edition with a different layout fails loudly, not silently: the live test pins the 11 numbers and pages.

Inside a half the region is still found from the content (the "detected" part is only the bounds, not the cut):

1. Words and graphics belong to a half only when they lie wholly inside it. This drops the page background (0 to 960), the divider box and the frame lines that cross the middle.
2. The half is a concept when its first line is `Messkonzept` followed by a number with its colon (`2-1:`, `2-1a:`). A body line that cites `Messkonzept 2-1:` lower down is not a heading.
3. A half whose title line is `Nr. (tbd)` is a placeholder and gives no region. The title decides, not a missing figure: the placeholder half has frames like every other half, and the synthetic concepts have a frame box but no image.
4. The bbox is `(x0, top, x1, bottom)`, origin top left (as for Berlin): the half's words and graphics from the heading's line down (graphics that start more than 3 pt above the heading, the frame tops at 20.3 pt, are left out), and only content that starts above the footer band at 0.91 of the page height (491.4 pt of 540), between the frames' bottom lines (up to 485.8) and the logo (498).
5. Order: pages ascending, left half before right. `number_hint` is the number without the colon.

## Tasks

- [x] MKC-27.1: coordinator-granted edits in lane A's files (the no-segmenter test's id, the `NoSegmenter` docstring)
- [x] MKC-27.1: own red tests on the real page furniture (`tests/extraction/test_sachsen_layout.py`)
- [x] MKC-27.1: `mkc/extraction/sachsen.py` and `SEGMENTERS["sachsennetze"]`
- [x] MKC-27.2: live check (11 regions on pages 3 to 8)
- [x] MKC-27.2: this plan, decision 74, status doc, backlog "As built", the `operators.yaml` comment, `handoff/lane-a2.md`

## Not in scope

- A catalogue whose halves are not at the page middle (not in the real PDF; the live test would catch a new layout).
- Extraction of the regions (MKC-22 and on, lane A).
