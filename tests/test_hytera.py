"""Hytera renderer, build and Hytera tool adapter (R9, R10), with a fake tool and a synthetic export."""

import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from radio_fleet import fleet, snapshot, sources
from radio_fleet.cli import main
from radio_fleet.config import ConfigError
from radio_fleet.dmrconf import CheckError
from radio_fleet.hytera_tool import HyteraCli
from radio_fleet.model import Channel, Ctcss, Mode
from radio_fleet.render import hytera
from radio_fleet.selection import Selection, Zone, select

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"

# A synthetic lossless export in the shape of the Hytera tool's: a digital channel with the name of a
# generated one, a hand-made analog channel, a group call contact for TG9 to reuse, a private call with a
# talkgroup's number, an RX group list and a zone named like a generated one. `rebuild` holds a hex row
# that YAML would read as a number if it were written back unquoted.
EXPORT = """\
format: synthetic-export/1
source: {file: BASE_PATH, modules: [], sha256: '00'}
model: {name: HP785}
radio: {radio_name: XX0SYN}
settings:
  menu: {language: English}
tables:
  digital_channels:
    node: 38
    entries:
      - index: 0
        logical: 1
        name: DMR Simplex
        rx_hz: 433450000
        rx_mhz: '433.45'
        tx_hz: 433450000
        tx_mhz: '433.45'
        settings: {color_code: 3, slot_operation: Slot 2, power_level: Low, vox: false}
        references:
          tx_contact: {index: 1, name: Local 9}
          rx_group_list: {index: 1, name: Local}
        unknown_bytes: {}
  analog_channels:
    node: 39
    entries:
      - index: 0
        logical: 1
        name: Hand FM
        rx_hz: 446006250
        tx_hz: 446006250
        settings: {channel_spacing: '12.5', tx_tone: {mode: none, default_ctcss_hz: 67.0}}
        unknown_bytes: {}
  contacts:
    node: 42
    entries:
      - {index: 0, name: Local 9, call_type: group, dmr_id: 9, link_a: 1, link_b: 1, unknown_hex: ''}
      - {index: 1, name: Person, call_type: private, dmr_id: 232, link_a: 0, link_b: 0, unknown_hex: ''}
  rx_groups:
    node: 108
    entries:
      - index: 0
        name: Local
        members: [{contact_position: 1, name: Local 9, call_id: 9}]
        unknown_hex: ''
  zones:
    node: 36
    entries:
      - index: 0
        name: FM
        members: [{kind: analog, channel_position: 1, name: Hand FM}]
        unknown_hex: ''
rebuild: {format_version: 2, raw: {image: {'0x00000000': '0012'}}}
"""

HAND_FM = yaml.safe_load(EXPORT)["tables"]["analog_channels"]["entries"][0]
NO_TONE = {"mode": "none", "default_ctcss_hz": None}


def example_selection(radio_id: str = "hp785") -> tuple[Selection, sources.Sources]:
    own = sources.load(EXAMPLES / "sources")
    radio = fleet.load(EXAMPLES / "fleet.yaml", EXAMPLES).radios[radio_id]
    upstream = snapshot.read(snapshot.path_for(EXAMPLES / "snapshots", "oevsv-repeater-db"))
    return select(radio, upstream, own), own


def tables(text: str) -> dict[str, list[dict[str, Any]]]:
    document = yaml.safe_load(text)
    return {key: table["entries"] for key, table in document["tables"].items()}


