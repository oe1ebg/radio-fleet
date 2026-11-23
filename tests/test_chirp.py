import csv
import io
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from radio_fleet import fleet
from radio_fleet.cli import main
from radio_fleet.fleet import GroupRule, PrefixRegion, Radio, Region
from radio_fleet.model import Channel, Ctcss, Dcs, Mode, Tone
from radio_fleet.render import chirp
from radio_fleet.render.csvcheck import CsvCheckError
from radio_fleet.selection import Drop, Group, Selection, select
from radio_fleet.sources import Sources

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
HEADER = (
    "Location,Name,Frequency,Duplex,Offset,Tone,rToneFreq,cToneFreq,DtcsCode,DtcsPolarity,RxDtcsCode,"
    "CrossMode,Mode,TStep,Skip,Power,Comment,URCALL,RPT1CALL,RPT2CALL,DVCODE"
)


def radio() -> Radio:
    return fleet.load(EXAMPLES / "fleet.yaml", EXAMPLES).radios["uv5r-mini"]


def render(*channels: Channel) -> list[str]:
    text = chirp.render(Selection(radio(), channels, (), (), (), ()))
    chirp.check(text, radio().capability)
    lines = text.splitlines()
    assert lines[0] == HEADER
    return lines[1:]


def fm(
    name: str,
    rx: int,
    tx: int,
    tone_tx: Tone | None = None,
    tone_rx: Tone | None = None,
    bandwidth_hz: int | None = None,
    power: str | None = "5W",
) -> Channel:
    return Channel(name, rx, tx, Mode.FM, tone_tx, tone_rx, bandwidth_hz, power=power, source="synthetic")


def test_repeater_simplex_ctcss_and_dcs_channels_give_the_expected_rows() -> None:
    assert render(
        fm("XX0SX", 145_500_000, 145_500_000, bandwidth_hz=25_000),
        fm("XX0RP", 145_612_500, 145_012_500, tone_tx=Ctcss(88.5), bandwidth_hz=12_500),
        fm("XX0UP", 438_962_500, 431_362_500, tone_tx=Ctcss(123.0), tone_rx=Ctcss(123.0), power="0.5W"),
        fm("XX0DC", 433_600_000, 433_600_000, tone_tx=Dcs(23), tone_rx=Dcs(23), power="2W"),
        fm("XX0MI", 431_037_500, 438_637_500),
    ) == [
        "1,XX0SX,145.500000,,0.000000,,88.5,88.5,023,NN,023,Tone->Tone,FM,12.50,,5.0W,,,,,",
        "2,XX0RP,145.612500,-,0.600000,Tone,88.5,88.5,023,NN,023,Tone->Tone,NFM,12.50,,5.0W,,,,,",
        "3,XX0UP,438.962500,-,7.600000,TSQL,123.0,123.0,023,NN,023,Tone->Tone,FM,12.50,,0.5W,,,,,",
        "4,XX0DC,433.600000,,0.000000,DTCS,88.5,88.5,023,NN,023,Tone->Tone,FM,12.50,,2.0W,,,,,",
        "5,XX0MI,431.037500,+,7.600000,,88.5,88.5,023,NN,023,Tone->Tone,FM,12.50,,5.0W,,,,,",
    ]


@pytest.mark.parametrize(
    ("tx", "rx", "columns"),
    [
        (Ctcss(77.0), Ctcss(88.5), "Cross,77.0,88.5,023,NN,023,Tone->Tone"),
        (None, Ctcss(88.5), "Cross,88.5,88.5,023,NN,023,->Tone"),
        (Dcs(47), None, "Cross,88.5,88.5,047,NN,023,DTCS->"),
        (None, Dcs(47), "Cross,88.5,88.5,023,NN,047,->DTCS"),
        (Ctcss(77.0), Dcs(47), "Cross,77.0,88.5,023,NN,047,Tone->DTCS"),
        (Dcs(47), Ctcss(77.0), "Cross,88.5,77.0,047,NN,023,DTCS->Tone"),
        (Dcs(47), Dcs(54), "Cross,88.5,88.5,047,NN,054,DTCS->DTCS"),
    ],
)
def test_different_tx_and_rx_tones_give_a_cross_mode(tx: Tone | None, rx: Tone | None, columns: str) -> None:
    (row,) = render(fm("XX0CR", 145_500_000, 145_500_000, tone_tx=tx, tone_rx=rx))
    assert row == f"1,XX0CR,145.500000,,0.000000,{columns},FM,12.50,,5.0W,,,,,"


