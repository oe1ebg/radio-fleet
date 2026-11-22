from radio_fleet import __version__
from radio_fleet.cli import main


def test_version():
    assert __version__


def test_cli_runs():
    assert main([]) == 0
