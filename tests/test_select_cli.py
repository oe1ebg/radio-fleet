import re
from collections.abc import Callable
from pathlib import Path

import pytest
from conftest import DMR_REPEATER, FM_REPEATER, mcp_csv

from radio_fleet import fleet, snapshot, sources
from radio_fleet.cli import main

REPO = Path(__file__).resolve().parents[1]

SPEC_RADIOS = {
    "AnyTone D878UV II Plus",
    "AnyTone D168UV",
    "Baofeng UV-5R mini",
    "Baofeng UV-9R Pro",
    "Retevis RT95",
    "Yaesu FT5D",
    "Yaesu FT-3185",
    "Yaesu FTX-1",
    "Hytera HP785",
    "Hytera HM785",
}

FLEET = """
sources: [synthetic-db]
radios:
  synthetic:
    model: Synthetic 2m FM
    renderer: chirp
    capability:
      bands: [{name: 2m, rx: [136, 174], tx: [144, 146]}]
      modes: [FM]
      channels: 10
      name_length: 8
    region: {prefixes: [XX0]}
"""


def test_the_example_fleet_names_every_radio_of_the_spec_and_loads() -> None:
    the_fleet = fleet.load(REPO / "fleet.yaml")
    the_fleet.check_references(sources.load(REPO / "sources"))
    assert {radio.model for radio in the_fleet.radios.values()} == SPEC_RADIOS
    assert the_fleet.sources[0] == "oevsv-repeater-db"


def test_select_prints_the_channels_drops_and_overrides(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "fleet.yaml").write_text(FLEET)
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "overrides.yaml").write_text(
        "overrides: [{callsign: XX0FM, reason: synthetic reason, set: {tone_tx: {ctcss: 77.0}, rx: 145.6125}}]\n"
    )
    snapshot.write(tmp_path / "snapshots", "synthetic-db", mcp_csv([FM_REPEATER, DMR_REPEATER]))
    args = ["--fleet", str(tmp_path / "fleet.yaml"), "--snapshots", str(tmp_path / "snapshots")]
    assert main(["select", "--radio", "synthetic", "--sources", str(tmp_path / "sources"), *args]) == 0
    out = capsys.readouterr().out
    assert out.startswith("synthetic (Synthetic 2m FM): 1 channels, 0 zones\n")
    assert re.search(r"XX0FM +RX 145.61250 TX 145.00000 FM tone TX CTCSS 77 tone RX CTCSS 88.5", out)
    assert "  XX0DM: mode DMR not supported\n" in out
    assert "  XX0FM FM: tone_tx=CTCSS 77, rx_hz=145.61250 MHz (synthetic reason)\n" in out


def headless_snapshot(directory: Path) -> None:
    (directory / "snapshots").mkdir()
    (directory / "snapshots" / "synthetic-db.csv").write_text("callsign,fm\n")


@pytest.mark.parametrize(
    ("setup", "message"),
    [
        (lambda d: None, "no snapshot for 'synthetic-db'"),
        (headless_snapshot, "lacks columns"),
        (lambda d: (d / "fleet.yaml").write_text(FLEET.replace("XX0", "[XX0")), "fleet.yaml"),
        (lambda d: (d / "fleet.yaml").write_text(FLEET.replace("  synthetic:", "  other:")), "no radio 'synthetic'"),
    ],
)
def test_select_reports_a_bad_input_and_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], setup: Callable[[Path], object], message: str
) -> None:
    (tmp_path / "fleet.yaml").write_text(FLEET)
    setup(tmp_path)
    args = ["--fleet", str(tmp_path / "fleet.yaml"), "--snapshots", str(tmp_path / "snapshots")]
    assert main(["select", "--radio", "synthetic", "--sources", str(tmp_path), *args]) == 1
    assert message in capsys.readouterr().err
