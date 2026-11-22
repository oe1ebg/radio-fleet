import re
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from conftest import DMR_REPEATER, FM_REPEATER, mcp_csv

from radio_fleet import fleet, snapshot, sources
from radio_fleet.cli import main

REPO = Path(__file__).resolve().parents[1]
EXAMPLES = REPO / "examples"

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
    the_fleet = fleet.load(EXAMPLES / "fleet.yaml", EXAMPLES)
    the_fleet.check_references(sources.load(EXAMPLES / "sources"))
    assert {radio.model for radio in the_fleet.radios.values()} == SPEC_RADIOS
    assert the_fleet.sources[0] == "oevsv-repeater-db"


def output(capsys: pytest.CaptureFixture[str], argv: list[str]) -> str:
    assert main(argv) == 0, capsys.readouterr().err
    return capsys.readouterr().out


def test_the_data_root_comes_from_data_else_fleet_data_else_the_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("FLEET_DATA", raising=False)
    monkeypatch.chdir(EXAMPLES)
    in_root = output(capsys, ["select", "--radio", "d878uv2plus"])
    assert in_root.startswith("d878uv2plus (AnyTone D878UV II Plus): ")
    assert "km from JJ00mm, beyond 80 km" in in_root

    monkeypatch.chdir(REPO)
    assert output(capsys, ["select", "--data", "examples", "--radio", "d878uv2plus"]) == in_root
    monkeypatch.chdir(tmp_path)
    assert output(capsys, ["select", "--data", str(EXAMPLES), "--radio", "d878uv2plus"]) == in_root

    monkeypatch.setenv("FLEET_DATA", str(EXAMPLES))
    assert output(capsys, ["select", "--radio", "d878uv2plus"]) == in_root
    monkeypatch.setenv("FLEET_DATA", str(tmp_path))
    assert output(capsys, ["select", "--data", str(EXAMPLES), "--radio", "d878uv2plus"]) == in_root


def test_an_own_list_that_is_named_but_missing_fails_with_its_file_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    shutil.copytree(EXAMPLES, tmp_path / "data")
    (tmp_path / "data" / "sources" / "own" / "simplex.yaml").unlink()
    assert main(["select", "--data", str(tmp_path / "data"), "--radio", "uv5r-mini"]) == 1
    assert f"no file {tmp_path / 'data' / 'sources' / 'own' / 'simplex.yaml'}" in capsys.readouterr().err


def test_options_that_name_one_path_win_over_the_data_root(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data, elsewhere = tmp_path / "data", tmp_path / "elsewhere"
    (data / "bases").mkdir(parents=True)
    (data / "bases" / "synthetic.yaml").write_text("synthetic: base\n")
    snapshot.write(elsewhere / "snapshots", "synthetic-db", mcp_csv([FM_REPEATER]))
    (elsewhere / "sources").mkdir()
    (elsewhere / "fleet.yaml").write_text(
        FLEET.replace("renderer: chirp\n", "renderer: chirp\n    base: bases/synthetic.yaml\n")
    )
    paths = ["--fleet", str(elsewhere / "fleet.yaml"), "--sources", str(elsewhere / "sources")]
    selected = output(
        capsys,
        ["select", "--data", str(data), "--radio", "synthetic", *paths, "--snapshots", str(elsewhere / "snapshots")],
    )
    assert selected.startswith("synthetic (Synthetic 2m FM): 1 channels")

    (data / "bases" / "synthetic.yaml").unlink()
    assert (
        main(
            ["select", "--data", str(data), "--radio", "synthetic", *paths, "--snapshots", str(elsewhere / "snapshots")]
        )
        == 1
    )
    assert f"radios.synthetic.base: no file {data / 'bases' / 'synthetic.yaml'}" in capsys.readouterr().err


def test_select_prints_the_channels_drops_and_overrides(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "fleet.yaml").write_text(FLEET)
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "overrides.yaml").write_text(
        "overrides: [{callsign: XX0FM, reason: synthetic reason,"
        " set: {tone_tx: {ctcss: 77.0}, rx: 145.6125, bandwidth: 12.5}},"
        " {callsign: XX0FM, band: 70cm, reason: no 70cm channel, clear: tone_rx}]\n"
    )
    snapshot.write(tmp_path / "snapshots", "synthetic-db", mcp_csv([FM_REPEATER, DMR_REPEATER]))
    args = ["--fleet", str(tmp_path / "fleet.yaml"), "--snapshots", str(tmp_path / "snapshots")]
    assert main(["select", "--radio", "synthetic", "--sources", str(tmp_path / "sources"), *args]) == 0
    out = capsys.readouterr().out
    assert out.startswith("synthetic (Synthetic 2m FM): 1 channels, 0 zones, 0 scan lists\n")
    assert re.search(r"XX0FM +RX 145.61250 TX 145.00000 FM tone TX CTCSS 77 tone RX CTCSS 88.5", out)
    assert "  XX0DM: mode DMR not supported\n" in out
    assert out.endswith(
        "overrides: 1\n"
        "  XX0FM FM 2m: tone_tx=CTCSS 77, rx_hz=145.61250 MHz, bandwidth_hz=12.5 kHz (synthetic reason)\n"
        "overrides that match nothing: 1\n"
        "  XX0FM 70cm: tone_rx=- (no 70cm channel)\n"
    )


def headless_snapshot(directory: Path) -> None:
    (directory / "snapshots").mkdir()
    (directory / "snapshots" / "synthetic-db.csv").write_text("callsign,fm\n")


@pytest.mark.parametrize(
    ("setup", "message"),
    [
        (lambda d: None, "no snapshot for 'synthetic-db'"),
        (headless_snapshot, "lacks columns"),
        (lambda d: (d / "fleet.yaml").unlink(), "no file"),
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