def test_the_render_edits_channels_contacts_rx_groups_and_zones() -> None:
    selection, own = example_selection()
    assert tables(hytera.render(selection, own, EXPORT)) == {
        "digital_channels": [
            {
                "index": 0,
                "logical": 1,
                "name": "DMR Simplex",
                "rx_hz": 433_450_000,
                "tx_hz": 433_450_000,
                "settings": {"color_code": 1, "slot_operation": "Slot 1", "power_level": "High", "vox": False},
                "references": {"tx_contact": {"index": 1, "name": "TG99"}, "rx_group_list": {"index": 1, "name": None}},
                "unknown_bytes": {},
            },
            {
                "name": "XX1BB TS1 TG232",
                "rx_hz": 438_962_500,
                "tx_hz": 431_462_500,
                "settings": {"power_level": "High", "color_code": 1, "slot_operation": "Slot 1"},
                "references": {"tx_contact": {"name": "TG232"}, "rx_group_list": {"name": "Austria"}},
            },
            {
                "name": "XX1BB TS2 TG9",
                "rx_hz": 438_962_500,
                "tx_hz": 431_462_500,
                "settings": {"power_level": "High", "color_code": 1, "slot_operation": "Slot 2"},
                "references": {"tx_contact": {"name": "Local 9"}, "rx_group_list": {"name": None}},
            },
        ],
        "analog_channels": [
            HAND_FM,
            {
                "name": "70cm Call",
                "rx_hz": 433_500_000,
                "tx_hz": 433_500_000,
                "settings": {
                    "power_level": "High",
                    "channel_spacing": "25",
                    "tx_tone": NO_TONE,
                    "rx_tone": NO_TONE,
                    "rx_squelch_mode": "Carrier",
                },
            },
            {
                "name": "XX1CC",
                "rx_hz": 438_625_000,
                "tx_hz": 431_025_000,
                "settings": {
                    "power_level": "High",
                    "channel_spacing": "25",
                    "tx_tone": {"mode": "CDCSS", "code": "023"},
                    "rx_tone": NO_TONE,
                    "rx_squelch_mode": "Carrier",
                },
            },
        ],
        "contacts": [
            {
                "index": 0,
                "name": "Local 9",
                "call_type": "group",
                "dmr_id": 9,
                "link_a": 1,
                "link_b": 1,
                "unknown_hex": "",
            },
            {
                "index": 1,
                "name": "Person",
                "call_type": "private",
                "dmr_id": 232,
                "link_a": 0,
                "link_b": 0,
                "unknown_hex": "",
            },
            {"name": "TG99", "call_type": "group", "dmr_id": 99},
            {"name": "TG232", "call_type": "group", "dmr_id": 232},
        ],
        "rx_groups": [
            {
                "index": 0,
                "name": "Local",
                "members": [{"contact_position": 1, "name": "Local 9", "call_id": 9}],
                "unknown_hex": "",
            },
            {"name": "Austria", "members": [{"name": "TG232"}, {"name": "Local 9"}]},
        ],
        "zones": [
            {
                "index": 0,
                "name": "FM",
                "members": [{"kind": "analog", "name": "70cm Call"}, {"kind": "analog", "name": "XX1CC"}],
                "unknown_hex": "",
            },
            {
                "name": "Simplex",
                "members": [{"kind": "analog", "name": "70cm Call"}, {"kind": "digital", "name": "DMR Simplex"}],
            },
            {
                "name": "DMR",
                "members": [
                    {"kind": "digital", "name": "DMR Simplex"},
                    {"kind": "digital", "name": "XX1BB TS1 TG232"},
                    {"kind": "digital", "name": "XX1BB TS2 TG9"},
                ],
            },
        ],
    }


def test_everything_but_the_edited_tables_is_unchanged() -> None:
    selection, own = example_selection()
    out = hytera.render(selection, own, EXPORT)
    base, rendered = yaml.safe_load(EXPORT), yaml.safe_load(out)
    for document in (base, rendered):
        for table in document["tables"].values():
            del table["entries"]
    assert rendered == base
    assert "'0x00000000': '0012'" in out


def test_a_member_and_a_tone_the_base_already_has_are_kept() -> None:
    selection, own = example_selection()
    fm = Channel("Hand FM", 446_006_250, 446_006_250, Mode.FM, tone_rx=Ctcss(88.5), bandwidth_hz=12_500)
    zone = Zone("FM", (fm,))
    out = hytera.render(Selection(selection.radio, (fm,), (zone,), (), ()), own, EXPORT)
    entry = tables(out)["analog_channels"][0]
    assert entry["settings"] == {
        "channel_spacing": "12.5",
        "tx_tone": {"mode": "none", "default_ctcss_hz": 67.0},
        "rx_tone": {"mode": "CTCSS", "hz": 88.5},
        "rx_squelch_mode": "CTCSS/CDCSS",
    }
    assert tables(out)["zones"][0]["members"] == [{"kind": "analog", "channel_position": 1, "name": "Hand FM"}]


