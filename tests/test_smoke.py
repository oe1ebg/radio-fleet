from radio_fleet import __version__
from radio_fleet.cli import main


def test_version() -> None:
    assert __version__


def test_cli_runs() -> None:
    assert main([]) == 0
