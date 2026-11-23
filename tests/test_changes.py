"""The change report `build/CHANGES.md` (R11), with synthetic builds and fake tools."""

import shutil
from dataclasses import fields, replace
from datetime import date
from pathlib import Path
from typing import Any

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
    override = Override("XX1AA", "the repeater moved to 77.0 Hz", {"tone_tx": Ctcss(77.0)}, clear=("tone_rx",))
    stale = Override("XX1GO", "the repeater lost its tone", {}, clear=("tone_tx",), mode=Mode.FM, band="70cm")
    selection = Selection(
        radio,
        after,
        (),
        (),
        (Drop("XX1FA", "TX 435.00000 MHz outside the TX bands"),),
        (AppliedOverride("XX1AA", Mode.FM, "2m", override),),
        (stale,),
        ("XX1TW: 2.4W -> Mid (2W)",),
    )
    build = tmp_path / "build"
    record.write_build(selection, build / "uv5r-mini")
    applied = tmp_path / "applied.yaml"
    record.save_applied(applied, {"uv5r-mini": Applied("2026-01-02", "sha256:00", records(before))})

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
        "- XX1TW [FM #2]: rx 439.00000, tx 431.40000, mode FM, tone_tx DCS 023, power 5W\n"
        "- XX1NE: rx 438.70000, tx 431.10000, mode FM, bandwidth 12.5 kHz\n"
        "\n"
        "### Removed (1)\n"
        "\n"
        "- XX1GO: rx 438.65000, tx 431.05000, mode FM, power 5W\n"
        "\n"
        "### Changed (2)\n"
        "\n"
        "- XX1AA: tone_tx CTCSS 88.5 -> CTCSS 77; tone_rx - -> CTCSS 77; power 5W -> 1W\n"
        "- XX1TW [FM]: power 5W -> 1W\n"
        "\n"
        "### Drops (1)\n"
        "\n"
        "- XX1FA: TX 435.00000 MHz outside the TX bands\n"
        "\n"
        "### Overrides (1)\n"
        "\n"
        "- XX1AA FM 2m: tone_tx=CTCSS 77, tone_rx=- (the repeater moved to 77.0 Hz)\n"
        "\n"
        "### Overrides that match nothing (1)\n"
        "\n"
        "- XX1GO FM 70cm: tone_tx=- (the repeater lost its tone)\n"
        "\n"
        "### Power set to the nearest value (1)\n"
        "\n"
        "- XX1TW: 2.4W -> Mid (2W)\n"
    )


def test_the_first_build_compares_against_nothing_and_an_unbuilt_radio_says_so(tmp_path: Path) -> None:
    radios = fleet.load(EXAMPLES / "fleet.yaml", EXAMPLES).radios
    selection = Selection(radios["rt95"], (replace(CALL, power="25W"),), (), (), (), ())
    record.write_build(selection, tmp_path / "build" / "rt95")

    changes.write([radios["rt95"], radios["hm785"]], tmp_path / "build", tmp_path / "applied.yaml")

    assert (tmp_path / "build" / "CHANGES.md").read_text(encoding="utf-8").split("\n## ")[1:] == [
        "rt95: Retevis RT95 (chirp)\n\n"
        "First build, nothing applied: 1 channels.\n\n"
        "### Added (1)\n\n- 2m Call: rx 145.50000, tx 145.50000, mode FM, power 25W\n\n"
        "### Removed (0)\n\nNone.\n\n"
        "### Changed (0)\n\nNone.\n\n"
        "### Drops (0)\n\nNone.\n\n"
        "### Overrides (0)\n\nNone.\n\n"
        "### Overrides that match nothing (0)\n\nNone.\n\n"
        "### Power set to the nearest value (0)\n\nNone.\n",
        "hm785: Hytera HM785 (hytera)\n\nNot built.\n",
    ]


def records(channels: tuple[Channel, ...]) -> tuple[record.ChannelRecord, ...]:
    return tuple(record.channel_record(channel) for channel in channels)


def lists(before: tuple[Channel, ...], after: tuple[Channel, ...], tmp_path: Path) -> dict[str, list[str]]:
    """The Added, Removed and Changed items of the uv5r-mini's report for an applied and a built set."""
    radio = fleet.load(EXAMPLES / "fleet.yaml", EXAMPLES).radios["uv5r-mini"]
    record.write_build(Selection(radio, after, (), (), (), ()), tmp_path / "build" / "uv5r-mini")
    applied = tmp_path / "applied.yaml"
    record.save_applied(applied, {"uv5r-mini": Applied("2026-01-02", "sha256:00", records(before))})
    changes.write([radio], tmp_path / "build", applied)
    report = (tmp_path / "build" / "CHANGES.md").read_text(encoding="utf-8")
    return {
        title: [line[2:] for line in report.split(f"### {title} (")[1].split("\n\n")[1].splitlines() if line != "None."]
        for title in ("Added", "Removed", "Changed")
    }


