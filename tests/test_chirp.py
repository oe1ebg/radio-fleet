import csv
import io
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from radio_fleet import fleet, sources
from radio_fleet.dmrconf import CheckError
from radio_fleet.model import Channel, Ctcss, Dcs, Mode
from radio_fleet.render import chirp
from radio_fleet.selection import Drop, Selection, select

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
RADIO = fleet.load(EXAMPLES / "fleet.yaml", EXAMPLES).radios["uv5r-mini"]


def rows_of(*channels: Channel) -> list[dict[str, str]]:
    selection = Selection(RADIO, channels, (), (), ())
    text = chirp.render(selection)
    chirp.check(text, selection)
    return list(csv.DictReader(io.StringIO(text)))


def fields(row: dict[str, str], *keys: str) -> tuple[str, ...]:
    return tuple(row[key] for key in keys)


def test_the_header_is_chirps_generic_csv() -> None:
    text = chirp.render(Selection(RADIO, (), (), (), ()))
    assert text == (
        "Location,Name,Frequency,Duplex,Offset,Tone,rToneFreq,cToneFreq,DtcsCode,DtcsPolarity,RxDtcsCode,"
        "CrossMode,Mode,TStep,Skip,Power,Comment,URCALL,RPT1CALL,RPT2CALL,DVCODE\n"
    )


def test_repeater_simplex_ctcss_and_dcs_channels_give_the_expected_rows() -> None:
    repeater = Channel("XX0FM", 145_600_000, 145_000_000, Mode.FM, bandwidth_hz=12_500, power="5.0W", source="db")
    simplex = Channel("2m Call", 145_500_000, 145_500_000, Mode.FM, source="simplex")
    up = Channel("XX0UP", 433_000_000, 434_600_000, Mode.FM, tone_tx=Ctcss(123.0))
    tsql = Channel("XX0TS", 438_962_500, 431_362_500, Mode.FM, tone_tx=Ctcss(88.5), tone_rx=Ctcss(88.5))
    dtcs = Channel("XX0DC", 438_625_000, 431_025_000, Mode.FM, tone_tx=Dcs(23), tone_rx=Dcs(23))
    cross = Channel("XX0CR", 145_662_500, 145_062_500, Mode.FM, tone_tx=Ctcss(77.0), tone_rx=Dcs(754))
    rows = rows_of(repeater, simplex, up, tsql, dtcs, cross)
    keys = ("Location", "Name", "Frequency", "Duplex", "Offset", "Mode", "TStep", "Power", "Comment")
    assert [fields(row, *keys) for row in rows] == [
        ("1", "XX0FM", "145.600000", "-", "0.600000", "NFM", "5.00", "5.0W", "db"),
        ("2", "2m Call", "145.500000", "", "0.000000", "FM", "5.00", "", "simplex"),
        ("3", "XX0UP", "433.000000", "+", "1.600000", "FM", "5.00", "", ""),
        ("4", "XX0TS", "438.962500", "-", "7.600000", "FM", "6.25", "", ""),
        ("5", "XX0DC", "438.625000", "-", "7.600000", "FM", "5.00", "", ""),
        ("6", "XX0CR", "145.662500", "-", "0.600000", "FM", "6.25", "", ""),
    ]
    tones = ("Tone", "rToneFreq", "cToneFreq", "DtcsCode", "DtcsPolarity", "RxDtcsCode", "CrossMode")
    assert [fields(row, *tones) for row in rows] == [
        ("", "88.5", "88.5", "023", "NN", "023", "Tone->Tone"),
        ("", "88.5", "88.5", "023", "NN", "023", "Tone->Tone"),
        ("Tone", "123.0", "123.0", "023", "NN", "023", "Tone->Tone"),
        ("TSQL", "88.5", "88.5", "023", "NN", "023", "Tone->Tone"),
        ("DTCS", "88.5", "88.5", "023", "NN", "023", "Tone->Tone"),
        ("Cross", "77.0", "77.0", "023", "NN", "754", "Tone->DTCS"),
    ]