@pytest.mark.parametrize(
    ("channels", "message"),
    [
        ((Channel("XX0FM", 433_500_000, 433_500_000, Mode.FM, power="5W"),), "power '5W' is not one of High"),
        ((Channel("XX0YS", 433_500_000, 433_500_000, Mode.C4FM),), "Hytera carries FM and DMR, not C4FM"),
        (
            (Channel("XX0FM", 433_500_000, 433_500_000, Mode.FM), Channel("XX0FM", 433_525_000, 433_525_000, Mode.FM)),
            "two analog channels are named 'XX0FM'",
        ),
        (
            (Channel("XX0DM", 433_450_000, 433_450_000, Mode.DMR, tx_talkgroup="TG232"),),
            "contact 'TG232' of the base is not the group call 232",
        ),
    ],
)
def test_a_channel_the_file_cannot_take_is_refused(channels: tuple[Channel, ...], message: str) -> None:
    selection, own = example_selection()
    export = EXPORT.replace("name: Person", "name: TG232")
    with pytest.raises(hytera.RenderError, match=message):
        hytera.render(Selection(selection.radio, channels, (), (), ()), own, export)


@pytest.mark.parametrize(
    ("export", "message"),
    [("tables: {zones: []}\n", "not a Hytera codeplug"), ("tables: [\n", "not valid YAML")],
)
def test_an_export_that_is_not_a_codeplug_is_refused(export: str, message: str) -> None:
    selection, own = example_selection()
    with pytest.raises(hytera.RenderError, match=message):
        hytera.render(selection, own, export)


class FakeHytera:
    """Exports EXPORT with the base path in it, as the real export names its source file."""

    def __init__(self, error: str | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, ...]] = []
        self.edited = ""

    def export(self, base: Path, document: Path) -> None:
        self.calls.append(("export", str(base), document.name))
        document.write_text(EXPORT.replace("BASE_PATH", str(base)), encoding="utf-8")

    def import_(self, document: Path, output: Path, base: Path, factory: Path) -> None:
        self.calls.append(("import", document.name, output.name, str(base), str(factory)))
        self.edited = document.read_text(encoding="utf-8")
        if self.error is not None:
            raise CheckError(self.error)
        output.write_bytes(b"synthetic rcdx")


@pytest.fixture
def data(tmp_path: Path) -> Path:
    """The example data root with the Hytera files of the HP785 outside it, as the owner keeps them."""
    shutil.copytree(EXAMPLES, tmp_path / "data")
    (tmp_path / "hytera").mkdir()
    for name in ("hp785.rcdx", "hp785-factory.rcdx"):
        (tmp_path / "hytera" / name).write_bytes(b"synthetic")
    fleet_file = tmp_path / "data" / "fleet.yaml"
    fleet_file.write_text(
        fleet_file.read_text()
        .replace("    # base: ../hytera/hp785.rcdx", "    base: ../hytera/hp785.rcdx")
        .replace("    # factory: ../hytera/hp785-factory.rcdx", "    factory: ../hytera/hp785-factory.rcdx")
    )
    return tmp_path / "data"


def output_of(data: Path) -> Path:
    return data / "build" / "hp785" / "hp785.rcdx"


