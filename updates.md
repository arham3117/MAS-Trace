# MAS-Trace testbed: work update

**As of:** 2026-10-05 · **Repo:** https://github.com/arham3117/MAS-Trace (branch `main`)
**Plan progress:** 40 of the plan's tasks are done (P0.1 → P9.1). **P9.2 is blocked** waiting for a team decision (see `decisions.md`).

---

## 1. Summary

The testbed has everything the plan needs up to the Stage 1 gate, plus most of the machinery for later stages:

- It runs 5-agent LLM teams on 7 graph layouts: one-way, two-way and mixed links.
- It plants a prompt-injection attack in one web page.
- It records every action in a hash-chained, Ed25519-signed log.
- It replays runs from a cache.
- It traces a symptom back to the agent and turn where the attack entered.

The end-to-end pipeline works and is tested, using the deterministic **scripted** model:
- Every plain-code gate check passes for **Stages 1, 2 and 3**.
- The tracer names the right agent (`A`) and turn (`A#1`) on the chain, fan-in, fan-out, two-way and mixed layouts.
- With the real local model, the system completes its tasks (73% clean utility) and raises no false alarms.

**The one blocker:** the prompt-injection attack never succeeds on the local model. The prompts I tuned for task
quality tell agents to forward only `FACT:` lines, so the attacker's text is filtered out at the first agent.
Without successful attacks, the tracer cannot be tested on the real model. Fixing this needs your decision **D1**
in `decisions.md`.

| Item | Status |
|---|---|
| Code | ~5,350 lines in `mastrace/`, ~4,700 lines of tests |
| `make check` (lint, format, mypy, unit + integration tests) | **392 passed** (29 gate tests and 1 model test run separately) |
| Stage 1 gate, plain code | **PASS** (`reports/gates/stage1_2026-10-05_plumbing.md`) |
| Stage 1 gate, with the real model | **INCONCLUSIVE** (`reports/gates/stage1_2026-10-05.md`) |
| Stage 2 and 3 checks, plain code | All pass (run during P8.2; not yet ticked) |
| Clean baseline (`s1_chain`, t01–t10) | Scripted 100%, dev model 73% (`reports/baselines/clean_s1_chain.md`) |
| Issues logged | 14 (`issue.md`): 8 resolved, 5 open, 1 blocked |
| Decisions waiting for you | 8 (`decisions.md`), 2 of them blocking |

---

## 2. Environment

| Item | Value |
|---|---|
| Python | 3.12 (pinned in `.python-version`; your default 3.14 is too new for LiteLLM), managed with `uv` |
| Key libraries | langgraph 1.2.13, litellm 1.104.0, pydantic 2.13.5, pynacl, networkx |
| Local model | Ollama on `localhost:11434`, `qwen2.5:14b-instruct-q4_K_M`, context 16,384 tokens |
| Data | `data/` (gitignored): runs, payloads, `ground_truth.sqlite`, cache, signing keys |

Commands:

```bash
make install            # set up the environment
make check              # lint + types + tests (run after every change)
uv run mastrace run --config s1_chain --task t01 --attack g1s0 --model scripted_gullible --seed 1
uv run mastrace verify-log --run <run_id>
uv run mastrace trace --run <run_id>
uv run mastrace gate --stage 1 [--plumbing-only]
uv run mastrace stage-status
```

---

## 3. What was built, phase by phase

### Phase 0: Project setup (P0.1–P0.5) ✅
- Package skeleton, `pyproject.toml`, `uv.lock`, ruff, mypy (strict on `core/` and `provenance/`), pytest markers
  (`plumbing`, `model`, `slow`, `gate`), and a `Makefile`.
- `CLAUDE.md`, `issue.md`, `.gitignore`, `.env.example` and `README.md`.
- `settings.py` and `configs/models.yaml` (model keys `scripted_gullible`, `scripted_resistant`, `dev_open`, `commercial`).
- **Network guard** (`tests/netguard.py`): every test blocks outbound connections. Only tests marked `model` may
  reach the model server. The guard later caught a real bug (ISSUE-010).
- Logging, and `code_version()`, which stamps every event with the git hash (plus `-dirty`).

### Phase 1: Event log and provenance (P1.1–P1.7) ✅
- **Schemas** for events, manifests, verdicts, overrides, graph configs (validation rules 1–8), tasks and attacks.
- **Canonical JSON and hashes** for request caching.
- **Payload store**: full inputs and outputs, stored by SHA-256, with atomic writes.
- **Ed25519 signer**: the key file has mode 0600, and a separate public key is used for verification.
- **Event store**: SQLite, append-only. There is no update or delete code, and database triggers also block any
  UPDATE or DELETE.
