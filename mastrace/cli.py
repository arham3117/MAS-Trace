"""Command-line entry point for the MAS-Trace testbed (`mastrace`)."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

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
