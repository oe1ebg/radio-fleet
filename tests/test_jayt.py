"""The jayt adapter's calls and its translation of the tool's outcome (R8, R10), with a stand-in jayt."""

import os
import sys
from pathlib import Path

import pytest

from radio_fleet.jayt import JaytCli, JaytError, MissingCommand


def stand_in(tmp_path: Path, script: str) -> JaytCli:
    executable = tmp_path / "jayt"
    executable.write_text(f"#!{sys.executable}\nimport sys\n{script}\n")
    os.chmod(executable, 0o755)
    return JaytCli(executable, "0000000")


def test_the_commands_and_their_arguments(tmp_path: Path) -> None:
    record = tmp_path / "argv"
    jayt = stand_in(tmp_path, f"open({str(record)!r}, 'a').write(repr(sys.argv[1:]) + '\\n')")
    base, document, output = tmp_path / "base.img", tmp_path / "doc.yaml", tmp_path / "out.img"
    jayt.export(base, document)
    jayt.import_(document, output, base)
    jayt.check(output)
    assert record.read_text().splitlines() == [
        repr(["export", str(base), "--format", "yaml", "-o", str(document)]),
        repr(["import", str(document), "-o", str(output), "--template", str(base)]),
        repr(["check", str(output)]),
    ]


def test_a_refusal_raises_the_tools_message(tmp_path: Path) -> None:
    jayt = stand_in(tmp_path, "print('out.img: slot 3: frequency outside the band')\nsys.exit(1)")
    with pytest.raises(JaytError) as error:
        jayt.check(tmp_path / "out.img")
    assert str(error.value) == "jayt 0000000 check failed:\nout.img: slot 3: frequency outside the band"
    assert not isinstance(error.value, MissingCommand)


@pytest.mark.parametrize(
    "usage", ["error: unrecognized subcommand 'import'", "error: unexpected argument '--template' found"]
)
def test_a_command_or_option_jayt_lacks_is_a_gap(tmp_path: Path, usage: str) -> None:
    jayt = stand_in(tmp_path, f"sys.stderr.write({usage + chr(10) + chr(10) + 'Usage: jayt'!r})\nsys.exit(2)")
    with pytest.raises(MissingCommand) as error:
        jayt.import_(tmp_path / "doc.yaml", tmp_path / "out.img", tmp_path / "base.img")
    assert str(error.value) == f"jayt 0000000 lacks `jayt import` as called:\n{usage}\n\nUsage: jayt"


def test_a_missing_jayt_names_its_path(tmp_path: Path) -> None:
    missing = tmp_path / "no-jayt"
    with pytest.raises(JaytError) as error:
        JaytCli(missing, "0000000").check(tmp_path / "out.img")
    assert str(error.value) == f"jayt 0000000 is not installed: no file {missing}"