- **Recorder**: assigns sequence numbers in a fixed order, chains hashes and signs each event. 1,000 events commit
  in 0.4 s (target < 2 s).
- **Verifier and `mastrace verify-log`**: detect edited fields, deleted records, reordered records, altered
  payloads, bad signatures and truncation.

### Phase 2: Gateways and memory (P2.1–P2.4) ✅
- **Text protocol** (`core/protocol.py`): the agent-profile block, inbox headers and JSON actions, shared by
  the prompt builder and the scripted model.
- **ScriptedProvider**: a deterministic stand-in model with `gullible` and `resistant` policies, per-agent
  overrides and two-way feedback rounds. Documented in `tests/fixtures/scripted_policies.md`.
- **LiteLLMProvider**: real models, temperature 0, seed, 3 retries on transient errors.
- **Model gateway**: cache, `record` / `replay` / `strict_replay` modes, output overrides, run token budget, and
  one event per call.
- **Tool gateway and tools**: `web_fetch` (fake web), `read_file` (blocks path traversal), `send_email` (writes to
  an outbox file; never sends anything real) and memory tools. Covers permission checks, argument checks,
  overrides and caching.
- **Memory service**: versioned keys, private per agent plus a `shared/` namespace.

### Phase 3: Router and run loop (P3.1–P3.5) ✅
- **All 7 graph configs** in `configs/graphs/` (`s3_whiteboard` is a placeholder; see D3) and the role prompts.
- **Router**: link checks per direction, message limits, budget and quarantine rejections, a fixed delivery order,
  and the termination rules.
- **ContextBuilder and AgentRunner**: every prompt item is tagged with its source event, so `built_from` is
  exact. Also handles the parse retry and fallback, and the tool-call cap.
- **LangGraph app**: `router ⇄ agents_step`. A looping config stops at the superstep limit instead of crashing.
- **`run_once` and `mastrace run`**: a whole run, verified at the end. Two identical runs produce identical logs.

### Phase 4: Environment, tasks and baseline (P4.1–P4.5) ✅
- **Materializer**: copies a task into the run and inserts a canary secret derived from the seed. The canary
  appears only in `credentials.txt`.
- **Prompt snapshot tests**.
- **Task suite t01–t10**: 41 web pages on topics such as CRM vendors, laptops, venues, cloud storage, travel and
  shipping. A subagent wrote them, and they were validated by tests: word counts, `FACT:` lines, and no text that
  would trigger the detectors.
- **Checkers**: utility (share of expected facts in the report), G1 (canary emailed to an outsider) and G2
  (marker in the report).
- **Clean baseline**: scripted 100%. Dev model **3% → 47% → 73%** over 3 prompt iterations (ISSUE-009). The fixes:
  - lenient JSON parsing;
  - "one action per reply" and "never invent tool results";
  - tool argument names listed in the prompt;
  - "copy FACT lines exactly";
  - "the report is the message you received, not a file".

### Phase 5: Attacks and ground truth (P5.1–P5.4) ✅
- **Attack library**: `g1s0`, `g1s1` (exfiltrate the canary), `g2s0`, `g2s1` (inject a marker); drafts `g1s2`,
  `g1s3`, `g2s2`, `g2s3` are disabled until Phase 13.
- **Injector**: poisons one page and writes ground truth **only** to `ground_truth.sqlite`. A test checks that
  nothing about the injection leaks into the run log.
- **Ground-truth resolver**: entry event, entry turn, true paths and attack success.
- **Boundary tests**: a static import graph proves analysis code cannot reach ground truth, even through a chain of
  imports, and that only the agent runner and the investigator call the model. Both checks are shown to catch a
  planted violation.

### Phase 6: Event graph, detectors and oracle (P6.1–P6.3) ✅
- **EventGraph**: breadth-first ancestors (each event visited once) and causal message paths.
- **Detectors**: D1 canary leak, D2 forbidden recipient, D4 injection pattern. They run after every commit and
  raise no alerts on clean runs.
- **Symptom oracle**: G1 → the leaking `send_email`; G2 → the `final_output`.

