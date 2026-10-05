"""Command-line entry point for the MAS-Trace testbed (`mastrace`)."""

import typer

app = typer.Typer(help="MAS-Trace testbed CLI.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """MAS-Trace testbed CLI."""


@app.command()
def version() -> None:
    """Print the package version."""
    from mastrace import __version__

    typer.echo(__version__)
