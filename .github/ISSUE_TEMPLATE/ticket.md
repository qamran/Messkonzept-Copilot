---
name: Ticket / issue / sub-issue
about: Every unit of work (ADR 005). Success criteria are mandatory.
title: "MKC-<n>: <short title>"
labels: []
---

**Key:** MKC-<n> (sub-issues: MKC-<n>.<m>)
**Phase:** <0–8 | deferred>
**Parent:** <MKC-<n> (#issue), for sub-issues>

**Goal:** <one sentence: what is true when this is done>

**Scope:** <design-doc feature numbers; what is in, what is out>

**Depends on:** <MKC-<m>, ...>

**Interfaces:**

- Consumes: <exact names from earlier tickets>
- Produces: <exact names later tickets rely on>

**Test:** <test names, commands or checks that prove it>

**Success criteria (definition of done):**

- [ ] <concrete, checkable result>
- [ ] <concrete, checkable result>
- [ ] Docs updated where a decision changed (design doc decision log, ADR, status doc)
- [ ] CI green; review agent (Fable) verdict "pass"
