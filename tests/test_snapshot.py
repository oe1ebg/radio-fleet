from pathlib import Path

import pytest
from conftest import DMR_REPEATER, FM_REPEATER, mcp_csv, mcp_row

from radio_fleet import snapshot
from radio_fleet.model import Channel, Ctcss, Dcs, Mode


def test_fm_repeater_row_converts() -> None:
    assert list(snapshot.channels_from_rows([FM_REPEATER])) == [
        Channel(
            name="XX0FM",
            rx_hz=145_600_000,
            tx_hz=145_000_000,
            mode=Mode.FM,
            tone_tx=Ctcss(88.5),
            tone_rx=Ctcss(88.5),
            source="synthetic-db",
        ),
    ]


def test_dmr_repeater_row_converts() -> None:
    assert list(snapshot.channels_from_rows([DMR_REPEATER])) == [
        Channel(name="XX0DM", rx_hz=438_962_500, tx_hz=431_462_500, mode=Mode.DMR, color_code=1, source="synthetic-db"),
    ]


def test_multimode_row_gives_one_channel_per_mode_and_tones_only_on_fm() -> None:
    row = mcp_row(
        callsign="XX0MM",
        freq_tx="439.0",
        freq_rx="431.4",
        ctcss_tx="77.0",
        dtcs_rx="23",
        bandwidth="12.5",
        fm="True",
        dmr="True",
        c4fm="True",
        dstar="True",
        dmr_cc="3",
    )
    channels = list(snapshot.channels_from_rows([row]))
    assert [c.mode for c in channels] == [Mode.FM, Mode.DMR, Mode.C4FM, Mode.DSTAR]
    fm, dmr = channels[0], channels[1]
    assert (fm.tone_tx, fm.tone_rx, fm.color_code, fm.bandwidth_hz) == (Ctcss(77.0), Dcs(23), None, 12_500)
    assert (dmr.tone_tx, dmr.tone_rx, dmr.color_code) == (None, None, 3)


def test_two_fetches_of_the_same_data_give_identical_snapshots(tmp_path: Path) -> None:
    other = mcp_row(callsign="XX0FM", band="70cm", freq_tx="430.0", freq_rx="437.6", fm="True")
    first = snapshot.write(tmp_path / "a", "synthetic-db", mcp_csv([DMR_REPEATER, other, FM_REPEATER])).read_bytes()
    second = snapshot.write(tmp_path / "b", "synthetic-db", mcp_csv([FM_REPEATER, DMR_REPEATER, other])).read_bytes()
    assert first == second
    lines = first.decode().split("\n")
    assert lines[0] == ",".join(snapshot.COLUMNS)
    assert [line.split(",")[:4] for line in lines[1:4]] == [
        ["XX0DM", "Synthetic Tower", "70cm", "431.4625"],
        ["XX0FM", "Synthetic Hill", "2m", "145.0"],
        ["XX0FM", "", "70cm", "430.0"],
    ]
    assert "\r" not in first.decode()


def test_snapshot_reads_back_into_channels(tmp_path: Path) -> None:
    path = snapshot.write(tmp_path, "synthetic-db", mcp_csv([FM_REPEATER, DMR_REPEATER]))
    assert [(c.name, c.mode) for c in snapshot.read(path)] == [("XX0DM", Mode.DMR), ("XX0FM", Mode.FM)]


def test_mcp_output_without_a_snapshot_column_is_refused() -> None:
    with pytest.raises(snapshot.SnapshotError, match="callsign"):
        snapshot.normalize("name,freq_tx\r\nX,145.0\r\n")


def test_rows_of_one_callsign_sort_by_frequency_as_a_number() -> None:
    rows = [mcp_row(callsign="XX0MB", freq_tx=f, fm="True") for f in ("145.0", "1296.1", "50.8")]
    lines = snapshot.normalize(mcp_csv(rows)).splitlines()[1:]
    freq_tx = snapshot.COLUMNS.index("freq_tx")
    assert [line.split(",")[freq_tx] for line in lines] == ["50.8", "145.0", "1296.1"]


def test_snapshot_columns_are_the_source_columns_of_the_pinned_mcp() -> None:
    from memory_channels_processor.processor import get_data_source_col_names

    assert tuple(get_data_source_col_names()) == snapshot.COLUMNS


@pytest.mark.parametrize("cell", [{"fm": "yes"}, {"freq_rx": "fast"}, {"dmr": "True", "dmr_cc": "1.5"}])
def test_an_unconvertible_cell_is_refused_with_its_callsign(cell: dict[str, str]) -> None:
    row = mcp_row(callsign="XX0BAD", freq_tx="145.0", freq_rx="145.6", fm="True") | cell
    with pytest.raises(snapshot.SnapshotError, match="XX0BAD"):
        next(snapshot.channels_from_rows([row]))


def test_an_unsortable_frequency_is_refused_with_its_callsign() -> None:
    with pytest.raises(snapshot.SnapshotError, match=r"XX0BAD.*freq_tx"):
        snapshot.normalize(mcp_csv([FM_REPEATER, mcp_row(callsign="XX0BAD", freq_tx="?")]))
