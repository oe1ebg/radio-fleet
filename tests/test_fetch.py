import re
import sys
from pathlib import Path

import pytest

from conftest import DMR_REPEATER, FM_REPEATER, mcp_csv, mcp_row
from radio_fleet.cli import main
from radio_fleet.mcp import FetchError, McpCli


class FakeMcp:
    def __init__(self, csv_text: str) -> None:
        self.csv_text = csv_text
        self.sources: list[str] = []

    def fetch_csv(self, source: str) -> str:
        self.sources.append(source)
        return self.csv_text


class NoNetwork:
    def fetch_csv(self, source: str) -> str:
        raise AssertionError("offline fetch must not call MCP")


def test_fetch_writes_the_snapshot_of_the_default_source(tmp_path: Path, capsys):
    fake = FakeMcp(mcp_csv([FM_REPEATER, DMR_REPEATER]))
    assert main(["fetch", "--snapshots", str(tmp_path)], fetcher=fake) == 0
    assert fake.sources == ["oevsv-repeater-db"]
    assert (tmp_path / "oevsv-repeater-db.csv").exists()
    assert "oevsv-repeater-db: 2 channels" in capsys.readouterr().out


def test_offline_fetch_reads_the_snapshot_without_mcp(tmp_path: Path, capsys):
    main(["fetch", "--snapshots", str(tmp_path)], fetcher=FakeMcp(mcp_csv([FM_REPEATER])))
    before = (tmp_path / "oevsv-repeater-db.csv").read_bytes()
    capsys.readouterr()
    assert main(["fetch", "--offline", "--snapshots", str(tmp_path)], fetcher=NoNetwork()) == 0
    assert "oevsv-repeater-db: 1 channels" in capsys.readouterr().out
    assert (tmp_path / "oevsv-repeater-db.csv").read_bytes() == before


def test_offline_fetch_without_a_snapshot_fails(tmp_path: Path, capsys):
    assert main(["fetch", "--offline", "--snapshots", str(tmp_path)], fetcher=NoNetwork()) == 1
    assert "no snapshot for 'oevsv-repeater-db'" in capsys.readouterr().err


FAKE_MCP_SCRIPT = """
import re
import sys
args = sys.argv[1:]
if args[args.index("--source") + 1] == "broken":
    print("The data source(s) returned an empty dataset!")
    sys.exit(1)
assert args[args.index("--output-format") + 1] == "csv" and "--no-cache" in args
open(args[args.index("--output-file") + 1], "w").write("callsign\\r\\nXX0FM\\r\\n")
"""


def test_mcp_cli_runs_mcp_with_csv_output(tmp_path: Path):
    script = tmp_path / "fake_mcp.py"
    script.write_text(FAKE_MCP_SCRIPT)
    cli = McpCli(command=[sys.executable, str(script)])
    assert cli.fetch_csv("synthetic-db") == "callsign\nXX0FM\n"
    with pytest.raises(FetchError, match="'broken'.*empty dataset"):
        cli.fetch_csv("broken")


class FailingMcp:
    def fetch_csv(self, source: str) -> str:
        raise FetchError(f"memory-channels-processor failed for source {source!r}: synthetic outage")


@pytest.mark.parametrize(("fetcher", "message"), [
    (FailingMcp(), "synthetic outage"),
    (FakeMcp("callsign,freq_tx\r\nXX0FM,145.0\r\n"), "lacks columns"),
    (FakeMcp(mcp_csv([FM_REPEATER, mcp_row(callsign="XX0BAD", fm="maybe")])), "'XX0BAD'.*not a boolean"),
])
def test_a_failed_fetch_exits_1_and_keeps_the_snapshot(tmp_path: Path, capsys, fetcher, message: str):
    main(["fetch", "--snapshots", str(tmp_path)], fetcher=FakeMcp(mcp_csv([DMR_REPEATER])))
    before = (tmp_path / "oevsv-repeater-db.csv").read_bytes()
    capsys.readouterr()
    assert main(["fetch", "--snapshots", str(tmp_path)], fetcher=fetcher) == 1
    captured = capsys.readouterr()
    assert re.search(f"^fleet fetch: .*{message}", captured.err)
    assert captured.out == ""
    assert (tmp_path / "oevsv-repeater-db.csv").read_bytes() == before
