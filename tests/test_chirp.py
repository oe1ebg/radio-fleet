import csv
import io
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from radio_fleet import fleet
from radio_fleet.cli import main
from radio_fleet.fleet import PrefixRegion, Radio
from radio_fleet.model import Channel, Ctcss, Dcs, Mode, Tone
from radio_fleet.render import chirp
from radio_fleet.render.csvcheck import CsvCheckError
from radio_fleet.selection import Drop, Selection, select
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
        fm("XX0DC", 433_600_000, 433_600_000, tone_tx=Dcs(23), tone_rx=Dcs(23), power="2 W"),
        fm("XX0MI", 431_037_500, 438_637_500),
    ) == [
        "1,XX0SX,145.500000,,0.000000,,88.5,88.5,023,NN,023,Tone->Tone,FM,12.50,,5.0W,synthetic,,,,",
        "2,XX0RP,145.612500,-,0.600000,Tone,88.5,88.5,023,NN,023,Tone->Tone,NFM,12.50,,5.0W,synthetic,,,,",
        "3,XX0UP,438.962500,-,7.600000,TSQL,123.0,123.0,023,NN,023,Tone->Tone,FM,12.50,,0.5W,synthetic,,,,",
        "4,XX0DC,433.600000,,0.000000,DTCS,88.5,88.5,023,NN,023,Tone->Tone,FM,12.50,,2.0W,synthetic,,,,",
        "5,XX0MI,431.037500,+,7.600000,,88.5,88.5,023,NN,023,Tone->Tone,FM,12.50,,5.0W,synthetic,,,,",
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
    assert row == f"1,XX0CR,145.500000,,0.000000,{columns},FM,12.50,,5.0W,synthetic,,,,"


def test_a_channel_listed_twice_is_one_memory() -> None:
    channel = fm("XX0SX", 145_500_000, 145_500_000)
    assert len(render(channel, channel)) == 1


def test_the_memory_limit_drops_channels_with_a_reason() -> None:
    small = replace(
        radio(),
        capability=replace(radio().capability, channels=2),
        region=PrefixRegion(("XX0",)),
        own_lists=(),
    )
    upstream = [fm(f"XX0A{i}", 145_500_000 + i * 12_500, 145_500_000 + i * 12_500) for i in range(3)]
    selection = select(small, upstream, Sources(EXAMPLES / "sources", {}, {}, {}, (), {}))
    assert selection.drops == (Drop("XX0A2", "channel limit of 2 reached"),)
    text = chirp.render(selection)
    chirp.check(text, small.capability)
    assert [row[1] for row in csv.reader(io.StringIO(text))][1:] == ["XX0A0", "XX0A1"]


@pytest.mark.parametrize(
    ("channel", "message"),
    [
        (Channel("XX0DM", 438_962_500, 431_462_500, Mode.DMR, power="5W"), "carries FM, not DMR"),
        (fm("XX0FM", 145_500_000, 145_500_000, power="High"), "power in watts, such as 5W, not 'High'"),
        (fm("XX0FM", 145_500_000, 145_500_000, power=None), "power in watts, such as 5W, not None"),
        (fm("XX0FM", 145_501_000, 145_501_000), r"RX 145.501000 MHz is on no CHIRP tuning step"),
    ],
)
def test_a_channel_chirp_cannot_carry_is_refused(channel: Channel, message: str) -> None:
    with pytest.raises(chirp.RenderError, match=message):
        render(channel)


ROW = "1,XX0SX,145.500000,,0.000000,,88.5,88.5,023,NN,023,Tone->Tone,FM,12.50,,5.0W,synthetic,,,,"


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
        "1,2m Call,145.500000,,0.000000,,88.5,88.5,023,NN,023,Tone->Tone,FM,12.50,,5.0W,simplex,,,,"
    )


def test_a_chirp_render_error_fails_the_build_and_names_the_radio(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = tmp_path / "data"
    shutil.copytree(EXAMPLES, data)
    fleet_file = data / "fleet.yaml"
    fleet_file.write_text(fleet_file.read_text().replace("power: 5W", "power: High"))
    assert main(["build", "--data", str(data), "--radio", "uv5r-mini"]) == 1
    assert capsys.readouterr().err == (
        "fleet build: uv5r-mini: channel 2m Call: CHIRP needs the power in watts, such as 5W, not 'High'\n"
    )
