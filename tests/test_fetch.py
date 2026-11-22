import re
import sys
from pathlib import Path

import pytest
from conftest import DMR_REPEATER, FM_REPEATER, mcp_csv, mcp_row

from radio_fleet.cli import main
from radio_fleet.mcp import Fetcher, FetchError, McpCli


class FakeMcp:
    def __init__(self, csv_text: str) -> None:
        self.csv_text = csv_text
        self.sources: list[str] = []

    def fetch_csv(self, source: str) -> str:
        self.sources.append(source)
        return self.csv_text


def fleet_file(directory: Path, *sources: str) -> str:
    path = directory / "fleet.yaml"
    path.write_text(f"sources: [{', '.join(sources)}]\nradios: {{}}\n")
    return str(path)


class NoNetwork:
    def fetch_csv(self, source: str) -> str:
        raise AssertionError("offline fetch must not call MCP")


def test_fetch_writes_a_snapshot_for_each_source_of_the_fleet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeMcp(mcp_csv([FM_REPEATER, DMR_REPEATER]))
    fleet = fleet_file(tmp_path, "synthetic-a", "synthetic-b")
    assert main(["fetch", "--fleet", fleet, "--snapshots", str(tmp_path)], fetcher=fake) == 0
    assert fake.sources == ["synthetic-a", "synthetic-b"]
    assert (tmp_path / "synthetic-a.csv").exists()
    assert (tmp_path / "synthetic-b.csv").exists()
    assert "synthetic-b: 2 channels" in capsys.readouterr().out


class OneSourceUp:
    def fetch_csv(self, source: str) -> str:
        if source != "synthetic-up":
            raise FetchError(f"memory-channels-processor failed for source {source!r}: synthetic outage")
        return mcp_csv([FM_REPEATER])