def test_a_profile_step_of_5_khz_and_a_skipped_channel_give_the_expected_tstep_and_skip() -> None:
    stepped = replace(radio(), step_hz=5_000)
    channels = (
        fm("XX0FV", 145_525_000, 145_525_000),
        replace(fm("XX0SK", 145_550_000, 145_550_000), skip=True),
        fm("XX0SX", 446_006_250, 446_006_250),
        replace(fm("XX0TW", 145_600_000, 145_000_000), step_hz=25_000),
    )
    rows = list(csv.reader(io.StringIO(chirp.render(Selection(stepped, channels, (), (), (), ())))))[1:]
    assert [(row[1], row[13], row[14]) for row in rows] == [
        ("XX0FV", "5.00", ""),
        ("XX0SK", "5.00", "S"),
        ("XX0SX", "6.25", ""),
        ("XX0TW", "25.00", ""),
    ]


def test_with_scan_list_rules_a_channel_no_scan_list_takes_is_skipped_unless_it_says_otherwise() -> None:
    scanning = replace(radio(), scan_lists=(GroupRule("Repeaters", channels=("XX0R*",)),))
    channels = (
        fm("XX0RA", 145_600_000, 145_000_000),
        fm("XX0SX", 145_500_000, 145_500_000),
        replace(fm("XX0SY", 145_525_000, 145_525_000), skip=False),
        replace(fm("XX0RB", 145_625_000, 145_025_000), skip=True),
    )
    scan = Group("Repeaters", (channels[0], channels[3]))
    text = chirp.render(Selection(scanning, channels, (), (scan,), (), ()))
    assert [(row[1], row[14]) for row in list(csv.reader(io.StringIO(text)))[1:]] == [
        ("XX0RA", ""),
        ("XX0SX", "S"),
        ("XX0SY", ""),
        ("XX0RB", "S"),
    ]


def test_the_comment_is_the_note_else_the_site_and_never_the_source() -> None:
    channels = (
        replace(fm("XX0NT", 145_500_000, 145_500_000), site="Synthetic Hill", note="calling channel"),
        replace(fm("XX0ST", 145_600_000, 145_000_000), site="Synthetic Hill"),
        fm("XX0NO", 145_525_000, 145_525_000),
    )
    assert [row.split(",")[16] for row in render(*channels)] == ["calling channel", "Synthetic Hill", ""]


def test_a_channel_off_its_own_step_is_refused() -> None:
    with pytest.raises(
        chirp.RenderError, match=r"XX0OF: RX 145\.506250 MHz or its offset is not on its step 12\.5 kHz"
    ):
        render(replace(fm("XX0OF", 145_506_250, 145_506_250), step_hz=12_500))


def test_a_channel_listed_twice_is_one_memory() -> None:
    channel = fm("XX0SX", 145_500_000, 145_500_000)
    assert len(render(channel, channel)) == 1


def test_the_memory_limit_drops_channels_with_a_reason() -> None:
    small = replace(
        radio(),
        capability=replace(radio().capability, channels=2),
        region=Region(PrefixRegion(("XX0",)), {}, {}),
        own_lists=(),
    )
    upstream = [
        replace(fm(f"XX0A{i}", 145_500_000 + i * 12_500, 145_500_000 + i * 12_500, power=None), callsign=f"XX0A{i}")
        for i in range(3)
    ]
    selection = select(small, upstream, Sources(EXAMPLES / "sources", {}, {}, {}, (), {}))
    assert selection.drops == (Drop("XX0A2", "channel limit of 2 reached"),)
    text = chirp.render(selection)
    chirp.check(text, small.capability)
    assert [row[1] for row in csv.reader(io.StringIO(text))][1:] == ["XX0A0", "XX0A1"]


