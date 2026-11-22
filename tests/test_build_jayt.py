"""The jayt renderer and its build (R8, R10) with a fake jayt and a synthetic FT-3185 document."""

import copy
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from radio_fleet import fleet
from radio_fleet.cli import main
from radio_fleet.config import ConfigError
from radio_fleet.jayt import JaytError, MissingCommand

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"

# What `jayt export --format yaml` gives for a synthetic FT-3185 image: one old channel and other parts.
DOCUMENT: dict[str, Any] = {
    "channels": [{"slot": 0, "name": "OLD", "freq_hz": 144_800_000, "mode": "FM", "used": True}],
    "home": [{"index": 0, "freq_hz": 144_000_000, "mode": "FM", "tone": "OFF"}],
    "model_code": "AH087N",
    "pms": [],
    "radio": "FT-3185",
    "settings": {"apo": "OFF", "beep": "LOW", "dt_mem": ["", ""], "pag_cdr": "05.47"},
    "source": {"file": {"sha256": "0" * 64, "size": 6356}, "format": "ft3185_image"},
    "special": {"wx": [{"name": None}]},
}


class FakeJayt:
    def __init__(self, document: dict[str, Any] = DOCUMENT, fail: str = "", missing: str = "") -> None:
        self.document = document
        self.fail = fail
        self.missing = missing
        self.calls: list[tuple[str, ...]] = []
        self.imported: dict[str, Any] = {}

    def export(self, file: Path, document: Path) -> None:
        self._call("export", file.name)
        document.write_text(yaml.safe_dump(self.document, sort_keys=False), encoding="utf-8")

    def import_(self, document: Path, output: Path, template: Path) -> None:
        self._call("import", document.name, output.name, template.name)
        self.imported = yaml.safe_load(document.read_text(encoding="utf-8"))
        output.write_bytes(b"synthetic radio file")

    def check(self, file: Path) -> None:
        self._call("check", file.name)
        assert file.read_bytes() == b"synthetic radio file"

    def _call(self, command: str, *args: str) -> None:
        self.calls.append((command, *args))
        if command == self.missing:
            raise MissingCommand(f"jayt 0000000 lacks `jayt {command}` as called")
        if command == self.fail:
            raise JaytError(f"jayt 0000000 {command} failed:\nslot 3: frequency outside the band")


@pytest.fixture
def data(tmp_path: Path) -> Path:
    """The example data root with a base for the FT-3185 (synthetic bytes; the fake reads none)."""
    root = tmp_path / "data"
    shutil.copytree(EXAMPLES, root)
    (root / "bases" / "jayt").mkdir()
    (root / "bases" / "jayt" / "ft3185.img").write_bytes(b"synthetic base")
    fleet_file = root / "fleet.yaml"
    profile = "    renderer: jayt\n"
    fleet_file.write_text(fleet_file.read_text().replace(profile, profile + "    base: bases/jayt/ft3185.img\n", 1))
    return root


def build(data: Path, jayt: FakeJayt) -> int:
    return main(["build", "--data", str(data), "--radio", "ft3185"], jayt=jayt)


