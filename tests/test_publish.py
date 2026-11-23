"""`fleet publish` and `fleet applied` (R12) on a copy of the example data root."""

import hashlib
import shutil
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from radio_fleet import record
from radio_fleet.cli import main

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
DAY = date(2026, 5, 6)


@pytest.fixture
def data(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    """The example data root with its equipment directory and a build of the uv5r-mini and the rt95."""
    root = tmp_path / "data"
    shutil.copytree(EXAMPLES, root)
    (root / "equipment").mkdir()
    for radio in ("uv5r-mini", "rt95"):
        assert main(["build", "--data", str(root), "--radio", radio]) == 0
    capsys.readouterr()
    return root


def run(data: Path, *args: str) -> int:
    return main([args[0], "--data", str(data), *args[1:]], today=DAY)


def test_publish_copies_the_build_to_the_dated_equipment_directory(
    data: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(data, "publish", "uv5r-mini") == 0
    target = data / "equipment" / "uv5r-mini" / "generated" / "2026-05-06"
    assert capsys.readouterr().out == f"uv5r-mini: {target}\n"
    build = data / "build" / "uv5r-mini"
    assert sorted(path.name for path in target.iterdir()) == ["selection.yaml", "uv5r-mini.csv"]
    for path in target.iterdir():
        assert path.read_bytes() == (build / path.name).read_bytes()


def test_publish_copies_to_the_equipment_dir_of_the_profile(data: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fleet_file = data / "fleet.yaml"
    profile = "    renderer: chirp\n"
    fleet_file.write_text(fleet_file.read_text().replace(profile, f"{profile}    equipment_dir: baofeng/mini\n", 1))
    assert main(["--data", str(data), "publish", "uv5r-mini"], today=DAY) == 0
    target = data / "equipment" / "baofeng" / "mini" / "generated" / "2026-05-06"
    assert capsys.readouterr().out == f"uv5r-mini: {target}\n"
    assert sorted(path.name for path in target.iterdir()) == ["selection.yaml", "uv5r-mini.csv"]
    assert not (data / "equipment" / "uv5r-mini").exists()


@pytest.mark.parametrize("command", ["publish", "applied"])
def test_publish_and_applied_take_no_snapshot_directory(data: Path, command: str) -> None:
    with pytest.raises(SystemExit):
        run(data, command, "--snapshots", str(data / "snapshots"), "uv5r-mini")


def test_publish_refuses_an_existing_target_and_leaves_it_unchanged(
    data: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = data / "equipment" / "uv5r-mini" / "generated" / "2026-05-06"
    target.mkdir(parents=True)
    (target / "notes.txt").write_text("hand-made")
    assert run(data, "publish", "uv5r-mini") == 1
    assert capsys.readouterr().err == f"fleet publish: {target} exists; publish never overwrites a file\n"
    assert [path.name for path in target.iterdir()] == ["notes.txt"]
    assert (target / "notes.txt").read_text() == "hand-made"


def test_a_failed_copy_leaves_no_target_and_a_later_publish_succeeds(
    data: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    copy = shutil.copyfileobj
    calls = []

    def fail_second(*args: Any) -> None:
        calls.append(args)
        if len(calls) == 2:
            raise OSError("No space left on device")
        copy(*args)

    monkeypatch.setattr(shutil, "copyfileobj", fail_second)
    target = data / "equipment" / "uv5r-mini" / "generated" / "2026-05-06"
    assert run(data, "publish", "uv5r-mini") == 1
    assert capsys.readouterr().err == (
        f"fleet publish: copying to {target} failed, nothing published: No space left on device\n"
    )
    assert not target.exists()

    monkeypatch.setattr(shutil, "copyfileobj", copy)
    assert run(data, "publish", "uv5r-mini") == 0
    assert sorted(path.name for path in target.iterdir()) == ["selection.yaml", "uv5r-mini.csv"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("", "{fleet}: `fleet publish` needs the equipment directory: equipment: DIR"),
        ("equipment: elsewhere\n", "no equipment directory {data}/elsewhere"),
    ],
)
def test_publish_needs_an_existing_equipment_directory(
    data: Path, change: str, message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    fleet_file = data / "fleet.yaml"
    text = fleet_file.read_text()
    fleet_file.write_text(text.replace("equipment: equipment\n", change))
    assert run(data, "publish", "uv5r-mini") == 1
    expected = message.format(fleet=fleet_file, data=data)
    assert capsys.readouterr().err == f"fleet publish: {expected}\n"


@pytest.mark.parametrize("command", ["publish", "applied"])
def test_a_radio_without_a_complete_build_is_refused(
    data: Path, command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    build = data / "build" / "ft5d"
    build.mkdir()
    (build / "ft5d.csv").write_text("left over")
    assert run(data, command, "ft5d") == 1
    assert capsys.readouterr().err == (
        f"fleet {command}: no build of ft5d in {build}; run `fleet build --radio ft5d`\n"
    )
    assert not (data / "equipment" / "ft5d").exists()
    assert not (data / "applied.yaml").exists()


@pytest.mark.parametrize("command", ["publish", "applied"])
def test_an_unknown_radio_is_refused(data: Path, command: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(data, command, "../build") == 1
    assert "no radio '../build'; radios: d878uv2plus, " in capsys.readouterr().err


def test_applied_records_the_digest_and_prints_the_tag_command_without_running_git(
    data: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_process(*args: object, **kwargs: object) -> None:
        raise AssertionError("fleet applied runs no process")

    monkeypatch.setattr(subprocess, "run", no_process)
    monkeypatch.setattr(subprocess, "Popen", no_process)
    build = data / "build" / "uv5r-mini"
    files = [build / "selection.yaml", build / "uv5r-mini.csv"]
    expected = hashlib.sha256()
    for file in files:
        expected.update(file.name.encode() + b"\0" + hashlib.sha256(file.read_bytes()).digest())
    digest = f"sha256:{expected.hexdigest()}"

    assert run(data, "applied", "uv5r-mini") == 0

    applied_file = data / "applied.yaml"
    assert capsys.readouterr().out == (f"uv5r-mini: {digest} in {applied_file}\ngit tag applied/uv5r-mini/2026-05-06\n")
    entry = record.load_applied(applied_file)["uv5r-mini"]
    assert (entry.date, entry.digest) == ("2026-05-06", digest)
    built = record.read_build(build)
    assert built is not None and entry.channels == built.channels
    report = (data / "build" / "CHANGES.md").read_text(encoding="utf-8")
    assert "## uv5r-mini: Baofeng UV-5R mini (chirp)\n\nAgainst the build applied on 2026-05-06: " in report


def test_applied_keeps_the_other_radios_and_replaces_its_own(data: Path) -> None:
    assert main(["applied", "--data", str(data), "rt95"], today=date(2026, 1, 1)) == 0
    assert run(data, "applied", "uv5r-mini") == 0
    (data / "build" / "uv5r-mini" / "uv5r-mini.csv").write_text("changed")
    assert main(["applied", "--data", str(data), "uv5r-mini"], today=date(2026, 6, 7)) == 0
    entries = record.load_applied(data / "applied.yaml")
    assert list(entries) == ["rt95", "uv5r-mini"]
    assert entries["rt95"].date == "2026-01-01"
    assert entries["uv5r-mini"].date == "2026-06-07"
    assert entries["uv5r-mini"].digest == record.digest(data / "build" / "uv5r-mini")