@pytest.mark.parametrize(
    ("channel", "message"),
    [
        (Channel("XX0DM", 438_962_500, 431_462_500, Mode.DMR), "carries FM, not DMR"),
        (fm("XX0FM", 145_500_000, 145_500_000, power=None), "CHIRP needs a power: give the profile a power level"),
        (fm("XX0FM", 145_501_000, 145_501_000), r"RX 145.501000 MHz is on no CHIRP tuning step"),
    ],
)
def test_a_channel_chirp_cannot_carry_is_refused(channel: Channel, message: str) -> None:
    with pytest.raises(chirp.RenderError, match=message):
        render(channel)


ROW = "1,XX0SX,145.500000,,0.000000,,88.5,88.5,023,NN,023,Tone->Tone,FM,12.50,,5.0W,,,,,"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (f"Location,Name\n{ROW}\n", "the header is not CHIRP's"),
        (f"{HEADER}\n{ROW},extra\n", "row 1: 22 columns, expected 21"),
        (f"{HEADER}\n{ROW.replace('1,', '7,', 1)}\n", "row 1: location '7', expected 1"),
        (f"{HEADER}\n{ROW.replace('XX0SX', 'XX0SX LONG NAME')}\n", "name 'XX0SX LONG NAME' is longer than 12"),
        (f"{HEADER}\n" + "".join(ROW.replace("1,", f"{n},", 1) + "\n" for n in range(1, 1001)), "1000 memories"),
    ],
)
def test_the_csv_check_refuses_rows_the_radio_cannot_take(text: str, message: str) -> None:
    with pytest.raises(CsvCheckError, match=message):
        chirp.check(text, radio().capability)


def test_build_writes_the_checked_chirp_csv(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data = tmp_path / "data"
    shutil.copytree(EXAMPLES, data)
    assert main(["build", "--data", str(data), "--radio", "uv5r-mini"]) == 0
    output = data / "build" / "uv5r-mini" / "uv5r-mini.csv"
    assert capsys.readouterr().out == f"uv5r-mini: {output}\n"
    assert output.read_text(encoding="utf-8").splitlines()[1] == (
        "1,2m Call,145.500000,,0.000000,,88.5,88.5,023,NN,023,Tone->Tone,FM,12.50,,5.0W,,,,,"
    )


def test_a_data_root_with_watts_per_channel_builds_unchanged(tmp_path: Path) -> None:
    data = tmp_path / "data"
    shutil.copytree(EXAMPLES, data)
    levels = "{Max: 5W, High: 5W, Mid: 2W, Low: 1W, Min: 0.5W}"
    fleet_file = data / "fleet.yaml"
    text = fleet_file.read_text()
    old_profile = f"    power: High\n    power_levels: &baofeng_power {levels}\n"
    assert old_profile in text
    text = text.replace(old_profile, "    power: 5W\n")
    fleet_file.write_text(text.replace("*baofeng_power", levels))
    simplex = data / "sources" / "own" / "simplex.yaml"
    simplex.write_text(simplex.read_text().replace("rx: 145.500, mode: FM}", "rx: 145.500, mode: FM, power: 2W}"))
    assert main(["build", "--data", str(data), "--radio", "uv5r-mini"]) == 0
    rows = (data / "build" / "uv5r-mini" / "uv5r-mini.csv").read_text(encoding="utf-8").splitlines()[1:]
    assert [row.split(",")[15] for row in rows[:2]] == ["2.0W", "5.0W"]


def test_a_chirp_render_error_fails_the_build_and_names_the_radio(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = tmp_path / "data"
    shutil.copytree(EXAMPLES, data)
    fleet_file = data / "fleet.yaml"
    fleet_file.write_text(fleet_file.read_text().replace("power: High\n    power_levels: &", "power_levels: &"))
    assert main(["build", "--data", str(data), "--radio", "uv5r-mini"]) == 1
    assert capsys.readouterr().err == (
        "fleet build: uv5r-mini: channel 2m Call: CHIRP needs a power: give the profile a power level and its "
        "watts, such as power: High and power_levels: {High: 5W}\n"
    )
