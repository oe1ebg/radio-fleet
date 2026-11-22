"""CHIRP renderer (R6): a radio's selection as CHIRP's generic CSV, for CHIRP's manual import.

The selection already respects the radio's memory count and name length (R4); `check` proves the file
does (R10). Locations start at 1, the first memory of the Baofeng and Retevis radios.
"""

from __future__ import annotations

import csv
import io
import re

from radio_fleet.dmrconf import CheckError
from radio_fleet.model import Channel, Ctcss, Dcs, Mode, Tone
from radio_fleet.selection import Selection

COLUMNS = (
    "Location",
    "Name",
    "Frequency",
    "Duplex",
    "Offset",
    "Tone",
    "rToneFreq",
    "cToneFreq",
    "DtcsCode",
    "DtcsPolarity",
    "RxDtcsCode",
    "CrossMode",
    "Mode",
    "TStep",
    "Skip",
    "Power",
    "Comment",
    "URCALL",
    "RPT1CALL",
    "RPT2CALL",
    "DVCODE",
)
# CHIRP's order when it picks the tuning step a frequency needs, in Hz.
_STEPS = (5_000, 6_250, 12_500, 2_500)
_POWER = re.compile(r"[0-9]+(\.[0-9]+)?W")
_NO_CTCSS = "88.5"
_NO_DCS = "023"


class RenderError(ValueError):
    pass


def render(selection: Selection) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    writer.writerows(_row(location, channel) for location, channel in enumerate(selection.channels, 1))
    return out.getvalue()


def check(text: str, selection: Selection) -> None:
    """Raise CheckError unless the file has CHIRP's columns and one row per channel within the radio's limits."""
    capability = selection.radio.capability
    rows = list(csv.reader(io.StringIO(text, newline="")))
    if not rows or tuple(rows[0]) != COLUMNS:
        raise CheckError(f"CSV check failed: the header is not CHIRP's columns {','.join(COLUMNS)}")
    memories = rows[1:]
    if len(memories) != len(selection.channels):
        raise CheckError(f"CSV check failed: {len(memories)} rows for {len(selection.channels)} channels")
    if len(memories) > capability.channels:
        raise CheckError(f"CSV check failed: {len(memories)} rows, the radio has {capability.channels} memories")
    for number, row in enumerate(memories, 2):
        if len(row) != len(COLUMNS):
            raise CheckError(f"CSV check failed: line {number} has {len(row)} columns, not {len(COLUMNS)}")
        if len(row[1]) > capability.name_length:
            limit = capability.name_length
            raise CheckError(f"CSV check failed: line {number}: name {row[1]!r} exceeds {limit} characters")


def _row(location: int, channel: Channel) -> list[str]:
    if channel.mode is not Mode.FM:
        raise RenderError(f"channel {channel.name}: CHIRP's radios here carry FM, not {channel.mode}")
    power = channel.power or ""
    if power and not _POWER.fullmatch(power):
        raise RenderError(f"channel {channel.name}: power {power!r} is not CHIRP's watts, such as 5.0W")
    shift = channel.tx_hz - channel.rx_hz
    tone, r_tone, c_tone, dtcs, rx_dtcs, cross = _tones(channel.tone_tx, channel.tone_rx)
    narrow = channel.bandwidth_hz is not None and channel.bandwidth_hz <= 12_500
    return [
        str(location),
        channel.name,
        _mhz(channel.rx_hz),
        "" if shift == 0 else "+" if shift > 0 else "-",
        _mhz(abs(shift)),
        tone,
        r_tone,
        c_tone,
        dtcs,
        "NN",
        rx_dtcs,
        cross,
        "NFM" if narrow else "FM",
        _step(channel),
        "",
        power,
        channel.source,
        "",
        "",
        "",
        "",
    ]


def _tones(tx: Tone | None, rx: Tone | None) -> tuple[str, str, str, str, str, str]:
    """CHIRP's Tone, rToneFreq, cToneFreq, DtcsCode, RxDtcsCode and CrossMode for a TX and an RX tone."""
    r_tone = f"{tx.hz:.1f}" if isinstance(tx, Ctcss) else _NO_CTCSS
    c_tone = f"{rx.hz:.1f}" if isinstance(rx, Ctcss) else r_tone
    dtcs = f"{tx.code:03d}" if isinstance(tx, Dcs) else _NO_DCS
    rx_dtcs = f"{rx.code:03d}" if isinstance(rx, Dcs) else dtcs
    if tx is None and rx is None:
        return "", r_tone, c_tone, dtcs, rx_dtcs, "Tone->Tone"
    if isinstance(tx, Ctcss) and rx is None:
        return "Tone", r_tone, c_tone, dtcs, rx_dtcs, "Tone->Tone"
    if isinstance(tx, Ctcss) and tx == rx:
        return "TSQL", r_tone, c_tone, dtcs, rx_dtcs, "Tone->Tone"
    if isinstance(tx, Dcs) and tx == rx:
        return "DTCS", r_tone, c_tone, dtcs, rx_dtcs, "Tone->Tone"
    return "Cross", r_tone, c_tone, dtcs, rx_dtcs, f"{_kind(tx)}->{_kind(rx)}"


def _kind(tone: Tone | None) -> str:
    return "" if tone is None else "Tone" if isinstance(tone, Ctcss) else "DTCS"


def _step(channel: Channel) -> str:
    step = next((step for step in _STEPS if channel.rx_hz % step == 0), None)
    if step is None:
        raise RenderError(f"channel {channel.name}: RX {_mhz(channel.rx_hz)} MHz is on no CHIRP tuning step")
    return f"{step / 1000:.2f}"


def _mhz(hz: int) -> str:
    return f"{hz / 1_000_000:.6f}"