def test_build_exports_edits_and_imports_and_keeps_only_the_checked_file(
    data: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    tool = FakeHytera()
    assert main(["build", "--data", str(data), "--radio", "hp785"], hytera=tool) == 0
    base, factory = data / ".." / "hytera" / "hp785.rcdx", data / ".." / "hytera" / "hp785-factory.rcdx"
    assert tool.calls == [
        ("export", str(base), "base.yaml"),
        ("import", "edited.yaml", "hp785.rcdx", str(base), str(factory)),
    ]
    selection, own = example_selection()
    assert tool.edited == hytera.render(selection, own, EXPORT.replace("BASE_PATH", str(base)))
    assert capsys.readouterr().out == f"hp785: {output_of(data)}\n"
    assert [path.name for path in (data / "build").rglob("*") if path.is_file()] == ["hp785.rcdx"]
    assert output_of(data).read_bytes() == b"synthetic rcdx"


def test_a_failing_import_check_fails_the_build_names_the_radio_and_removes_its_output(
    data: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["build", "--data", str(data), "--radio", "hp785"], hytera=FakeHytera()) == 0
    capsys.readouterr()
    message = "the Hytera tool's import failed:\ntables.zones.entries[1].members[0]: no digital channel named 'X'"
    assert main(["build", "--data", str(data), "--radio", "hp785"], hytera=FakeHytera(message)) == 1
    assert capsys.readouterr().err == f"fleet build: hp785: {message}\n"
    assert not output_of(data).exists()


def test_a_hytera_radio_without_base_factory_or_tool_fails_the_build(
    data: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["build", "--data", str(data), "--radio", "hm785"], hytera=FakeHytera()) == 1
    assert (
        capsys.readouterr().err == "fleet build: hm785: the hytera renderer needs a base and a factory in the profile\n"
    )
    fleet_file = data / "fleet.yaml"
    fleet_file.write_text(re.sub(r"  hytera:\n(    .*\n)+", "", fleet_file.read_text()))
    assert main(["build", "--data", str(data), "--radio", "hp785"]) == 1
    assert capsys.readouterr().err == (
        "fleet build: hp785: the hytera renderer needs tools.hytera (export and import commands) in the fleet file\n"
    )


def test_a_missing_factory_is_refused_with_its_path(data: Path) -> None:
    fleet_file = data / "fleet.yaml"
    (data / ".." / "hytera" / "hp785-factory.rcdx").unlink()
    with pytest.raises(ConfigError, match=r"radios\.hp785\.factory: no file \S*hytera/hp785-factory\.rcdx"):
        fleet.load(fleet_file, data).check_references(sources.load(data / "sources"))


def test_only_a_hytera_radio_takes_a_factory_image(data: Path) -> None:
    fleet_file = data / "fleet.yaml"
    fleet_file.write_text(
        fleet_file.read_text().replace("renderer: chirp\n", "renderer: chirp\n    factory: x.rcdx\n", 1)
    )
    with pytest.raises(ConfigError, match=r"radios\.uv5r-mini\.factory: only the hytera renderer takes a factory"):
        fleet.load(fleet_file, data)


def test_the_example_fleet_names_no_hytera_file() -> None:
    radios = fleet.load(EXAMPLES / "fleet.yaml", EXAMPLES).radios
    hytera_radios = [radio for radio in radios.values() if radio.renderer is fleet.Renderer.HYTERA]
    assert [radio.id for radio in hytera_radios] == ["hp785", "hm785"]
    assert all(radio.base is None and radio.factory is None for radio in hytera_radios)


# A stand-in for the Hytera tool: it records its arguments in calls.jsonl of its working directory and runs
# the Python statement given as its first argument, which writes the export or the rebuilt file, or fails.
STAND_IN = """\
import json, pathlib, sys
pathlib.Path("calls.jsonl").open("a").write(json.dumps(sys.argv[1:]) + "\\n")
command, *args = sys.argv[1:]
exec(command)
"""
EXPORT_SCRIPT = f"pathlib.Path(args[-1]).write_text({EXPORT!r})"
IMPORT_SCRIPT = "pathlib.Path(args[1]).write_bytes(b'synthetic rcdx')"


def stand_in(root: Path, export: str = EXPORT_SCRIPT, import_: str = IMPORT_SCRIPT) -> tuple[list[str], list[str]]:
    """Write the stand-in to `root` and return its export and import command lines."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "tool.py").write_text(STAND_IN)
    return (
        [sys.executable, "tool.py", export, "--in={base}", "{document}"],
        [sys.executable, "tool.py", import_, "{document}", "{output}", "--secrets={base}", "--defaults={factory}"],
    )


def calls(root: Path) -> list[list[str]]:
    return [json.loads(line)[1:] for line in (root / "calls.jsonl").read_text().splitlines()]


def test_build_runs_the_configured_commands_in_the_data_root(data: Path) -> None:
    export, import_ = stand_in(data)
    fleet_file = data / "fleet.yaml"
    text = re.sub(r"  hytera:\n(    .*\n)+", "", fleet_file.read_text())
    fleet_file.write_text(
        text.replace("tools:\n", f"tools:\n  hytera: {json.dumps({'export': export, 'import': import_})}\n")
    )
    assert main(["build", "--data", str(data), "--radio", "hp785"]) == 0
    base = (data / ".." / "hytera" / "hp785.rcdx").absolute()
    factory = (data / ".." / "hytera" / "hp785-factory.rcdx").absolute()
    (exported, document), (edited, output, secrets, defaults) = calls(data)
    assert (exported, Path(document).name) == (f"--in={base}", "base.yaml")
    assert (Path(edited).name, Path(output).name) == ("edited.yaml", "hp785.rcdx")
    assert (secrets, defaults) == (f"--secrets={base}", f"--defaults={factory}")
    assert output_of(data).read_bytes() == b"synthetic rcdx"


def test_the_adapter_fills_the_placeholders_with_absolute_paths(tmp_path: Path) -> None:
    tool = HyteraCli(*stand_in(tmp_path, "", ""), tmp_path)
    base, factory = Path("relative", "hp785.rcdx"), tmp_path / "factory.rcdx"
    tool.export(base, tmp_path / "base.yaml")
    tool.import_(tmp_path / "edited.yaml", tmp_path / "out.rcdx", base, factory)
    assert calls(tmp_path) == [
        [f"--in={base.absolute()}", str(tmp_path / "base.yaml")],
        [
            str(tmp_path / "edited.yaml"),
            str(tmp_path / "out.rcdx"),
            f"--secrets={base.absolute()}",
            f"--defaults={factory}",
        ],
    ]


@pytest.mark.parametrize(
    ("script", "message"),
    [
        (
            "sys.stderr.write('tables.contacts.entries[3].link_a: read-only in this version\\n'); sys.exit(1)",
            "the Hytera tool's import failed:\ntables.contacts.entries[3].link_a: read-only in this version",
        ),
        ("sys.exit(2)", "the Hytera tool's import failed:\nexit status 2"),
    ],
)
def test_a_failing_tool_raises_its_message(tmp_path: Path, script: str, message: str) -> None:
    tool = HyteraCli(*stand_in(tmp_path, "", script), tmp_path)
    with pytest.raises(CheckError) as error:
        tool.import_(tmp_path / "e.yaml", tmp_path / "o.rcdx", tmp_path / "b", tmp_path / "f")
    assert str(error.value) == message


def test_a_missing_tool_says_it_cannot_run(tmp_path: Path) -> None:
    tool = HyteraCli(["no-such-hytera-tool", "{base}", "{document}"], [], tmp_path)
    with pytest.raises(CheckError) as error:
        tool.export(tmp_path / "b.rcdx", tmp_path / "b.yaml")
    assert str(error.value) == "the Hytera tool cannot run: no-such-hytera-tool not found"


@pytest.mark.parametrize(
    ("command", "key"),
    [
        ("export: [tool, '{base}']", "export"),
        ("import: [tool, '{document}', '{output}', '{base}', '{factory}', '{secret}']", "import"),
        ("import: []", "import"),
    ],
)
def test_a_command_line_must_name_exactly_its_files(data: Path, command: str, key: str) -> None:
    fleet_file = data / "fleet.yaml"
    text = fleet_file.read_text()
    old = next(line for line in text.splitlines() if line.startswith(f"    {key}: "))
    fleet_file.write_text(text.replace(old, f"    {command}"))
    with pytest.raises(ConfigError, match=rf"tools\.hytera\.{key}: expected a list of arguments with exactly"):
        fleet.load(fleet_file, data)
