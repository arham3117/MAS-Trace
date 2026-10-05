"""`run_once`: one complete, logged, verified run (plan.md §7.5, P3.5)."""

from __future__ import annotations

import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mastrace.core.errors import RunExists
from mastrace.core.logging import code_version, get_logger
from mastrace.core.protocol import render_task
from mastrace.core.schemas import (
    EventKind,
    GraphConfig,
    Override,
    RunManifest,
    TaskSpec,
)
from mastrace.environment.materializer import env_snapshot_hash, materialize
from mastrace.environment.tasks import load_task
from mastrace.mediation.budget import TokenBudget
from mastrace.mediation.cache import ResponseCache
from mastrace.mediation.model_gateway import Mode, ModelGateway
from mastrace.mediation.providers import make_provider
from mastrace.mediation.providers.scripted import Policy
from mastrace.mediation.router import Router
from mastrace.mediation.tool_gateway import ToolGateway
from mastrace.provenance.event_store import EventStore
from mastrace.provenance.payload_store import PayloadStore
from mastrace.provenance.recorder import EventDraft, Recorder
from mastrace.provenance.signer import Signer
from mastrace.provenance.verifier import Problem, verify_run
from mastrace.runtime.agent_runner import AgentRunner
from mastrace.runtime.graph_config import config_hash, load_graph
from mastrace.runtime.langgraph_app import CommitHook, RunContext, run_graph
from mastrace.runtime.prompts import render_system_prompt
from mastrace.settings import Settings, get_settings, load_model

log = get_logger("run")

# (run_env_dir, task, run_id) -> None. Supplied by the controller for attack runs (P5.2).
InjectHook = Callable[[Path, TaskSpec, str], None]
MANIFEST = "manifest.json"


@dataclass
class RunResult:
    """Outcome of one run."""

    run_id: str
    run_dir: Path
    status: str
    final_output: str | None
    supersteps: int
    tokens_used: int
    problems: list[Problem] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)


def make_run_id(
    config_name: str, task_id: str, attack_id: str | None, model_key: str, seed: int
) -> str:
    """`<config>-<task>-<attack|clean>-<model>-s<seed>` (§7.5)."""
    return f"{config_name}-{task_id}-{attack_id or 'clean'}-{model_key}-s{seed}"


def task_sources_for(cfg: GraphConfig, agent_id: str, task: TaskSpec) -> list[str]:
    """`researcher_2` reads `sources_2`; every other entry agent reads `sources`."""
    return task.sources_2 if cfg.agent(agent_id).role == "researcher_2" else task.sources


