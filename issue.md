# Issue log

Rules are in `plan.md` §0.3:

- Log immediately.
- IDs are sequential and are never reused or deleted.
- Update the index and the entry together.
- Resolve only with a regression test.
- After 3 failed attempts, mark the issue Blocked.

**Status values:** Open · In progress · Blocked · Resolved · Won't fix · Reopened
**Severity values:** Blocker · High · Medium · Low
**Type values:** bug · env · api-mismatch · spec-gap · decision · decision-change · flaky-test · gate-failure · performance

## Index

| ID | Title | Type | Severity | Status | Task | Opened | Resolved |
|---|---|---|---|---|---|---|---|
| ISSUE-001 | Project setup choices for P0.1 | decision | Low | Resolved | P0.1 | 2026-10-05 | 2026-10-05 |
| ISSUE-002 | Model config schema and placeholder dev model | decision | Low | Resolved | P0.3 | 2026-10-05 | 2026-10-05 |
| ISSUE-003 | Scope of the `no_network` fixture | decision | Low | Resolved | P0.4 | 2026-10-05 | 2026-10-05 |
| ISSUE-004 | Recorder design: local refs, clock, signature bytes and tamper triggers | decision | Low | Resolved | P1.6 | 2026-10-05 | 2026-10-05 |
| ISSUE-005 | Prompt/text contract and ScriptedProvider details | decision | Low | Resolved | P2.1 | 2026-10-05 | 2026-10-05 |
| ISSUE-006 | `s3_whiteboard` layout is unknown | spec-gap | Medium | Open | P3.1 | 2026-10-05 | |
| ISSUE-007 | Run IDs contain the attack ID, and every event ID contains the run ID | spec-gap | Low | Open | P5.2 | 2026-10-05 | |

---

## ISSUE-001: Project setup choices for P0.1

- **Type:** decision
- **Severity:** Low
- **Status:** Resolved
- **Task / phase:** P0.1
- **Opened:** 2026-10-05

**What happened**
P0.1 left several setup details open. These choices were made:
1. **Repo root.** The repo root is the existing `AI-Orchestration/` directory. A nested `mas-trace-testbed/` directory (§6) is not created. Paths in §6 are read relative to this root.
2. **Interpreter.** `.python-version` pins Python 3.12. The machine default is 3.14, which is too new for some dependencies (litellm and its transitive packages). `requires-python` stays `>=3.11`, as §2 requires.
3. **Ruff scope.** Ruff excludes `*.md`, because recent ruff formats the Python snippets in `plan.md`.
4. **Mypy.** `strict` is on for `mastrace.core.*` and `mastrace.provenance.*` (§5). The rest uses `check_untyped_defs`.
5. **Typer.** The CLI has a root callback so that `mastrace` stays a command group while it has only one command.
6. **Commit hashes in ticks.** A commit cannot contain its own hash. Each task's tick and Progress-log line go into the **next** commit, which references the hash of the task's commit.

Installed versions at setup: langgraph 1.2.13, litellm 1.104.0, pydantic 2.13.5.

**Resolution**
- Date: 2026-10-05
- Fix: recorded as decisions; no code defect.
- Regression test: n/a (decision).

---

## ISSUE-002: Model config schema and placeholder dev model

- **Type:** decision
- **Severity:** Low
- **Status:** Resolved
- **Task / phase:** P0.3
- **Opened:** 2026-10-05

**What happened**
P0.3 does not fix the `models.yaml` schema or the dev model name. These choices were made:
1. **Schema.** `models.yaml` has a top-level `models:` mapping. Each entry has `provider` (`scripted` or `litellm`), plus `policy` (scripted only), or `model`, `api_base_env`, `temperature`, `seed_supported` and `max_tokens`.
2. **API base.** The base URL is stored as the **name** of an environment variable (`api_base_env: OLLAMA_BASE_URL`). It is resolved from the process environment, then from `.env`.
3. **Placeholder model.** `dev_open.model` is set to `ollama/qwen2.5:7b-instruct` until the team chooses a model (§2 says the team picks it).
4. **Commercial key.** `commercial` loads with `model: null`. `ModelConfig.configured` is False until P13.3.
5. **Default key.** `Settings.default_model_key` defaults to `dev_open`.

