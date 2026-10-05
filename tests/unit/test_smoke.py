"""Smoke test for the package skeleton."""

from typer.testing import CliRunner

import mastrace
from mastrace.cli import app


def test_version_command() -> None:
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert mastrace.__version__ in result.output
