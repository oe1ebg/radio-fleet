"""CHIRP renderer (R6): a radio's selection as CHIRP's generic CSV, which the owner imports in CHIRP.

Memories are numbered from 1 in the order of the selection. CHIRP reads the power in watts and the tone
settings as its memory fields: `Tone` is the tone mode, `rToneFreq` the CTCSS tone sent with `Tone`,
`cToneFreq` the CTCSS tone of `TSQL`, and `Cross` combines a TX and an RX tone as `CrossMode` names.
"""

from __future__ import annotations

import csv
import io
import re

from radio_fleet.fleet import Capability
from radio_fleet.model import Channel, Ctcss, Dcs, Mode, Tone
from radio_fleet.render.csvcheck import CsvCheckError, check_memories, check_rows, mhz, rows
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
# The CHIRP tuning steps a frequency and its offset are tried on, coarsest first.
STEPS_HZ = (12_500, 6_250, 5_000, 2_500)
_WATTS = re.compile(r"(\d+(?:\.\d+)?)\s*W")
_DEFAULT_CTCSS = Ctcss(88.5)
_DEFAULT_DCS = Dcs(23)


class RenderError(ValueError):
    pass


def render(selection: Selection) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    for number, channel in enumerate(dict.fromkeys(selection.channels), 1):
        writer.writerow(_row(number, channel))
    return out.getvalue()


def check(text: str, capability: Capability) -> None:
    table = rows(text)
    if not table or tuple(table[0]) != COLUMNS:
        raise CsvCheckError(f"the header is not CHIRP's: {','.join(COLUMNS)}")
    check_rows(table[1:], len(COLUMNS))
    check_memories([row[1] for row in table[1:]], capability)


def _row(number: int, channel: Channel) -> list[str]:
    if channel.mode is not Mode.FM:
        raise RenderError(f"channel {channel.name}: the CHIRP renderer carries FM, not {channel.mode}")
    offset = channel.tx_hz - channel.rx_hz
    duplex = "" if offset == 0 else "+" if offset > 0 else "-"
    narrow = channel.bandwidth_hz is not None and channel.bandwidth_hz <= 12_500
    return [
        str(number),
        channel.name,
        mhz(channel.rx_hz),
        duplex,
        mhz(abs(offset)),
        *_tones(channel.tone_tx, channel.tone_rx),
        "NFM" if narrow else "FM",
        _step(channel, abs(offset)),
        "",
        _power(channel),
        channel.source,
        "",
        "",
        "",
        "",
    ]


def _tones(tx: Tone | None, rx: Tone | None) -> list[str]:
    """The columns Tone, rToneFreq, cToneFreq, DtcsCode, DtcsPolarity, RxDtcsCode and CrossMode."""
    rtone = ctone = _DEFAULT_CTCSS
    dtcs = rx_dtcs = _DEFAULT_DCS
    cross = "Tone->Tone"
    if tx is None and rx is None:
        mode = ""
    elif isinstance(tx, Ctcss) and rx is None:
        mode, rtone = "Tone", tx
    elif isinstance(tx, Ctcss) and tx == rx:
        mode, rtone, ctone = "TSQL", tx, tx
    elif isinstance(tx, Dcs) and tx == rx:
        mode, dtcs, rx_dtcs = "DTCS", tx, tx
    else:
        mode, cross = "Cross", f"{_kind(tx)}->{_kind(rx)}"
        if isinstance(tx, Ctcss):
            rtone = tx
        elif isinstance(tx, Dcs):
            dtcs = tx
        if isinstance(rx, Ctcss):
            ctone = rx
        elif isinstance(rx, Dcs):
            rx_dtcs = rx
    return [mode, f"{rtone.hz:.1f}", f"{ctone.hz:.1f}", f"{dtcs.code:03d}", "NN", f"{rx_dtcs.code:03d}", cross]


def _kind(tone: Tone | None) -> str:
    return "" if tone is None else "Tone" if isinstance(tone, Ctcss) else "DTCS"


def _step(channel: Channel, offset: int) -> str:
    for step in STEPS_HZ:
        if channel.rx_hz % step == 0 and offset % step == 0:
            return f"{step / 1000:.2f}"
    raise RenderError(f"channel {channel.name}: RX {mhz(channel.rx_hz)} MHz is on no CHIRP tuning step")


def _power(channel: Channel) -> str:
    match = _WATTS.fullmatch(channel.power or "")
    if match is None:
        raise RenderError(f"channel {channel.name}: CHIRP needs the power in watts, such as 5W, not {channel.power!r}")
    return f"{float(match.group(1)):.1f}W"