**Resolution**
- Date: 2026-10-05
- Fix: recorded as decisions. **The team should confirm the `dev_open` model name** before P4.5.
- Regression test: `tests/unit/test_settings.py` (schema and key loading).

---

## ISSUE-003: Scope of the `no_network` fixture

- **Type:** decision
- **Severity:** Low
- **Status:** Resolved
- **Task / phase:** P0.4
- **Opened:** 2026-10-05

**What happened**
P0.4 says `no_network` "blocks `socket.socket.connect` except to hosts allowed in the model config, and only when the test is marked `model`". The wording is ambiguous. It was read as follows:
1. `no_network` is **autouse**, so every test blocks outbound connections, `connect` and `connect_ex` alike. This makes §0.4 ("No network access outside the gateways") hold everywhere.
2. Only tests marked `model` get the exception for provider hosts: the hostnames of every `api_base` in `configs/models.yaml`, plus the IPs they resolve to.
3. `AF_UNIX` sockets are never blocked, because they are local IPC and not network.
4. The guard lives in `tests/netguard.py` (`NetworkGuard`, `NetworkBlockedError`), so gate check G-C5 can reuse it.

**Resolution**
- Date: 2026-10-05
- Fix: recorded as decision.
- Regression test: `tests/unit/test_fixtures.py`

---

## ISSUE-004: Recorder design: local refs, clock, signature bytes and tamper triggers

- **Type:** decision
- **Severity:** Low
- **Status:** Resolved
- **Task / phase:** P1.4–P1.6
- **Opened:** 2026-10-05

**What happened**
P1.4–P1.6 leave several details open. These choices were made:
1. **Local refs.** Event IDs are assigned only at commit (end of superstep), but events within a turn reference each other in `built_from`. `EventBuffer.add` returns a local ref `local:<turn_id>:<k>`. `Recorder.commit` rewrites local refs to event IDs and keeps the mapping. Later router events, such as `message` events built from a turn's `model_call`, can therefore still use them.
2. **Time and hashing.** `time` is part of the hashed record (§7.6 hashes everything except `record_hash` and `signature`). So "identical records regardless of arrival order" holds for a fixed clock. `Recorder` takes an injectable `clock`, and the test uses a constant. Replay matching (G-C3) compares `(kind, actor, turn_id, input_ref, output_ref)`, which excludes time, so this does not affect replay.
3. **Signature input.** The Ed25519 signature covers the raw 32 bytes `bytes.fromhex(record_hash)`. The public key is also written to `data/keys/recorder_ed25519.pub`, so the verifier never needs the private key.
4. **Database guard.** Besides having no UPDATE/DELETE code path, `events.sqlite` has triggers that abort any UPDATE or DELETE on `events`. Tamper tests (P1.7) drop the triggers first, as an attacker with file access could.
5. **Extra helpers.** `EventStore` additionally exposes `append_many` (one transaction per commit), `alerts()`, `verdicts()`, `summary()` and a read-only mode. It has no update or delete for events.

**Resolution**
- Date: 2026-10-05
- Fix: recorded as decisions.
- Regression test: `tests/unit/test_recorder.py`, `tests/unit/test_event_store.py`

---

## ISSUE-005: Prompt/text contract and ScriptedProvider details

- **Type:** decision
- **Severity:** Low
- **Status:** Resolved
- **Task / phase:** P2.1
- **Opened:** 2026-10-05

