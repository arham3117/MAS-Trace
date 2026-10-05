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