def test_the_memory_limit_drops_channels_with_a_reason() -> None:
    own = sources.load(EXAMPLES / "sources")
    radio = replace(RADIO, capability=replace(RADIO.capability, channels=1))
    selection = select(radio, [], own)
    rows = list(csv.DictReader(io.StringIO(chirp.render(selection))))
    assert [row["Name"] for row in rows] == ["2m Call"]
    assert ("70cm Call", "channel limit of 1 reached") in [(drop.name, drop.reason) for drop in selection.drops]


def test_a_channel_chirp_cannot_carry_takes_no_memory_and_is_dropped_with_the_reason() -> None:
    off_step = Channel("XX0OS", 145_600_100, 145_000_100, Mode.FM)
    first = Channel("XX0AA", 145_600_000, 145_000_000, Mode.FM)
    second = Channel("XX0BB", 145_612_500, 145_012_500, Mode.FM)
    radio = replace(
        RADIO,
        region=fleet.PrefixRegion(("XX",)),
        own_lists=(),
        capability=replace(RADIO.capability, channels=2),
    )
    selection = select(radio, [off_step, first, second], sources.load(EXAMPLES / "sources"), chirp.unfit)
    assert [channel.name for channel in selection.channels] == ["XX0AA", "XX0BB"]
    assert selection.drops == (Drop("XX0OS", "RX 145.600100 MHz is on no CHIRP tuning step"),)
    with pytest.raises(chirp.RenderError, match=r"XX0OS: RX 145\.600100 MHz is on no CHIRP tuning step"):
        chirp.render(Selection(RADIO, (off_step,), (), (), ()))


@pytest.mark.parametrize(
    ("channel_power", "radio_power", "written"),
    [("2.0W", "5.0W", "2.0W"), ("Low", "5.0W", "5.0W"), ("Low", None, ""), (None, None, "")],
)
def test_a_channel_power_in_watts_is_written_and_a_level_name_gives_the_profiles_watts(
    channel_power: str | None, radio_power: str | None, written: str
) -> None:
    radio = replace(RADIO, power=radio_power)
    channel = Channel("XX0FM", 145_600_000, 145_000_000, Mode.FM, power=channel_power)
    (row,) = csv.DictReader(io.StringIO(chirp.render(Selection(radio, (channel,), (), (), ()))))
    assert row["Power"] == written


def test_a_profile_power_that_is_not_watts_is_refused() -> None:
    channel = Channel("XX0FM", 145_600_000, 145_000_000, Mode.FM, power="High")
    with pytest.raises(chirp.RenderError, match="the profile's power 'High' is not CHIRP's watts"):
        chirp.render(Selection(replace(RADIO, power="High"), (channel,), (), (), ()))


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda text: text.replace("Location,", "Loc,"), "header is not CHIRP's columns"),
        (lambda text: text.replace(",simplex,", ",simplex,extra,"), "line 2 has 22 columns, not 21"),
        (lambda text: text.replace("2m Call", "2m Call is too long"), "exceeds 12 characters"),
        (lambda text: text + text.splitlines(keepends=True)[1], "2 rows for 1 channels"),
    ],
)
def test_the_csv_check_refuses_a_file_that_breaks_the_columns_or_limits(
    edit: Callable[[str], str], message: str
) -> None:
    selection = Selection(RADIO, (Channel("2m Call", 145_500_000, 145_500_000, Mode.FM, source="simplex"),), (), (), ())
    text = chirp.render(selection)
    with pytest.raises(CheckError, match=message):
        chirp.check(edit(text), selection)


def test_the_csv_check_refuses_more_rows_than_memories() -> None:
    channels = tuple(Channel(f"S{i}", 145_500_000, 145_500_000, Mode.FM) for i in range(2))
    radio = replace(RADIO, capability=replace(RADIO.capability, channels=1))
    selection = Selection(radio, channels, (), (), ())
    with pytest.raises(CheckError, match="2 rows, the radio has 1 memories"):
        chirp.check(chirp.render(selection), selection)