def test_the_build_edits_the_channels_and_calls_import_and_check(
    data: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    jayt = FakeJayt()
    assert build(data, jayt) == 0
    output = data / "build" / "ft3185" / "ft3185.img"
    assert capsys.readouterr().out == f"ft3185: {output}\n"
    assert jayt.calls == [
        ("export", "ft3185.img"),
        ("import", "ft3185.jayt.yaml", "ft3185.img", "ft3185.img"),
        ("check", "ft3185.img"),
    ]
    assert output.read_bytes() == b"synthetic radio file"
    document = yaml.safe_load((data / "build" / "ft3185" / "ft3185.jayt.yaml").read_text())
    assert document == jayt.imported
    assert {key: value for key, value in document.items() if key != "channels"} == {
        key: value for key, value in DOCUMENT.items() if key != "channels"
    }
    assert document["channels"] == [
        {"slot": 0, "name": "2m Cal", "freq_hz": 145_500_000, "tx_hz": 145_500_000, "rpt": "SIMP", "offset_hz": 0,
         "mode": "FM", "tone": "OFF"},
        {"slot": 1, "name": "70cm C", "freq_hz": 433_500_000, "tx_hz": 433_500_000, "rpt": "SIMP", "offset_hz": 0,
         "mode": "FM", "tone": "OFF"},
        {"slot": 2, "name": "XX1AA", "freq_hz": 145_600_000, "tx_hz": 145_000_000, "rpt": "-", "offset_hz": 600_000,
         "mode": "FM-N", "tone": "TSQ", "ctcss_hz": "88.5", "ctcss_dec_hz": "88.5"},
        {"slot": 3, "name": "XX1CC", "freq_hz": 438_625_000, "tx_hz": 431_025_000, "rpt": "-",
         "offset_hz": 7_600_000, "mode": "FM", "tone": "DCS", "dcs": "023", "dcs_dec": "023"},
        {"slot": 4, "name": "XX3DD", "freq_hz": 145_662_500, "tx_hz": 145_062_500, "rpt": "-", "offset_hz": 600_000,
         "mode": "FM", "tone": "ENC", "ctcss_hz": "123.0"},
    ]  # fmt: skip


def test_the_profile_power_reaches_the_channel(data: Path) -> None:
    fleet_file = data / "fleet.yaml"
    base = "    base: bases/jayt/ft3185.img\n"
    fleet_file.write_text(fleet_file.read_text().replace(base, base + "    power: High\n"))
    jayt = FakeJayt()
    assert build(data, jayt) == 0
    assert {channel["tx_power"] for channel in jayt.imported["channels"]} == {"HIGH"}


def test_a_failing_check_fails_the_build_names_the_radio_and_removes_its_output(
    data: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert build(data, FakeJayt()) == 0
    capsys.readouterr()
    assert build(data, FakeJayt(fail="check")) == 1
    assert capsys.readouterr().err == (
        "fleet build: ft3185: jayt 0000000 check failed:\nslot 3: frequency outside the band\n"
    )
    assert not list((data / "build" / "ft3185").iterdir())


@pytest.mark.parametrize("command", ["import", "check"])
def test_a_missing_jayt_command_stops_after_the_document_and_names_the_gap(
    data: Path, command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert build(data, FakeJayt(missing=command)) == 1
    document = data / "build" / "ft3185" / "ft3185.jayt.yaml"
    assert capsys.readouterr().err == (
        f"fleet build: ft3185: jayt 0000000 lacks `jayt {command}` as called\n"
        f"the radio document is written to {document}\n"
    )
    assert yaml.safe_load(document.read_text())["channels"][0]["name"] == "2m Cal"
    assert not (data / "build" / "ft3185" / "ft3185.img").exists()


def test_a_document_of_another_radio_fails_the_build(data: Path, capsys: pytest.CaptureFixture[str]) -> None:
    other = copy.deepcopy(DOCUMENT) | {"radio": "FTX-1"}
    assert build(data, FakeJayt(other)) == 1
    assert capsys.readouterr().err == (
        f"fleet build: ft3185: {data / 'bases' / 'jayt' / 'ft3185.img'}: "
        "the jayt renderer writes FT-3185 channels, not those of radio 'FTX-1'\n"
    )


def test_a_tone_the_radio_cannot_carry_fails_the_build(data: Path, capsys: pytest.CaptureFixture[str]) -> None:
    own = data / "sources" / "own" / "simplex.yaml"
    own.write_text(
        own.read_text().replace(
            "{name: 2m Call, rx: 145.500, mode: FM}", "{name: 2m Call, rx: 145.500, mode: FM, tone_rx: {ctcss: 88.5}}"
        )
    )
    assert build(data, FakeJayt()) == 1
    assert capsys.readouterr().err.endswith(
        "channel 2m Cal: the FT-3185 cannot carry tone TX none, tone RX CTCSS 88.5\n"
    )


def test_a_jayt_radio_needs_a_base_and_the_jayt_tool(data: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["build", "--data", str(data), "--radio", "ftx1"], jayt=FakeJayt()) == 1
    assert (
        capsys.readouterr().err == "fleet build: ftx1: the jayt renderer needs a base (the radio file) in the profile\n"
    )
    fleet_file = data / "fleet.yaml"
    fleet_file.write_text(fleet_file.read_text().replace("  jayt: {path: tools/jayt, commit: '0000000'}\n", ""))
    assert main(["build", "--data", str(data), "--radio", "ft3185"]) == 1
    assert capsys.readouterr().err == (
        "fleet build: ft3185: the jayt renderer needs tools.jayt (path and commit) in the fleet file\n"
    )


def test_the_jayt_path_is_relative_to_the_data_root_and_the_commit_is_checked(data: Path) -> None:
    fleet_file = data / "fleet.yaml"
    tool = fleet.load(fleet_file, data).jayt
    assert tool == fleet.Tool(data / "tools" / "jayt", "0000000")
    fleet_file.write_text(fleet_file.read_text().replace("commit: '0000000'", "commit: main"))
    with pytest.raises(ConfigError, match=r"tools\.jayt\.commit: expected a git commit: 7 to 40 hex digits"):
        fleet.load(fleet_file, data)


def test_a_bare_jayt_path_is_the_file_in_the_data_root_not_a_path_lookup(
    data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fleet_file = data / "fleet.yaml"
    fleet_file.write_text(fleet_file.read_text().replace("path: tools/jayt", "path: jayt"))
    monkeypatch.chdir(data)
    tool = fleet.load(Path("fleet.yaml"), Path(".")).jayt
    assert tool is not None
    assert tool.path == data.absolute() / "jayt"
