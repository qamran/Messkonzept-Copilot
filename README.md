# Messkonzept-Copilot

Messkonzept-Copilot reads grid operators' Messkonzept PDFs and turns them into structured records keyed by Lokationsbündelstruktur (LBS). A person approves each record before it is saved. It also gives household site advice with citations. It is the capstone project for the Turing College AI Engineering course (Case 5, agent harness).

**Status:** Phase 0 (foundation). The backend skeleton is in `backend/`. Start the database with `docker compose up -d db`, then run `cd backend && uv sync && uv run pytest`. A full README comes with MKC-44.

## Where to find things

The code is pushed to two repos: [qamran/Messkonzept-Copilot](https://github.com/qamran/Messkonzept-Copilot) (home) and the Turing College submission repo, which has the same code. Tickets exist only in the home repo.

- **Board** (ticket status): [https://github.com/users/qamran/projects/1](https://github.com/users/qamran/projects/1)
- **Tickets** (`MKC-<n>`, issue number = key): [https://github.com/qamran/Messkonzept-Copilot/issues](https://github.com/qamran/Messkonzept-Copilot/issues)
- **Design doc:** [docs/superpowers/specs/241120261330-messkonzept-copilot-design.md](docs/superpowers/specs/241120261330-messkonzept-copilot-design.md)
- **Architecture Decision Records:** [docs/adr/](docs/adr/)
- **Agent restart file** (what is done, in progress and next): [HANDOFF.md](HANDOFF.md)
- **Project status:** [docs/241120261430-project-status.md](docs/241120261430-project-status.md)
- **Course brief:** [AE.CAP_afa.md](AE.CAP_afa.md)

Every commit message starts with its ticket key (`MKC-<n>: …`), so each commit in either repo leads back to its ticket.
