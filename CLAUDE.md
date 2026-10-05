# CLAUDE.md: working rules for this repo

- The build plan is `plan.md`. Follow it phase by phase, task by task. Tick tasks with commit hashes.
- At session start: read plan.md §0 and §12 (Progress log), and all non-resolved entries in `issue.md`.
- Log problems in `issue.md` immediately (plan.md §0.3). Resolve only with a regression test.
  After 3 failed attempts: mark Blocked and move on, or ask the human.
- Never change plan.md §2 Fixed decisions without a `decision-change` issue and human approval.
- Invariants (plan.md §3): agents only talk through the router and gateways; no LLM in the core;
  the log is append-only and signed; analysis never reads ground truth; everything replayable.
- Determinism: sorted iteration, counter-based IDs, no timestamps in prompts, temperature 0.
- Run `make check` after every task; run `make gate STAGE=N` at the end of each stage phase.
- Commit message format: `P<phase>.<task>: <summary>` (+ `fixes ISSUE-xxx`).
- Ask the human before: spending on commercial APIs, running the full experiment matrix,
  deleting data, or changing a fixed decision.
