"""P7.3: `mastrace trace` on a scripted run."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mastrace.cli import app


def test_trace_cli(tmp_data_dir: Path) -> None:
    runner = CliRunner()
    args = [
        "run",
        "--config",
        "s1_chain",
        "--task",
        "t01",
        "--attack",
        "g1s0",
        "--model",
        "scripted_gullible",
        "--seed",
        "1",
    ]
    assert runner.invoke(app, args).exit_code == 0
    res = runner.invoke(app, ["trace", "--run", "s1_chain-t01-g1s0-scripted_gullible-s1"])
    assert res.exit_code == 0, res.output
    assert "Verdict: confirmed" in res.output
    assert "agent=A" in res.output and "turn=A#1" in res.output


def test_trace_cli_clean_run_has_nothing(tmp_data_dir: Path) -> None:
    runner = CliRunner()
    args = ["run", "--config", "s1_chain", "--task", "t01", "--model", "scripted_gullible"]
    assert runner.invoke(app, args).exit_code == 0
    res = runner.invoke(app, ["trace", "--run", "s1_chain-t01-clean-scripted_gullible-s1"])
    assert res.exit_code == 1 and "no alerts" in res.output
