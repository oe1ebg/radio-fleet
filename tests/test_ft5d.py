import csv
import io
import shutil
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import pytest

from radio_fleet import fleet
from radio_fleet.cli import main
from radio_fleet.fleet import Radio
from radio_fleet.mcp import ExportError, McpCli
from radio_fleet.model import Channel, Ctcss, Dcs, Mode
from radio_fleet.render import ft5d
from radio_fleet.render.csvcheck import CsvCheckError
from radio_fleet.selection import Group, Selection

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
FIRST_BANK = 28


def radio() -> Radio:
    return fleet.load(EXAMPLES / "fleet.yaml", EXAMPLES).radios["ft5d"]


SIMPLEX = Channel("XX0 Call", 145_500_000, 145_500_000, Mode.FM, source="simplex")
REPEATER_FM = Channel("XX0RP", 145_612_500, 145_012_500, Mode.FM, tone_tx=Ctcss(88.5), tone_rx=Ctcss(88.5))
REPEATER_C4FM = Channel("XX0RP", 145_612_500, 145_012_500, Mode.C4FM)
DIGITAL = Channel("XX0DN", 438_962_500, 431_362_500, Mode.C4FM)
TONE = Channel("XX0TN", 438_650_000, 431_050_000, Mode.FM, tone_tx=Ctcss(123.0))
CHANNELS = (SIMPLEX, REPEATER_FM, REPEATER_C4FM, DIGITAL, TONE)
ZONES = (Group("Simplex", (SIMPLEX,)), Group("C4FM", (REPEATER_C4FM, DIGITAL)), Group("FM", (REPEATER_FM, TONE)))


def selection(channels: tuple[Channel, ...] = CHANNELS, zones: tuple[Group, ...] = ZONES) -> Selection:
    return Selection(radio(), channels, zones, (), (), ())


def banks(row: Sequence[str]) -> list[int]:
    return [bank for bank in range(1, 25) if row[FIRST_BANK + bank - 1] == "ON"]


def test_a_synthetic_selection_gives_an_ft5d_csv_with_the_expected_banks() -> None:
    text = ft5d.render(selection(), McpCli())
    ft5d.check(text, radio().capability)
    table = list(csv.reader(io.StringIO(text)))
    assert len(table) == 900
    assert [row[0] for row in table] == [str(n) for n in range(1, 901)]
    memories = [row for row in table if row[2]]
    assert [(row[10], row[2], row[3], row[8], row[11], row[12]) for row in memories] == [
        ("XX0 Call", "145.50000", "145.50000", "FM", "OFF", "88.5 Hz"),
        ("XX0RP", "145.61250", "145.01250", "AMS", "TONE SQL", "88.5 Hz"),
        ("XX0DN", "438.96250", "431.36250", "DN", "OFF", "88.5 Hz"),
        ("XX0TN", "438.65000", "431.05000", "FM", "TONE", "123.0 Hz"),
    ]
    assert [banks(row) for row in memories] == [[1], [2, 3], [2], [3]]


class FakeMcp:
    def __init__(self, keep: int | None = None) -> None:
        self.keep = keep
        self.calls: list[tuple[list[dict[str, str]], str, list[str]]] = []

    def export(self, channels_csv: str, output_format: str, options: Sequence[str]) -> str:
        rows = list(csv.DictReader(io.StringIO(channels_csv)))
        self.calls.append((rows, output_format, list(options)))
        written = rows[: self.keep]
        filler = ["" for _ in range(ft5d.WIDTH - 3)]
        return "".join(
            ",".join([str(n), "OFF", row["freq_rx"] if row in written else "", *filler]) + "\n"
            for n, row in enumerate(rows, 1)
        )


def test_the_memories_and_banks_go_to_mcp_as_its_csv_and_bank_filters() -> None:
    mcp = FakeMcp()
    ft5d.render(selection(), mcp)
    ((rows, output_format, options),) = mcp.calls
    assert output_format == "yaesu-ft5d"
    assert options == [
        "--sort",
        "scan_group",
        "--yaesu-bank",
        "1:scan_group==1",
        "2:scan_group==2",
        "2:scan_group==3",
        "3:scan_group==2",
        "3:scan_group==4",
    ]
    assert [(r["callsign"], r["scan_group"], r["band"], r["fm"], r["c4fm"], r["ctcss_tx"]) for r in rows] == [
        ("XX0 Call", "1", "2m", "True", "False", ""),
        ("XX0RP", "2", "2m", "True", "True", "88.5"),
        ("XX0DN", "3", "70cm", "False", "True", ""),
        ("XX0TN", "4", "70cm", "True", "False", "123"),
    ]
    assert rows[0]["source_id"] == "simplex"
    assert rows[1]["freq_rx"] == "145.612500" and rows[1]["freq_tx"] == "145.012500"