def test_a_failing_source_does_not_stop_the_others(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fleet = fleet_file(tmp_path, "synthetic-down", "synthetic-up", "synthetic-gone")
    assert main(["fetch", "--fleet", fleet, "--snapshots", str(tmp_path)], fetcher=OneSourceUp()) == 1
    captured = capsys.readouterr()
    assert captured.out == f"synthetic-up: 1 channels in {tmp_path / 'synthetic-up.csv'}\n"
    assert "'synthetic-down': synthetic outage" in captured.err
    assert "'synthetic-gone': synthetic outage" in captured.err


class UnreadableSources:
    def fetch_csv(self, source: str) -> str:
        if source == "synthetic-binary":
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
        if source == "synthetic-denied":
            raise PermissionError(13, "Permission denied", "synthetic-denied.csv")
        return mcp_csv([FM_REPEATER])


def test_a_source_failing_with_an_os_or_decode_error_does_not_stop_the_others(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fleet = fleet_file(tmp_path, "synthetic-binary", "synthetic-denied", "synthetic-up")
    assert main(["fetch", "--fleet", fleet, "--snapshots", str(tmp_path)], fetcher=UnreadableSources()) == 1
    captured = capsys.readouterr()
    assert captured.out == f"synthetic-up: 1 channels in {tmp_path / 'synthetic-up.csv'}\n"
    assert "'synthetic-binary': 'utf-8' codec can't decode" in captured.err
    assert "'synthetic-denied': [Errno 13] Permission denied" in captured.err


def test_fetch_without_a_fleet_file_exits_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["fetch", "--fleet", str(tmp_path / "none.yaml")], fetcher=NoNetwork()) == 1
    assert "no file" in capsys.readouterr().err


def test_offline_fetch_reads_the_snapshot_without_mcp(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(
        ["fetch", "--source", "oevsv-repeater-db", "--snapshots", str(tmp_path)],
        fetcher=FakeMcp(mcp_csv([FM_REPEATER])),
    )
    before = (tmp_path / "oevsv-repeater-db.csv").read_bytes()
    capsys.readouterr()
    assert (
        main(["fetch", "--source", "oevsv-repeater-db", "--offline", "--snapshots", str(tmp_path)], fetcher=NoNetwork())
        == 0
    )
    assert "oevsv-repeater-db: 1 channels" in capsys.readouterr().out
    assert (tmp_path / "oevsv-repeater-db.csv").read_bytes() == before


def test_offline_fetch_without_a_snapshot_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(["fetch", "--source", "oevsv-repeater-db", "--offline", "--snapshots", str(tmp_path)], fetcher=NoNetwork())
        == 1
    )
    assert "no snapshot for 'oevsv-repeater-db'" in capsys.readouterr().err


FAKE_MCP_SCRIPT = """
import re
import sys
args = sys.argv[1:]
if args[args.index("--source") + 1] == "broken":
    print("The data source(s) returned an empty dataset!")
    sys.exit(1)
if args[args.index("--source") + 1] == "binary":
    open(args[args.index("--output-file") + 1], "wb").write(b"callsign\\n\\xff\\n")
    sys.exit(0)
assert args[args.index("--output-format") + 1] == "csv" and "--no-cache" in args
open(args[args.index("--output-file") + 1], "w").write("callsign\\r\\nXX0FM\\r\\n")
"""


def test_mcp_cli_runs_mcp_with_csv_output(tmp_path: Path) -> None:
    script = tmp_path / "fake_mcp.py"
    script.write_text(FAKE_MCP_SCRIPT)
    cli = McpCli(command=[sys.executable, str(script)])
    assert cli.fetch_csv("synthetic-db") == "callsign\nXX0FM\n"
    with pytest.raises(FetchError, match=r"'broken'.*empty dataset"):
        cli.fetch_csv("broken")
    with pytest.raises(FetchError, match=r"output for source 'binary' is unreadable"):
        cli.fetch_csv("binary")


def test_a_missing_mcp_is_reported_as_a_missing_tool(tmp_path: Path) -> None:
    cli = McpCli(command=[str(tmp_path / "no-such-mcp")])
    with pytest.raises(FetchError, match="memory-channels-processor is not installed"):
        cli.fetch_csv("synthetic-db")


class FailingMcp:
    def fetch_csv(self, source: str) -> str:
        raise FetchError(f"memory-channels-processor failed for source {source!r}: synthetic outage")


@pytest.mark.parametrize(
    ("fetcher", "message"),
    [
        (FailingMcp(), "synthetic outage"),
        (FakeMcp("callsign,freq_tx\r\nXX0FM,145.0\r\n"), "lacks columns"),
        (FakeMcp(mcp_csv([FM_REPEATER, mcp_row(callsign="XX0BAD", fm="maybe")])), "'XX0BAD'.*not a boolean"),
    ],
)
def test_a_failed_fetch_exits_1_and_keeps_the_snapshot(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fetcher: Fetcher, message: str
) -> None:
    main(
        ["fetch", "--source", "oevsv-repeater-db", "--snapshots", str(tmp_path)],
        fetcher=FakeMcp(mcp_csv([DMR_REPEATER])),
    )
    before = (tmp_path / "oevsv-repeater-db.csv").read_bytes()
    capsys.readouterr()
    assert main(["fetch", "--source", "oevsv-repeater-db", "--snapshots", str(tmp_path)], fetcher=fetcher) == 1
    captured = capsys.readouterr()
    assert re.search(f"^fleet fetch: .*{message}", captured.err)
    assert captured.out == ""
    assert (tmp_path / "oevsv-repeater-db.csv").read_bytes() == before


def test_fetch_reads_the_snapshots_of_the_data_root(capsys: pytest.CaptureFixture[str]) -> None:
    examples = Path(__file__).resolve().parents[1] / "examples"
    assert main(["fetch", "--data", str(examples), "--offline"], fetcher=NoNetwork()) == 0
    assert capsys.readouterr().out.endswith(f"in {examples / 'snapshots' / 'oevsv-repeater-db.csv'}\n")