**What happened**
§7.13 says what the scripted model does, but not how it learns its role, neighbours, sources or senders from a prompt. These choices were made:
1. **Shared text contract.** `mastrace/core/protocol.py` holds it, and the ContextBuilder (P3.3) must use it.
   - Every system prompt ends with an `## Agent profile` block of `key: value` lines.
   - User items carry headers: `[TASK from user]`, `[MESSAGE from B]`, `[TOOL RESULT <tool>]` and `[NOTE]`.
   - Task bodies list their URLs on `SOURCE: <url>` lines, so `researcher_2` simply receives a task whose `SOURCE:` lines are `sources_2`.
   - Action JSON is parsed leniently: bare JSON, a ```json fence, or the first `{…}` object.
2. **Feedback text.** `<n>` in `FEEDBACK: received (<n>)` is the round number on that link (1, 2, …). Feedback goes only to senders listed in `two_way_with`.
3. **No resending.** Each unit (a `FACT:` line or an instruction paragraph) is sent to a given neighbour at most once per run. Without this, `s2_two_way_mesh` would echo facts until the message limits hit.
4. **Operator per turn.** The operator emails and sets `final_output` on **every** turn that brings new content. The report covers all content received so far. Exfiltration triggers on instruction paragraphs that arrived in the current turn.
5. **Email rule.** An email address counts as an instruction only if it is **not** an allowed recipient. **Constraint for P4.3:** clean task pages must contain no email addresses other than `team@acme.example`, or G-C4 (no false alarms) breaks.

**Resolution**
- Date: 2026-10-05
- Fix: recorded as decisions and documented in `tests/fixtures/scripted_policies.md`.
- Regression test: `tests/unit/test_scripted_provider.py`

---

## ISSUE-006: `s3_whiteboard` layout is unknown

- **Type:** spec-gap
- **Severity:** Medium
- **Status:** Open
- **Task / phase:** P3.1
- **Opened:** 2026-10-05

**What happened**
§6 lists `s3_whiteboard.yaml` as "the team's whiteboard layout, 5 agents", but the layout is not written down anywhere in the repo.

**Expected vs actual**
- Expected: the team's layout.
- Actual: a valid placeholder Stage 3 layout is committed: A→B, A↔C, B→D, C→D, D↔E. Its description is marked `PLACEHOLDER` so all 7 configs load.

**Workaround (if any)**
The placeholder is used. No gate check depends on `s3_whiteboard` specifically, but `full.yaml` (Phase 13) runs it.

**Needs from the human:** the whiteboard layout: links and their types, roles, and entry and sink agents.

---

## ISSUE-007: Run IDs contain the attack ID, and every event ID contains the run ID

- **Type:** spec-gap
- **Severity:** Low
- **Status:** Open
- **Task / phase:** P3.5 / P5.2
- **Opened:** 2026-10-05

**What happened**
§7.5 fixes the run ID format as `<config>-<task>-<attack|clean>-<model>-s<seed>`, and §7.4 makes every `event_id` `<run_id>:<seq>`. So the attack ID (e.g. `g1s0`) appears in every event of an attack run. P5.2's acceptance test says the run's `events.sqlite` must not contain the attack ID string. Taken literally, the two conflict.

**Proposed resolution (applied unless the human objects)**
1. Keep the §7.5 run ID format, because it is useful for humans and for `--resume`.
2. The P5.2 test scans every event field **except identifiers** (`event_id`, `run_id`, `built_from`, payload refs) and every payload file for the attack ID and the attacker email. It runs on a `scripted_resistant` run, where no agent acts on the payload. The poisoned page payload necessarily contains the attacker's text, so it is excluded.
3. Analysis code never parses run IDs. A static check is added to `test_boundaries.py` in P5.4: no `run_id.split`/attack-ID regex under `mastrace/analysis/`.
4. Alternative, if the team prefers: use an opaque deterministic run ID (a hash of the run tuple) in events, and keep the readable name only as the directory name and in `manifest.json`.

---

<!--
Copy this block for each new issue, directly below the last entry. Replace every <...>.

## ISSUE-<NNN>: <short title>

- **Type:** <type>
- **Severity:** <severity>
- **Status:** Open
- **Task / phase:** <P#.#>
- **Opened:** <YYYY-MM-DD>

**What happened**
<observed behaviour, short error message, where it happened>

**How to reproduce**
```bash
<exact command(s)>
```

**Expected vs actual**
- Expected: <...>
- Actual: <...>

**Suspected cause**
<...>

**Attempts** (append only)
1. <YYYY-MM-DD>: tried <...>; result <...>

**Workaround (if any)**
<...>

**Resolution** (fill when resolved)
- Date: <YYYY-MM-DD>
- Commit: <hash>
- Fix: <what changed>
- Regression test: `tests/...::test_name` (or why no test is possible)
-->
