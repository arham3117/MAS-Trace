"""P3.5: run_once and the `mastrace run` CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from mastrace.cli import app
from mastrace.core.errors import RunExists
from mastrace.core.schemas import EventKind
from mastrace.provenance.event_store import EventStore
from mastrace.runtime.run import read_manifest, run_once
from mastrace.settings import Settings

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "env"


def settings(root: Path) -> Settings:
    return Settings(data_dir=root / "data", templates_dir=FIXTURES)


def signature(run_dir: Path) -> list[tuple[str, str, str | None, str | None, str | None]]:
    with EventStore.for_run(run_dir, readonly=True) as s:
        return [(e.kind.value, e.actor, e.turn_id, e.input_ref, e.output_ref) for e in s.iter()]


def test_run_once_completes_and_verifies(tmp_path: Path) -> None:
    r = run_once("s1_chain", "t_test", None, "scripted_gullible", 1, settings=settings(tmp_path))
    assert r.run_id == "s1_chain-t_test-clean-scripted_gullible-s1"
    assert r.status == "completed" and r.problems == []
    assert r.final_output is not None and "FACT: A costs 10" in r.final_output
    m = read_manifest(r.run_dir)
    assert m.status == "completed" and m.attack_id is None and m.env_snapshot_hash
    with EventStore.for_run(r.run_dir, readonly=True) as s:
        kinds = [e.kind for e in s.iter()]
        summary = s.summary()
    assert kinds[0] == EventKind.RUN_START and kinds[-1] == EventKind.RUN_END
    assert kinds.count(EventKind.TASK_INPUT) == 1
    assert summary is not None and summary["status"] == "completed"
    assert (r.run_dir / "env" / "outbox.jsonl").read_text().count("team@acme.example") == 1


def test_same_arguments_twice_identical(tmp_path: Path) -> None:
    a = run_once(
        "s1_chain", "t_test", None, "scripted_gullible", 1, settings=settings(tmp_path / "1")
    )
    b = run_once(
        "s1_chain", "t_test", None, "scripted_gullible", 1, settings=settings(tmp_path / "2")
    )
    assert signature(a.run_dir) == signature(b.run_dir)


def test_stats_match_event_counts(tmp_path: Path) -> None:
    r = run_once(
        "s2_two_way_chain", "t_test", None, "scripted_gullible", 1, settings=settings(tmp_path)
    )
    with EventStore.for_run(r.run_dir, readonly=True) as s:
        events = list(s.iter())

    def count(*ks: EventKind) -> int:
        return sum(e.kind in ks for e in events)

    assert r.stats["model_calls"] == count(EventKind.MODEL_CALL)
    assert r.stats["tool_calls"] == count(
        EventKind.TOOL_CALL, EventKind.EXTERNAL_READ, EventKind.MEMORY_READ, EventKind.MEMORY_WRITE
    )
    assert r.stats["router_messages"] == count(EventKind.MESSAGE, EventKind.ROUTER_REJECT)


def test_fanin_researcher_2_reads_sources_2(tmp_path: Path) -> None:
    r = run_once("s1_fanin", "t_test", None, "scripted_gullible", 1, settings=settings(tmp_path))
    assert r.status == "completed"
    with EventStore.for_run(r.run_dir, readonly=True) as s:
        reads = [(e.turn_id, e.meta["args"]["url"]) for e in s.iter(EventKind.EXTERNAL_READ)]
    assert ("B#1", "https://vendor-c.example/pricing") in reads
    assert all(t != "B#1" or "vendor-c" in u for t, u in reads)
    assert r.final_output is not None and "FACT: C costs 15" in r.final_output


@pytest.mark.parametrize(
    "config",
    [
        "s1_chain",
        "s1_fanin",
        "s1_fanout",
        "s2_two_way_chain",
        "s2_two_way_mesh",
        "s3_mixed_two_paths",
        "s3_whiteboard",
    ],
)
def test_every_config_completes_scripted(tmp_path: Path, config: str) -> None:
    r = run_once(config, "t_test", None, "scripted_gullible", 1, settings=settings(tmp_path))
    assert r.status == "completed", r.status
    assert r.problems == []


def test_existing_run_refused_unless_overwrite(tmp_path: Path) -> None:
    s = settings(tmp_path)
    run_once("s1_chain", "t_test", None, "scripted_gullible", 1, settings=s)
    with pytest.raises(RunExists):
        run_once("s1_chain", "t_test", None, "scripted_gullible", 1, settings=s)
    r = run_once("s1_chain", "t_test", None, "scripted_gullible", 1, settings=s, overwrite=True)
    assert r.problems == []


def test_crash_is_recorded_then_reraised(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from mastrace.runtime import agent_runner

    def boom(*a: object, **k: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(agent_runner.AgentRunner, "run_turn", boom)
    s = settings(tmp_path)
    with pytest.raises(RuntimeError, match="boom"):
        run_once("s1_chain", "t_test", None, "scripted_gullible", 1, settings=s)
    run_dir = s.runs_dir / "s1_chain-t_test-clean-scripted_gullible-s1"
    with EventStore.for_run(run_dir, readonly=True) as st:
        last = st.last()
    assert last is not None and last.kind == EventKind.RUN_END
    assert last.meta["status"] == "crashed" and "boom" in last.meta["error"]
    assert read_manifest(run_dir).status == "crashed"


def test_cli_run(tmp_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from mastrace.settings import get_settings

    monkeypatch.setenv("MASTRACE_TEMPLATES_DIR", str(FIXTURES))
    get_settings.cache_clear()
    args = [
        "run",
        "--config",
        "s1_chain",
        "--task",
        "t_test",
        "--model",
        "scripted_gullible",
        "--seed",
        "2",
    ]
    res = CliRunner().invoke(app, args)
    assert res.exit_code == 0, res.output
    assert "completed" in res.output
    ok = CliRunner().invoke(
        app, ["verify-log", "--run", "s1_chain-t_test-clean-scripted_gullible-s2"]
    )
    assert ok.exit_code == 0, ok.output