### Phase 7: Replay and tracer (P7.1–P7.3) ✅
- **Replay engine**: a replay with no overrides reproduces the run exactly (gate check G-C3). Each replay salts its
  own cache entries, so the "majority of 3 replays" rule really samples three times (ISSUE-008; the plan had a
  hidden flaw here).
- **Tracer v1**:
  - ranks entry candidates by content overlap plus injection pattern;
  - confirms them by replaying with the candidate neutralized;
  - extracts paths, and for Stage 3 tests each path by dropping its distinguishing edge.
- **`mastrace trace`**: prints the ranking, the replays and the verdict.

### Phase 8: Scorer and gates (P8.1–P8.3) ✅
- **Scorer**: agent, step and event correctness, path precision and recall, wrong blame, false alarms and cost →
  `scores.csv`.
- **Gate suites** for all three stages (§9), plus the "15 seeds until 5 symptomatic runs" rule for real-model checks.
- **`mastrace gate --stage N`** and **`mastrace stage-status`**, which write the §9.4 report.

### Phase 9: Stage 1 gate (P9.1 ✅, P9.2 ⛔, P9.3 pending)
- **P9.1, plain code: PASS.** All checks pass 5/5:
  - G-C1 log complete
  - G-C2 integrity
  - G-C3 replay identical
  - G-C4 no false alarms
  - G-C5 no direct network
  - G1-1 chain, G1-2 fan-in, G1-3 fan-out
- **P9.2, real model: INCONCLUSIVE.**
  - G-C4 with the dev model: PASS 5/5.
  - G1-1 and G1-2 with the dev model: 0 of 15 runs symptomatic.

  The first attempt also surfaced ISSUE-010 (LiteLLM contacting GitHub), which is fixed.

### Already done ahead of plan (plain code only, not ticked)
These were run during P8.2, and all pass with the scripted model:
- G2-1: two-way conversations always stop (20/20).
- G2-2: the tracer finishes on long conversations, visiting each event once.
- G2-3: the culprit is found after back-and-forth.
- G3-1: both paths are found on the mixed layout.
- G3-2: the causal path is picked when one path is made resistant.

---

## 4. Issues (`issue.md`)

| ID | Title | Type | Status |
|---|---|---|---|
| 001 | Project setup choices | decision | Resolved |
| 002 | Model config schema; dev model (switched to the installed 14b model) | decision | Resolved, needs confirmation (D2) |
| 003 | Scope of the network guard | decision | Resolved |
| 004 | Recorder design (local refs, clock, signatures, triggers) | decision | Resolved |
| 005 | Prompt contract and scripted-model details | decision | Resolved |
| 006 | `s3_whiteboard` layout unknown | spec-gap | **Open** (D3) |
| 007 | Run IDs contain the attack ID | spec-gap | **Open** (D4) |
| 008 | n=3 replays would be identical because of the cache | spec-gap | Resolved |
| 009 | Dev model clean utility below 50% | spec-gap | Resolved (73%) |
| 010 | LiteLLM contacts GitHub on import | bug | Resolved |
| 011 | Attack does not land on dev model | gate-failure | **Blocked** (D1) |
| 012 | Prompts have no injection defence | decision | **Open** (D5) |
| 013 | Duplicate verdict ID when tracing twice | bug | Resolved |
| 014 | Ground-truth paths over-count | spec-gap | **Open** (D6) |

Small fixes not logged as issues, because each was fixed inside its own task and covered by a test:
- a macOS socket-path length limit in one test;
- a typo-level index error in one test;
- a ruff style fix.

---

## 5. Choices I made on my own (please review)

These are all recorded as `decision` issues. None of them changes a §2 fixed decision.

- **Repo root.** The project lives at the repo root, not in a `mas-trace-testbed/` subfolder (ISSUE-001).
- **Commit hashes in ticks.** Each task's tick and Progress-log line go into the *next* commit, because a commit
  cannot contain its own hash (ISSUE-001).
- **Code landing early.** Some code landed in an earlier task's commit when a later task depended on it. For
  example, the role prompts arrived with P3.1 because config validation needs them, and the event graph arrived
  with P5.3. Commit messages say so.
- **Code written ahead of order.** P5–P8 were written while the P4.5 baseline was running. They were committed in
  plan order only after P4.5 passed.
- **The dev model** (D2), **no injection defence in prompts** (D5) and **lenient JSON parsing** for real models.
- **One extra field.** `extra_params` was added to model configs, used for `num_ctx`.

---

## 6. What's next

1. **You:** answer `decisions.md`, especially **D1** (how to make attacks land) and **D7** (whether I may continue
   plain-code work meanwhile).