def run_once(
    config: str | Path | GraphConfig,
    task_id: str,
    attack_id: str | None = None,
    model_key: str | None = None,
    seed: int = 1,
    mode: Mode = "record",
    overrides: Sequence[Override] = (),
    *,
    settings: Settings | None = None,
    run_id: str | None = None,
    env_source: Path | None = None,
    inject: InjectHook | None = None,
    policy_overrides: dict[str, Policy] | None = None,
    feedback_rounds: int = 1,
    on_commit: Sequence[CommitHook] = (),
    overwrite: bool = False,
    replay_of: str | None = None,
) -> RunResult:
    """Run one configuration end to end and verify its log.

    `env_source` copies an existing materialized env (replays); otherwise the task
    template is materialized and, for attack runs, `inject` poisons it.
    """
    settings = settings or get_settings()
    cfg = config if isinstance(config, GraphConfig) else load_graph(config)
    model_key = model_key or cfg.model
    model_cfg = load_model(model_key, settings.models_config)
    if model_cfg.provider == "scripted":
        cfg.check_scripted_feedback(feedback_rounds)
    task = load_task(task_id, settings.templates_dir)
    run_id = run_id or make_run_id(cfg.name, task_id, attack_id, model_key, seed)
    run_dir = settings.runs_dir / run_id
    if run_dir.exists():
        if not overwrite:
            raise RunExists(f"run directory exists: {run_dir}")
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)

    # -- environment -----------------------------------------------------------
    env_dir = run_dir / "env"
    if env_source is not None:
        shutil.copytree(env_source, env_dir, ignore=shutil.ignore_patterns("outbox.jsonl"))
        snapshot = env_snapshot_hash(env_dir)
    else:
        materialize(settings.templates_dir / task_id, env_dir, seed)
        if attack_id is not None:
            if inject is None:
                raise ValueError("attack runs need an inject hook (the controller provides it)")
            inject(env_dir, task, run_id)
        snapshot = env_snapshot_hash(env_dir)

    cfg_hash = config_hash(cfg)
    version = code_version()
    manifest = RunManifest(
        run_id=run_id,
        config_name=cfg.name,
        config_hash=cfg_hash,
        config=cfg.model_dump(mode="json"),
        stage=cfg.stage,
        task_id=task_id,
        attack_id=attack_id,
        model_key=model_key,
        seed=seed,
        mode=mode,
        overrides=list(overrides),
        code_version=version,
        status="running",
        env_snapshot_hash=snapshot,
        replay_of=replay_of,
    )
    _write_manifest(run_dir, manifest)

    # -- wiring ------------------------------------------------------------------
    assert settings.keys_dir is not None and settings.cache_path is not None
    store = EventStore.for_run(run_dir)
    recorder = Recorder(
        run_id,
        cfg.stage,
        store,
        PayloadStore(run_dir / "payloads"),
        Signer(settings.keys_dir),
        version,
    )
    budget = TokenBudget(cfg.limits.max_tokens_run)
    cache = ResponseCache(settings.cache_path)
    provider = make_provider(model_cfg, policy_overrides, feedback_rounds)
    model_gw = ModelGateway(
        provider,
        cache,
        budget,
        mode=mode,
        overrides=overrides,
        temperature=model_cfg.temperature,
        max_tokens=model_cfg.max_tokens,
        seed=seed,
    )
    tool_gw = ToolGateway(
        env_dir, snapshot, {a.id: a.tools for a in cfg.agents}, cache=cache, overrides=overrides
    )
    router = Router(cfg, recorder, budget, overrides)
    prompts = {a.id: render_system_prompt(cfg, a.id, task.allowed_recipients) for a in cfg.agents}
    runner = AgentRunner(cfg, model_gw, tool_gw, prompts)
    ctx = RunContext(cfg, router, runner, recorder, budget, on_commit=list(on_commit))

    recorder.record_now(
        EventDraft(
            kind=EventKind.RUN_START,
            actor="controller",
            superstep=0,
            meta={
                "config": cfg.name,
                "config_hash": cfg_hash,
                "task_id": task_id,
                "model": model_key,
                "seed": seed,
                "mode": mode,
                "env_snapshot_hash": snapshot,
            },
        )
    )
    for agent_id in cfg.entry_agents:
        body = render_task(task.instruction, task_sources_for(cfg, agent_id, task))
        ev = recorder.record_now(
            EventDraft(
                kind=EventKind.TASK_INPUT,
                actor="user",
                superstep=0,
                receivers=[agent_id],
                output_text=body,
            )
        )
        router.put_task(agent_id, ev.event_id, body)

    # -- run ---------------------------------------------------------------------
    status, supersteps, error = "crashed", 0, None
    try:
        state = run_graph(ctx, thread_id=run_id)
        status = str(state["status"])
        supersteps = state["superstep"]
    except BaseException as e:
        error = e
        log.exception("run %s crashed", run_id)
    stats = {
        "router_messages": router.stats()["messages"],
        "model_calls": model_gw.stats()["calls"],
        "live_model_calls": model_gw.stats()["live_calls"],
        "tool_calls": tool_gw.stats()["calls"],
    }
    end_meta: dict[str, Any] = {"status": status, "supersteps": supersteps, "tokens": budget.used}
    if error is not None:
        end_meta["error"] = f"{type(error).__name__}: {error}"[:500]
    _finish(recorder, store, ctx, end_meta, stats, supersteps)
    store.close()
    cache.close()
    manifest.status = status
    _write_manifest(run_dir, manifest)
    if error is not None:
        raise error

    problems = verify_run(run_dir, keys_dir=settings.keys_dir)
    if problems:
        log.error("run %s failed log verification: %s", run_id, problems)
    return RunResult(
        run_id=run_id,
        run_dir=run_dir,
        status=status,
        final_output=ctx.final_output,
        supersteps=supersteps,
        tokens_used=budget.used,
        problems=problems,
        stats=stats,
    )


def _finish(
    recorder: Recorder,
    store: EventStore,
    ctx: RunContext,
    end_meta: dict[str, Any],
    stats: dict[str, int],
    supersteps: int,
) -> None:
    """Commit anything left from a crashed superstep, then write `run_end` and the summary."""
    if ctx.pending:
        recorder.commit([r.buffer for r in ctx.pending])
        ctx.pending = []
    end = recorder.record_now(
        EventDraft(kind=EventKind.RUN_END, actor="controller", superstep=supersteps, meta=end_meta)
    )
    store.set_summary(
        {
            **end_meta,
            "final_output": ctx.final_output,
            "stats": stats,
            "event_count": end.seq,
            "head_hash": end.record_hash,
        }
    )


def _write_manifest(run_dir: Path, manifest: RunManifest) -> None:
    (run_dir / MANIFEST).write_text(manifest.model_dump_json(indent=2), encoding="utf-8")


def read_manifest(run_dir: Path) -> RunManifest:
    """Load a run's manifest.json."""
    return RunManifest.model_validate_json((run_dir / MANIFEST).read_text(encoding="utf-8"))