def test_a_memory_that_mcp_does_not_write_fails_the_render() -> None:
    with pytest.raises(ft5d.RenderError, match="memory-channels-processor wrote 3 memories for 4"):
        ft5d.render(selection(), FakeMcp(keep=3))


@pytest.mark.parametrize(
    ("channels", "message"),
    [
        ((replace(TONE, tone_tx=Dcs(23)),), "XX0TN: memory-channels-processor's FT5D output carries no DCS"),
        ((replace(TONE, tone_rx=Ctcss(88.5)),), "XX0TN: .* takes an RX tone only equal to the TX tone"),
        ((replace(TONE, tone_tx=None, tone_rx=Ctcss(88.5)),), "takes an RX tone only equal to the TX tone"),
        ((replace(TONE, mode=Mode.DMR),), "XX0TN: the FT5D renderer carries FM and C4FM, not DMR"),
        ((TONE, replace(TONE, tone_tx=None)), "XX0TN: another FM channel has its name and frequencies"),
    ],
)
def test_a_channel_the_ft5d_output_cannot_carry_is_refused(channels: tuple[Channel, ...], message: str) -> None:
    with pytest.raises(ft5d.RenderError, match=message):
        ft5d.render(selection(channels, ()), FakeMcp())


def test_more_zones_than_banks_are_refused() -> None:
    zones = tuple(Group(f"Z{n}", (SIMPLEX,)) for n in range(25))
    with pytest.raises(ft5d.RenderError, match="25 zones, the FT5D has 24 banks"):
        ft5d.render(selection((SIMPLEX,), zones), FakeMcp())


def test_the_csv_check_refuses_rows_the_radio_cannot_take() -> None:
    text = ft5d.render(selection(), FakeMcp())
    lines = text.splitlines()
    lines[1] += ","
    with pytest.raises(CsvCheckError, match="row 2: 55 columns, expected 54"):
        ft5d.check("\n".join(lines), radio().capability)
    with pytest.raises(CsvCheckError, match="4 memories, the radio has 3"):
        ft5d.check(text, replace(radio().capability, channels=3))


FAKE_MCP_SCRIPT = """
import sys
args = sys.argv[1:]
channels = open("channels.csv").read()
if "--fail" in args:
    print("Unable to get a template for the specified options!")
    sys.exit(1)
out = args[args.index("--output-file") + 1]
open(out, "w").write(" ".join(args[: args.index("--output-file")]) + "\\n" + channels)
"""


def test_mcp_cli_exports_a_csv_input_through_an_output_format(tmp_path: Path) -> None:
    script = tmp_path / "fake_mcp.py"
    script.write_text(FAKE_MCP_SCRIPT)
    cli = McpCli(command=[sys.executable, str(script)])
    assert cli.export("callsign\nXX0FM\n", "yaesu-ft5d", ["--sort", "scan_group"]) == (
        "--source csv --csv-input-file channels.csv --offline --output-format yaesu-ft5d --sort scan_group\n"
        "callsign\nXX0FM\n"
    )
    with pytest.raises(ExportError, match="failed for the yaesu-ft5d output: Unable to get a template"):
        cli.export("callsign\nXX0FM\n", "yaesu-ft5d", ["--fail"])


def test_build_writes_the_checked_ft5d_csv(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data = tmp_path / "data"
    shutil.copytree(EXAMPLES, data)
    assert main(["build", "--data", str(data), "--radio", "ft5d"]) == 0
    output = data / "build" / "ft5d" / "ft5d.csv"
    assert capsys.readouterr().out == f"ft5d: {output}\n"
    names = [row[10] for row in csv.reader(io.StringIO(output.read_text(encoding="utf-8"))) if row[2]]
    assert names == ["2m Call", "70cm Call", "C4FM Call", "XX1AA", "XX3DD", "XX5FF"]


def test_a_channel_with_dcs_fails_the_ft5d_build_and_names_the_radio(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = tmp_path / "data"
    shutil.copytree(EXAMPLES, data)
    fleet_file = data / "fleet.yaml"
    fleet_file.write_text(
        fleet_file.read_text().replace('      exclude: {XX1CC: "DCS, which MCP\'s FT5D output cannot carry"}\n', "")
    )
    assert main(["build", "--data", str(data), "--radio", "ft5d"]) == 1
    assert capsys.readouterr().err == (
        "fleet build: ft5d: channel XX1CC: memory-channels-processor's FT5D output carries no DCS\n"
    )
