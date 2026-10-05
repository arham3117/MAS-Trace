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
) -> None:
    """Run one configuration end to end and verify its log."""
    from mastrace.control.controller import run_with_attack

    if mode not in MODES:
        raise typer.BadParameter(f"mode must be one of {', '.join(MODES)}")
    result = run_with_attack(
        config, task, attack, model, seed, mode=cast("Mode", mode), overwrite=overwrite
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