def test_the_modes_of_a_multi_mode_repeater_are_told_apart(tmp_path: Path) -> None:
    fm = Channel("XX1CC", 439_100_000, 431_500_000, Mode.FM, tone_tx=Ctcss(88.5), power="5W")
    dmr = Channel("XX1CC", 439_100_000, 431_500_000, Mode.DMR, color_code=1, time_slot=1, power="5W")
    assert lists((fm, dmr), (replace(dmr, power="1W"),), tmp_path) == {
        "Added": [],
        "Removed": ["XX1CC [FM]: rx 439.10000, tx 431.50000, mode FM, tone_tx CTCSS 88.5, power 5W"],
        "Changed": ["XX1CC [DMR]: power 5W -> 1W"],
    }


def test_a_channel_named_like_a_repeat_is_its_own_channel(tmp_path: Path) -> None:
    named = replace(TWIN, name="XX1TW (2)", power="1W")
    assert lists((TWIN, replace(TWIN, power="2W"), named), (TWIN, named), tmp_path) == {
        "Added": [],
        "Removed": ["XX1TW [FM #2]: rx 439.00000, tx 431.40000, mode FM, tone_tx DCS 023, power 2W"],
        "Changed": [],
    }


def test_a_unique_name_that_changes_mode_is_a_change(tmp_path: Path) -> None:
    dmr = replace(GONE, mode=Mode.DMR, color_code=1)
    assert lists((GONE,), (dmr,), tmp_path) == {
        "Added": [],
        "Removed": [],
        "Changed": ["XX1GO: mode FM -> DMR; color_code - -> 1"],
    }


def test_an_unreadable_build_record_is_reported_and_the_other_radios_still_are(tmp_path: Path) -> None:
    radios = fleet.load(EXAMPLES / "fleet.yaml", EXAMPLES).radios
    record.write_build(Selection(radios["rt95"], (CALL,), (), (), (), ()), tmp_path / "build" / "rt95")
    (tmp_path / "build" / "uv5r-mini").mkdir()
    (tmp_path / "build" / "uv5r-mini" / "selection.yaml").write_text("channels: [")

    changes.write([radios["uv5r-mini"], radios["rt95"]], tmp_path / "build", tmp_path / "applied.yaml")

    sections = (tmp_path / "build" / "CHANGES.md").read_text(encoding="utf-8").split("\n## ")[1:]
    assert sections[0] == (
        "uv5r-mini: Baofeng UV-5R mini (chirp)\n\n"
        "The build record selection.yaml is unreadable; run `fleet build --radio uv5r-mini`.\n"
    )
    assert sections[1].startswith("rt95: Retevis RT95 (chirp)\n\nFirst build, nothing applied: 1 channels.")


def test_every_channel_field_a_radio_holds_is_recorded_and_compared() -> None:
    full = Channel(
        "XX1FU", 438_000_000, 430_400_000, Mode.DMR, Ctcss(67.0), Dcs(23), 12_500, 1, 2, "TG 232", "Austria", "1W"
    )
    assert list(record.channel_record(replace(full, rx_only=True))) == ["name", *record.FIELDS]
    others: dict[str, Any] = {
        "name": "XX1FV",
        "rx_hz": 438_100_000,
        "tx_hz": 430_500_000,
        "mode": Mode.FM,
        "tone_tx": Ctcss(77.0),
        "tone_rx": Dcs(25),
        "bandwidth_hz": 25_000,
        "color_code": 2,
        "time_slot": 1,
        "tx_talkgroup": "TG 9",
        "rx_group_list": "Local",
        "power": "5W",
        "rx_only": True,
    }
    not_held = {"tags", "source", "position", "callsign", "site"}
    assert {field.name for field in fields(Channel)} == set(others) | not_held
    for field, value in others.items():
        changed = record.channel_record(replace(full, **{field: value}))
        assert changed != record.channel_record(full), field


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


def test_a_report_that_cannot_be_written_does_not_hide_the_build_result(
    data: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (data / "applied.yaml").write_text("uv5r-mini: [")
    assert build(data, "hp785", FakeHytera("the Hytera tool's import failed")) == 1
    err = capsys.readouterr().err
    assert "fleet build: hp785: " in err and "the Hytera tool's import failed" in err
    assert "fleet: CHANGES.md not written: " in err

    assert build(data, "uv5r-mini") == 1
    out, err = capsys.readouterr()
    assert out == f"uv5r-mini: {data / 'build' / 'uv5r-mini' / 'uv5r-mini.csv'}\n"
    assert err.startswith("fleet: CHANGES.md not written: ")
