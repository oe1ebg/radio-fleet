"""Upstream snapshots: MCP CSV normalized to `snapshots/<source>.csv`, and read back into channels."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Iterator, Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path

from radio_fleet.model import Channel, Ctcss, Dcs, Mode, Position, Tone

# MCP 0.2.5's source columns, in MCP's order. The source_* columns carry the CC BY 4.0 attribution.
COLUMNS: tuple[str, ...] = (
    "callsign",
    "name",
    "band",
    "freq_tx",
    "freq_rx",
    "ctcss_tx",
    "ctcss_rx",
    "dtcs_tx",
    "dtcs_rx",
    "c4fm",
    "dmr",
    "dmr_id",
    "dmr_cc",
    "dstar",
    "dstar_rpt1",
    "dstar_rpt2",
    "fm",
    "bandwidth",
    "landmark",
    "state",
    "country",
    "country_code",
    "loc_exact",
    "lat",
    "long",
    "locator",
    "sea_level",
    "comment",
    "skip",
    "scan_group",
    "source_id",
    "source_name",
    "source_provider",
    "source_type",
    "source_license",
    "source_url",
)

_MODE_COLUMNS: tuple[tuple[str, Mode], ...] = (
    ("fm", Mode.FM),
    ("dmr", Mode.DMR),
    ("c4fm", Mode.C4FM),
    ("dstar", Mode.DSTAR),
)


class SnapshotError(ValueError):
    pass


def path_for(snapshots_dir: Path, source: str) -> Path:
    return snapshots_dir / f"{source}.csv"


def normalize(mcp_csv: str) -> str:
    """Return the snapshot text for MCP's CSV: fixed columns, rows sorted by callsign and frequency."""
    reader = csv.DictReader(io.StringIO(mcp_csv, newline=""))
    _require_columns(reader, "MCP output")
    rows = [tuple(row[c] for c in COLUMNS) for row in reader]
    rows.sort(key=_sort_key)
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    writer.writerows(rows)
    return out.getvalue()


def write(snapshots_dir: Path, source: str, mcp_csv: str) -> Path:
    """Write the snapshot only when every row converts, so a bad fetch leaves the old snapshot in place."""
    text = normalize(mcp_csv)
    list(channels_from_rows(csv.DictReader(io.StringIO(text, newline=""))))
    path = path_for(snapshots_dir, source)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def read(path: Path) -> list[Channel]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        _require_columns(reader, f"snapshot {path}")
        return list(channels_from_rows(reader))


def _require_columns(reader: csv.DictReader[str], what: str) -> None:
    missing = [c for c in COLUMNS if c not in (reader.fieldnames or ())]
    if missing:
        raise SnapshotError(f"{what} lacks columns: {', '.join(missing)}")


def channels_from_rows(rows: Iterable[Mapping[str, str]]) -> Iterator[Channel]:
    """One channel per mode the repeater carries; a row without a mode gives none.

    FM channels take DCS over CTCSS when a row lists both for one direction.
    """
    for row in rows:
        try:
            channels = [_channel(row, mode) for column, mode in _MODE_COLUMNS if _bool(row[column])]
        except (ArithmeticError, ValueError) as error:
            raise SnapshotError(f"row {row['callsign']!r}: {error}") from error
        yield from channels


def _channel(row: Mapping[str, str], mode: Mode) -> Channel:
    fm = mode is Mode.FM
    return Channel(
        name=row["callsign"],
        rx_hz=_hz(row["freq_rx"]),
        tx_hz=_hz(row["freq_tx"]),
        mode=mode,
        tone_tx=_tone(row["ctcss_tx"], row["dtcs_tx"]) if fm else None,
        tone_rx=_tone(row["ctcss_rx"], row["dtcs_rx"]) if fm else None,
        bandwidth_hz=round(Decimal(row["bandwidth"]) * 1000) if row["bandwidth"] else None,
        color_code=int(row["dmr_cc"]) if mode is Mode.DMR and row["dmr_cc"] else None,
        source=row["source_id"],
        position=_position(row["lat"], row["long"]),
        callsign=row["callsign"],
        site=row["name"] or None,
    )


def _hz(mhz: str) -> int:
    return round(Decimal(mhz) * 1_000_000)


def _position(lat: str, lon: str) -> Position | None:
    if not (lat and lon):
        return None
    position = Position(float(lat), float(lon))
    if not (-90 <= position.lat <= 90 and -180 <= position.lon <= 180):
        raise ValueError(f"lat/long out of range: {lat}, {lon}")
    return position


def _tone(ctcss: str, dcs: str) -> Tone | None:
    if dcs:
        return Dcs(int(Decimal(dcs)))
    if ctcss:
        return Ctcss(float(ctcss))
    return None


def _bool(value: str) -> bool:
    if value not in ("True", "False", ""):
        raise SnapshotError(f"not a boolean: {value!r}")
    return value == "True"


_CALLSIGN, _FREQ_TX = COLUMNS.index("callsign"), COLUMNS.index("freq_tx")


def _sort_key(row: tuple[str, ...]) -> tuple[str, Decimal, tuple[str, ...]]:
    freq_tx = row[_FREQ_TX]
    try:
        value = Decimal(freq_tx) if freq_tx else Decimal(0)
    except InvalidOperation:
        value = Decimal("NaN")
    if not value.is_finite():
        raise SnapshotError(f"row {row[_CALLSIGN]!r}: freq_tx is not a number: {freq_tx!r}")
    return row[_CALLSIGN], value, row
