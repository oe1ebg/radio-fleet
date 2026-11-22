"""The change report `build/CHANGES.md` (R11), with synthetic builds and fake tools."""

import shutil
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from radio_fleet import changes, fleet, record
from radio_fleet.cli import main
from radio_fleet.dmrconf import CheckError
from radio_fleet.model import Channel, Ctcss, Dcs, Mode
from radio_fleet.record import Applied
from radio_fleet.selection import Drop, Selection
from radio_fleet.sources import AppliedOverride, Override

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"

CALL = Channel("2m Call", 145_500_000, 145_500_000, Mode.FM, power="5W")
REPEATER = Channel("XX1AA", 145_600_000, 145_000_000, Mode.FM, tone_tx=Ctcss(88.5), power="5W")
GONE = Channel("XX1GO", 438_650_000, 431_050_000, Mode.FM, power="5W")
TWIN = Channel("XX1TW", 439_000_000, 431_400_000, Mode.FM, tone_tx=Dcs(23), power="5W")


def test_a_before_and_after_pair_gives_the_expected_report(tmp_path: Path) -> None:
    radio = fleet.load(EXAMPLES / "fleet.yaml", EXAMPLES).radios["uv5r-mini"]
    before = (CALL, REPEATER, GONE, TWIN)
    after = (
        CALL,
        replace(REPEATER, tone_tx=Ctcss(77.0), tone_rx=Ctcss(77.0), power="1W"),
        replace(TWIN, power="1W"),
        replace(TWIN, name="XX1TW"),
        Channel("XX1NE", 438_700_000, 431_100_000, Mode.FM, bandwidth_hz=12_500),
    )
    override = Override("XX1AA", "the repeater moved to 77.0 Hz", {"tone_tx": Ctcss(77.0)})
    selection = Selection(
        radio,
        after,
        (),
        (Drop("XX1FA", "TX 435.00000 MHz outside the TX bands"),),
        (AppliedOverride("XX1AA", Mode.FM, override),),
    )
    build = tmp_path / "build"
    record.write_build(selection, build / "uv5r-mini")
    applied = tmp_path / "applied.yaml"
    record.save_applied(
        applied, {"uv5r-mini": Applied("2026-01-02", "sha256:00", tuple(map(record.channel_record, before)))}
    )

    changes.write([radio], build, applied)

    assert (build / "CHANGES.md").read_text(encoding="utf-8") == (
        "# Changes\n"
        "\n"
        "Each radio's build in `build/` against its last applied build in `applied.yaml`.\n"
        "\n"
        "## uv5r-mini: Baofeng UV-5R mini (chirp)\n"
        "\n"
        "Against the build applied on 2026-01-02: 5 channels, 1 unchanged.\n"
        "\n"
        "### Added (2)\n"
        "\n"
        "- XX1TW (2): rx 439.00000, tx 431.40000, mode FM, tone_tx DCS 023, power 5W\n"
        "- XX1NE: rx 438.70000, tx 431.10000, mode FM, bandwidth 12.5 kHz\n"
        "\n"
        "### Removed (1)\n"
        "\n"
        "- XX1GO: rx 438.65000, tx 431.05000, mode FM, power 5W\n"
        "\n"
        "### Changed (2)\n"
        "\n"
        "- XX1AA: tone_tx CTCSS 88.5 -> CTCSS 77; tone_rx - -> CTCSS 77; power 5W -> 1W\n"
        "- XX1TW: power 5W -> 1W\n"
        "\n"
        "### Drops (1)\n"
        "\n"
        "- XX1FA: TX 435.00000 MHz outside the TX bands\n"
        "\n"
        "### Overrides (1)\n"
        "\n"
        "- XX1AA FM: tone_tx=CTCSS 77 (the repeater moved to 77.0 Hz)\n"
    )


def test_the_first_build_compares_against_nothing_and_an_unbuilt_radio_says_so(tmp_path: Path) -> None:
    radios = fleet.load(EXAMPLES / "fleet.yaml", EXAMPLES).radios
    selection = Selection(radios["rt95"], (CALL,), (), (), ())
    record.write_build(selection, tmp_path / "build" / "rt95")

    changes.write([radios["rt95"], radios["hm785"]], tmp_path / "build", tmp_path / "applied.yaml")

    assert (tmp_path / "build" / "CHANGES.md").read_text(encoding="utf-8").split("\n## ")[1:] == [
        "rt95: Retevis RT95 (chirp)\n\n"
        "First build, nothing applied: 1 channels.\n\n"
        "### Added (1)\n\n- 2m Call: rx 145.50000, tx 145.50000, mode FM, power 5W\n\n"
        "### Removed (0)\n\nNone.\n\n"
        "### Changed (0)\n\nNone.\n\n"
        "### Drops (0)\n\nNone.\n\n"
        "### Overrides (0)\n\nNone.\n",
        "hm785: Hytera HM785 (hytera)\n\nNot built.\n",
    ]


class FakeDmrconf:
    def verify(self, radio: str, codeplug: Path) -> None:
        pass


