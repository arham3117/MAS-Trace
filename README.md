# MAS-Trace testbed

A testbed that runs 5-agent LLM systems connected as a graph, plants a prompt-injection
attack in one agent, records every action in a tamper-evident log, and traces the observed
symptom back to the agent and step where the attack entered.

The build plan is in [`plan.md`](plan.md), and open problems are in [`issue.md`](issue.md).

## Quick start

```bash
# Requirements: uv (https://docs.astral.sh/uv/), Python >= 3.11 (3.12 pinned)
make install                  # create .venv and install dependencies
cp .env.example .env          # then set OLLAMA_BASE_URL / VLLM_BASE_URL
make check                    # lint + format check + mypy + unit tests
```

## Common commands

```bash
make check                    # run after every change
make test-all                 # every test, including model / slow / gate
make gate STAGE=1             # run the stage gate (plan.md §9)
mastrace run --config configs/graphs/s1_chain.yaml --task t01 --attack g1s0 \
    --model scripted_gullible --seed 1
mastrace verify-log --run <run_id>
mastrace trace --run <run_id>
```

Some commands only exist once their phase is built. See plan.md §11.

## Layout

- `mastrace/`: the package (core, provenance, mediation, runtime, environment, control,
  groundtruth, analysis, evaluation)
- `configs/`: graph, model, tracer and experiment configs
- `prompts/`, `env/templates/`, `attacks/`: agent prompts, task environments, attack specs
- `tests/`: unit, integration and gate tests
- `data/` (gitignored): run logs, payloads, ground truth, caches, keys