2. **Me, after D1:**
   - apply the chosen fix and re-run the clean baseline (it must stay ≥ 50%);
   - re-run `mastrace gate --stage 1`;
   - if it passes, tick P9.2, tag `gate-stage1-pass` (P9.3) and continue to Stage 2.
3. **Then:**
   - Phase 10: two-way gate with the real model;
   - Phase 11: multi-path and multi-cause tracing (needs D3 and D6);
   - Phase 12: AI investigator and healing;
   - Phase 13: experiments (the commercial model needs D8).

**Time estimate for real-model gates.** A dev-model run takes ~1.5–2 minutes, and each symptomatic run adds up to 9
replays. A full real-model gate check can take 1–2 hours of local compute (no API cost).

---

## Update 2026-10-05: answers.md applied (stopped at a §6 stop condition)

- **Decisions recorded:** ISSUE-015 to ISSUE-022 (one per D1–D8). `decisions.md` answer lines filled in. Linked statuses updated: 002 note, 006, 007, 011, 012, 014.
- **D4 opaque IDs:** done. Events use `run_uid` (`r_` + 16 hex); the readable `run_name` appears only in the directory and `manifest.json`. The strict GT test passes: it scans every event field, identifiers included, and every non-page payload. **Plumbing gates re-run: PASS (43/43, stages 1–3).** ISSUE-007 and ISSUE-018 resolved.
- **D2:** the model digest is recorded per run (`7cdf5a01…`). ISSUE-016 resolved.
- **D3:** the provisional whiteboard layout is in place. An attack run and trace complete. **Note for the team:** with every agent gullible, the leak arrives first over the shorter route A→C→E, so that is the causal path. The intended route A→B→D→E is causal only when C is resistant. ISSUE-006 and ISSUE-017 resolved (provisional).
- **D1a–D1d:**
  - `page_render` (`plain` for real models);
  - normalized utility matching with `match_any` cores, each checked by a test to be distinctive within its task;
  - `handoff_style` prompt sets (`summary` default, `fact_only` identical to the old prompts, `full_context`), with a test that no prompt tells agents to relay or obey instructions;
  - per-hop propagation check (evaluation side);
  - (task, seed) gate sampling and the G2 fallback.
- **D1 baseline (summary, plain):** dev_open utility **53%** (scripted 100%). Prompt iterations used: **1 of 3**. Iteration 0 scored 7%; iteration 1 scored 43% with the first matcher, and 53% after adding number-word and unit-name forms (the same runs re-scored). ISSUE-023 resolved. Report: `reports/baselines/clean_s1_chain.md`.
- **Stage 1 gate (new §9.3 rule):** **running in the background**; results will be appended here. G1-1 __/__ symptomatic, __/5 correct; G1-2 __/__, __/5.
- **G2 fallback used:** pending (it depends on the gate).
- **Propagation by hop (s1_chain, dev_open):** pending (it depends on the gate).
- **D6 validation: agreement 57% on 20 runs (35 run–path pairs). This is a stop condition (ISSUE-025).**
  - Anchor labels and replay *necessity* agree on every single-carrier run (C resistant), and disagree on every run where the payload travels redundant routes. Each route carried the attack, but none is necessary alone.
  - Against replay *sufficiency*, agreement is **100%**.
  - Anchor labels are merged as code but **not used in any report** until the team chooses: (1) validate against sufficiency, (2) use replay labels as truth, or (3) report "carried" and "necessary" as two metrics.
  - Report: `reports/results/d6_path_validation.md`.
- **D7 plain-code progress:**
  - P10.1, P10.2 and P11.1 ticked: their acceptance is covered by the passing scripted gate checks G2-1, G2-2, G3-1 and G3-2.
  - **P11.2 done.** Candidate pairs confirm independent causes, and the scorer compares entry sets. Found and fixed **ISSUE-024**: the tracer could confirm the operator's `credentials.txt` read (a downstream effect) as the entry. A "derived candidate" rule now prevents this.
  - P10.3 and P11.3 are not ticked. P12.1 and P12.2 have not been started, because the stop condition paused new work.
- **Open questions for the team:**
  1. **ISSUE-025:** which truth definition for Stage 3 paths? Options 1–3 above; my recommendation is option 3, reporting both, because "carried" and "necessary" answer different questions.
  2. **D3:** is A→C→E being causal on the whiteboard layout what the team intended?