class FakeJayt:
    def export(self, file: Path, document: Path) -> None:
        document.write_text("channels: []\nradio: FT-3185\n", encoding="utf-8")

    def import_(self, document: Path, output: Path, template: Path) -> None:
        output.write_bytes(b"synthetic radio file")

    def check(self, file: Path) -> None:
        pass


class FakeHytera:
    """The export names its base file, as the real one does; that path must not reach the report."""

    def __init__(self, error: str | None = None) -> None:
        self.error = error

    def export(self, base: Path, document: Path) -> None:
        document.write_text(_HYTERA_EXPORT.replace("BASE_PATH", str(base)), encoding="utf-8")

    def import_(self, document: Path, output: Path, base: Path, factory: Path) -> None:
        if self.error is not None:
            raise CheckError(self.error)
        output.write_bytes(b"synthetic rcdx")


_HYTERA_EXPORT = """\
source: {file: BASE_PATH}
tables:
  digital_channels: {entries: []}
  analog_channels: {entries: []}
  contacts: {entries: []}
  rx_groups: {entries: []}
  zones: {entries: []}
"""


@pytest.fixture
def data(tmp_path: Path) -> Path:
    """The example data root with synthetic bases for the jayt and Hytera radios, outside the data root."""
    root = tmp_path / "data"
    shutil.copytree(EXAMPLES, root)
    (tmp_path / "private").mkdir()
    for name in ("ft3185.img", "ftx1.img", "hp785.rcdx", "hm785.rcdx", "factory.rcdx"):
        (tmp_path / "private" / name).write_bytes(b"synthetic")
    text = (root / "fleet.yaml").read_text()
    for radio in ("ft3185", "ftx1"):
        text = text.replace(f"  {radio}:\n", f"  {radio}:\n    base: ../private/{radio}.img\n")
    for radio in ("hp785", "hm785"):
        text = text.replace(
            f"    # base: ../hytera/{radio}.rcdx\n    # factory: ../hytera/{radio}-factory.rcdx\n",
            f"    base: ../private/{radio}.rcdx\n    factory: ../private/factory.rcdx\n",
        )
    (root / "fleet.yaml").write_text(text)
    return root


def build(data: Path, radio: str, hytera: FakeHytera | None = None) -> int:
    return main(
        ["build", "--data", str(data), "--radio", radio],
        dmrconf=FakeDmrconf(),
        jayt=FakeJayt(),
        hytera=hytera or FakeHytera(),
    )


def test_the_report_covers_every_radio_and_renderer_without_a_base_path(
    data: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    the_fleet = fleet.load(data / "fleet.yaml", data)
    # The FTX-1 is not buildable yet: the jayt renderer carries the FT-3185's FM channels only.
    built = [radio for radio in the_fleet.radios.values() if radio.id != "ftx1"]
    assert {radio.renderer for radio in built} == set(fleet.Renderer)
    for radio in built:
        assert build(data, radio.id) == 0, capsys.readouterr().err
    assert build(data, "ftx1") == 1

    report = (data / "build" / "CHANGES.md").read_text(encoding="utf-8")
    sections = report.split("\n## ")[1:]
    assert [section.split(":")[0] for section in sections] == list(the_fleet.radios)
    for radio, section in zip(the_fleet.radios.values(), sections, strict=True):
        if radio.id == "ftx1":
            assert section == "ftx1: Yaesu FTX-1 (jayt)\n\nNot built.\n"
            continue
        assert section.startswith(f"{radio.id}: {radio.model} ({radio.renderer})\n\nFirst build, nothing applied: ")
        assert "### Added (0)" not in section
    assert "private" not in report and "synthetic" not in report
    assert "private" not in capsys.readouterr().out.replace(str(data), "")


def test_a_failed_build_leaves_its_radio_unbuilt_in_the_report(data: Path) -> None:
    assert build(data, "hp785") == 0
    assert build(data, "hp785", FakeHytera("the Hytera tool's import failed")) == 1
    report = (data / "build" / "CHANGES.md").read_text(encoding="utf-8")
    assert "## hp785: Hytera HP785 (hytera)\n\nNot built.\n" in report
    assert not (data / "build" / "hp785" / "selection.yaml").exists()


def test_after_applied_a_rebuild_reports_only_what_changed(data: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert build(data, "uv5r-mini") == 0
    assert main(["applied", "--data", str(data), "uv5r-mini"], today=date(2026, 3, 4)) == 0
    own = data / "sources" / "own" / "simplex.yaml"
    own.write_text(own.read_text().replace("{name: 2m Call, rx: 145.500,", "{name: 2m Call, rx: 145.525,"))
    assert build(data, "uv5r-mini") == 0

    report = (data / "build" / "CHANGES.md").read_text(encoding="utf-8")
    section = report.split("## uv5r-mini: ")[1].split("\n## ")[0]
    assert "Against the build applied on 2026-03-04: " in section
    assert "### Added (0)" in section and "### Removed (0)" in section
    assert "### Changed (1)\n\n- 2m Call: rx 145.50000 -> 145.52500; tx 145.50000 -> 145.52500\n" in section
