import csv
import io
from collections.abc import Sequence
from pathlib import Path

import pytest

from radio_fleet import fleet
from radio_fleet.dmrconf import CheckError
from radio_fleet.mcp import McpCli
from radio_fleet.model import Channel, Ctcss, Dcs, Mode
from radio_fleet.render import ft5d
from radio_fleet.selection import Selection, Zone

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
RADIO = fleet.load(EXAMPLES / "fleet.yaml", EXAMPLES).radios["ft5d"]

REPEATER = Channel("XX0FM", 145_600_000, 145_000_000, Mode.FM, tone_tx=Ctcss(88.5), tone_rx=Ctcss(88.5))
DIGITAL = Channel("XX0FM", 145_600_000, 145_000_000, Mode.C4FM)
SIMPLEX = Channel("2m Call", 145_500_000, 145_500_000, Mode.FM)
UHF = Channel("XX0UP", 438_625_000, 431_025_000, Mode.FM, tone_tx=Ctcss(123.0))
CHANNELS = (REPEATER, DIGITAL, SIMPLEX, UHF)
SELECTION = Selection(
    RADIO,
    CHANNELS,
    (Zone("FM", (REPEATER, SIMPLEX, UHF)), Zone("C4FM", (DIGITAL,)), Zone("Simplex", (SIMPLEX,))),
    (),
    (),
)


class FakeMcp:
    def __init__(self) -> None:
        self.calls: list[tuple[list[dict[str, str]], str, list[str]]] = []

    def convert(self, channels_csv: str, output_format: str, options: Sequence[str]) -> str:
        self.calls.append((list(csv.DictReader(io.StringIO(channels_csv))), output_format, list(options)))
        return "converted"


def test_a_selection_gives_mcps_ft5d_csv_with_the_expected_banks() -> None:
    text = ft5d.render(SELECTION, McpCli())
    ft5d.check(text, SELECTION)
    rows = [line.split(",") for line in text.splitlines()]
    assert len(rows) == ft5d.MEMORIES
    memories = [row for row in rows if row[2]]
    assert [(row[0], row[2], row[3], row[8], row[10], row[11], row[12]) for row in memories] == [
        ("1", "145.60000", "145.00000", "FM", "XX0FM", "TONE SQL", "88.5 Hz"),
        ("2", "145.60000", "145.00000", "DN", "XX0FM", "OFF", "88.5 Hz"),
        ("3", "145.50000", "145.50000", "FM", "2m Call", "OFF", "88.5 Hz"),
        ("4", "438.62500", "431.02500", "FM", "XX0UP", "TONE", "123.0 Hz"),
    ]
    banks = [[bank for bank in range(1, ft5d.BANKS + 1) if row[27 + bank] == "ON"] for row in memories]
    assert banks == [[1], [2], [1, 3], [1]]


def test_the_selection_goes_to_mcp_with_one_bank_filter_per_zone() -> None:
    mcp = FakeMcp()
    assert ft5d.render(SELECTION, mcp) == "converted"
    ((rows, output_format, options),) = mcp.calls
    assert output_format == "yaesu-ft5d"
    assert options == [
        "--name-format",
        "name",
        "--sort",
        "scan_group",
        "--yaesu-bank",
        "1:comment~=;b01;",
        "2:comment~=;b02;",
        "3:comment~=;b03;",
    ]
    keys = ("callsign", "name", "band", "freq_rx", "fm", "c4fm", "comment", "scan_group")
    assert [tuple(row[key] for key in keys) for row in rows] == [
        ("M001", "XX0FM", "2m", "145.600000", "True", "False", ";b01;", "1"),
        ("M002", "XX0FM", "2m", "145.600000", "False", "True", ";b02;", "2"),
        ("M003", "2m Call", "2m", "145.500000", "True", "False", ";b01;b03;", "3"),
        ("M004", "XX0UP", "70cm", "438.625000", "True", "False", ";b01;", "4"),
    ]


@pytest.mark.parametrize(
    ("channel", "message"),
    [
        (Channel("XX0DM", 438_962_500, 431_462_500, Mode.DMR), "carries FM and C4FM, not DMR"),
        (Channel("Hill, Big", 145_500_000, 145_500_000, Mode.FM), "cannot hold , or"),
        (Channel("XX0DC", 438_625_000, 431_025_000, Mode.FM, tone_tx=Dcs(23)), "one CTCSS tone, no DCS"),
        (
            Channel("XX0SP", 438_625_000, 431_025_000, Mode.FM, tone_tx=Ctcss(77.0), tone_rx=Ctcss(88.5)),
            "one CTCSS tone",
        ),
    ],
)
def test_a_channel_mcp_cannot_write_for_the_ft5d_is_refused(channel: Channel, message: str) -> None:
    with pytest.raises(ft5d.RenderError, match=message):
        ft5d.render(Selection(RADIO, (channel,), (), (), ()), FakeMcp())


def test_more_zones_than_banks_are_refused() -> None:
    zones = tuple(Zone(f"Z{i}", (SIMPLEX,)) for i in range(ft5d.BANKS + 1))
    with pytest.raises(ft5d.RenderError, match="25 zones, the FT5D has 24 banks"):
        ft5d.render(Selection(RADIO, (SIMPLEX,), zones, (), ()), FakeMcp())


def empty_memory(number: int) -> str:
    return f"{number}," + "," * (ft5d.WIDTH - 2) + "0"


@pytest.mark.parametrize(
    ("lines", "message"),
    [
        ([empty_memory(n) for n in range(1, ft5d.MEMORIES)], "899 rows, the FT5D import has 900"),
        ([empty_memory(n) for n in range(1, ft5d.MEMORIES + 1)], "0 memories for 1 channels"),
        ([empty_memory(n + 1) for n in range(1, ft5d.MEMORIES + 1)], "row 1 is not memory 1 with 54 columns"),
    ],
)
def test_the_csv_check_refuses_a_file_without_the_memories_of_the_selection(lines: list[str], message: str) -> None:
    with pytest.raises(CheckError, match=message):
        ft5d.check("\n".join(lines) + "\n", Selection(RADIO, (SIMPLEX,), (), (), ()))


def test_the_csv_check_refuses_a_bank_column_that_is_not_on_or_off() -> None:
    text = ft5d.render(Selection(RADIO, (SIMPLEX,), (Zone("Simplex", (SIMPLEX,)),), (), ()), McpCli())
    first, rest = text.split("\n", 1)
    fields = first.split(",")
    fields[28] = "YES"
    with pytest.raises(CheckError, match="row 1 has a bank column that is not ON or OFF"):
        ft5d.check(",".join(fields) + "\n" + rest, Selection(RADIO, (SIMPLEX,), (), (), ()))
