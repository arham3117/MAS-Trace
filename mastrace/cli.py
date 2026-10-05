"""Command-line entry point for the MAS-Trace testbed (`mastrace`)."""

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, cast

import typer
from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from mastrace.mediation.model_gateway import Mode

MODES = ("record", "replay", "strict_replay")

app = typer.Typer(help="MAS-Trace testbed CLI.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """MAS-Trace testbed CLI."""


@app.command()
def version() -> None:
    """Print the package version."""
    from mastrace import __version__

    typer.echo(__version__)


@app.command("verify-log")
def verify_log(
    run: Annotated[str, typer.Option("--run", help="Run ID under data/runs/.")],
    data_dir: Annotated[
        Path | None, typer.Option("--data-dir", help="Override the data directory.")
    ] = None,
) -> None:
    """Verify a run's hash chain, signatures and payloads. Exit code 1 if anything is wrong."""
    from mastrace.provenance.verifier import verify_run
    from mastrace.settings import Settings, get_settings

    settings = Settings(data_dir=data_dir) if data_dir else get_settings()
    run_dir = settings.runs_dir / run
    problems = verify_run(run_dir, keys_dir=settings.keys_dir)
    console = Console()
    if not problems:
        console.print(f"[green]OK[/green] {run}: log verified")
        return
    table = Table(title=f"{len(problems)} integrity problem(s) in {run}")
    for col in ("check", "seq", "event_id", "detail"):
        table.add_column(col)
    for p in problems:
        table.add_row(p.check, str(p.seq or ""), p.event_id or "", p.detail)
    console.print(table)
    raise typer.Exit(code=1)


@app.command("run")
def run_cmd(
    config: Annotated[str, typer.Option("--config", help="Graph config name or YAML path.")],
    task: Annotated[str, typer.Option("--task", help="Task ID, e.g. t01.")],
    model: Annotated[str, typer.Option("--model", help="Model key from configs/models.yaml.")],
    seed: Annotated[int, typer.Option("--seed")] = 1,
    attack: Annotated[str | None, typer.Option("--attack", help="Attack ID, e.g. g1s0.")] = None,
    mode: Annotated[str, typer.Option("--mode", help="record | replay | strict_replay")] = "record",
    overwrite: Annotated[
        bool, typer.Option("--overwrite", help="Replace an existing run.")
    ] = False,
    allow_disabled: Annotated[
        bool, typer.Option("--allow-disabled", help="Allow attacks drafted for later phases.")
    ] = False,
) -> None:
    """Run one configuration end to end and verify its log."""
    from mastrace.control.controller import run_with_attack

    if mode not in MODES:
        raise typer.BadParameter(f"mode must be one of {', '.join(MODES)}")
    result = run_with_attack(
        config,
        task,
        attack,
        model,
        seed,
        mode=cast("Mode", mode),
        overwrite=overwrite,
        allow_disabled=allow_disabled,
    )
    table = Table(title=result.run_id)
    table.add_column("field")
    table.add_column("value")
    for k, v in [
        ("status", result.status),
        ("supersteps", str(result.supersteps)),
        ("tokens", str(result.tokens_used)),
        ("integrity", "OK" if not result.problems else f"{len(result.problems)} problem(s)"),
        ("run dir", str(result.run_dir)),
    ]:
        table.add_row(k, v)
    Console().print(table)
    if result.problems:
        raise typer.Exit(code=1)


@app.command("trace")
def trace_cmd(
    run: Annotated[str, typer.Option("--run", help="Run ID to diagnose.")],
    symptom: Annotated[
        str | None, typer.Option("--symptom", help="Symptom event ID (default: top alert).")
    ] = None,
) -> None:
    """Trace a symptom back to where the attack entered, confirming by replay."""
    from mastrace.analysis.detectors import top_alert
    from mastrace.analysis.tracer import Tracer, detector_check
    from mastrace.provenance.event_store import EventStore
    from mastrace.settings import get_settings

    settings = get_settings()
    with EventStore.for_run(settings.runs_dir / run, readonly=True) as store:
        alerts = store.alerts()
    alert = top_alert(alerts)
    if alert is None:
        Console().print(f"[yellow]{run}: no alerts; nothing to trace[/yellow]")
        raise typer.Exit(code=1)
    symptom_id = symptom or alert.event_id
    verdict = Tracer(settings).trace(run, symptom_id, detector_check(alert.detector, settings))

    console = Console()
    ranking = Table(title=f"Entry candidates for {symptom_id} ({alert.detector})")
    for col in ("candidate", "kind", "turn", "score", "overlap", "pattern", "depth"):
        ranking.add_column(col)
    for r in verdict.ranking:
        ranking.add_row(
            r["candidate"],
            r["kind"],
            str(r["turn_id"]),
            f"{r['score']:.3f}",
            f"{r['overlap']:.3f}",
            str(r["pattern"]),
            str(r["depth"]),
        )
    console.print(ranking)
    reps = Table(title="Replays")
    for col in ("kind", "target", "replays", "symptom present", "result"):
        reps.add_column(col)
    for r in verdict.replays:
        target = r.get("candidate") or "→".join(r.get("path", []))
        result = str(r.get("confirmed", r.get("status")))
        reps.add_row(
            r["kind"],
            str(target),
            ", ".join(r["replay_run_ids"]),
            str(r.get("symptom_present", "")),
            result,
        )
    console.print(reps)
    console.print(
        f"[bold]Verdict:[/bold] {verdict.status}  entry={verdict.entry_event_id}  "
        f"agent={verdict.entry_agent}  turn={verdict.entry_turn}  paths={verdict.paths}"
    )


@app.command("gate")
def gate_cmd(
    stage: Annotated[int, typer.Option("--stage", min=1, max=3)],
    plumbing_only: Annotated[
        bool, typer.Option("--plumbing-only", help="Skip checks that need a real model.")
    ] = False,
) -> None:
    """Run the common checks and every stage up to N; write the gate report."""
    from mastrace.control.gates import run_gate

    outcome = run_gate(stage, include_model=not plumbing_only)
    Console().print(f"[bold]Stage {stage}: {outcome.overall}[/bold]  report: {outcome.report}")
    if outcome.overall != "PASS":
        raise typer.Exit(code=1)


@app.command("stage-status")
def stage_status_cmd() -> None:
    """Show the latest gate result for each stage."""
    from mastrace.control.gates import stage_status

    table = Table(title="Stage gates")
    for col in ("stage", "overall", "report"):
        table.add_column(col)
    status = stage_status()
    for s in (1, 2, 3):
        overall, report = status.get(s, ("not run", ""))
        table.add_row(str(s), overall, report)
    Console().print(table)
