"""The dmrconf adapter's translation of the tool's outcome (R10), with a stand-in command."""

import sys
from pathlib import Path

import pytest

from radio_fleet.dmrconf import CheckError, DmrconfCli


def stand_in(script: str) -> DmrconfCli:
    return DmrconfCli((sys.executable, "-c", f"import sys\n{script}"))


def test_verify_calls_dmrconf_verify_with_the_radio_and_the_file(tmp_path: Path) -> None:
    record = tmp_path / "argv"
    stand_in(f"open({str(record)!r}, 'w').write(repr(sys.argv[1:]))").verify("d878uv2", tmp_path / "c.yaml")
    assert record.read_text() == repr(["verify", "--radio", "d878uv2", str(tmp_path / "c.yaml")])


def test_a_refusal_raises_the_tools_message_without_colours(tmp_path: Path) -> None:
    dmrconf = stand_in(
        "sys.stdout.write('progress')\n"
        r"sys.stderr.write('\x1b[1;31mFrequency 1000MHz is outside of allowed frequency ranges.\x1b[0m\n')"
        "\nsys.exit(1)"
    )
    with pytest.raises(CheckError) as error:
        dmrconf.verify("d878uv2", tmp_path / "c.yaml")
    assert str(error.value) == "dmrconf verify failed:\nFrequency 1000MHz is outside of allowed frequency ranges."


def test_a_refusal_on_stdout_only_raises_that_message(tmp_path: Path) -> None:
    with pytest.raises(CheckError) as error:
        stand_in("print('Unknown radio key.')\nsys.exit(255)").verify("nope", tmp_path / "c.yaml")
    assert str(error.value) == "dmrconf verify failed:\nUnknown radio key."


def test_a_silent_refusal_raises_the_exit_status(tmp_path: Path) -> None:
    with pytest.raises(CheckError) as error:
        stand_in("sys.exit(3)").verify("d878uv2", tmp_path / "c.yaml")
    assert str(error.value) == "dmrconf verify failed:\nexit status 3"


def test_a_missing_dmrconf_says_it_is_not_installed(tmp_path: Path) -> None:
    missing = str(tmp_path / "no-dmrconf")
    with pytest.raises(CheckError) as error:
        DmrconfCli((missing,)).verify("d878uv2", tmp_path / "c.yaml")
    assert str(error.value) == f"dmrconf is not installed: {missing} not found"
