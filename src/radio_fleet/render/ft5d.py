"""Yaesu FT5D renderer (R7): a radio's selection as the ADMS-14 import CSV, written by MCP's `yaesu-ft5d` output.

The selection goes to MCP as MCP CSV, one row per memory. MCP keeps one row per callsign and frequency pair,
so an FM and a C4FM channel of the same name and frequencies become one AMS memory, and any other pair is
refused. The memory number rides in MCP's `scan_group` column: MCP sorts by it, and the profile's zones
become the banks 1 to 24 as filters on it. ADMS banks have no names.

MCP's output has gaps that are refused here rather than written wrong: it sets no DCS tone mode, and its
tone squelch uses the TX tone for RX as well.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence

from radio_fleet.fleet import Capability
from radio_fleet.mcp import Exporter
from radio_fleet.model import Channel, Ctcss, Dcs, Mode
from radio_fleet.render.csvcheck import check_memories, check_rows, rows
from radio_fleet.selection import Selection
from radio_fleet.snapshot import COLUMNS

OUTPUT_FORMAT = "yaesu-ft5d"
BANKS = 24
WIDTH = 54
_RX, _NAME = 2, 10
_FLAGS = {Mode.FM: "fm", Mode.C4FM: "c4fm"}


class RenderError(ValueError):
    pass


def render(selection: Selection, mcp: Exporter) -> str:
    memories, numbers = _memories(selection)
    options = ["--sort", "scan_group", *_banks(selection, numbers)]
    text = mcp.export(_csv(memories), OUTPUT_FORMAT, options)
    written = sum(1 for row in rows(text) if len(row) > _RX and row[_RX])
    if written != len(memories):
        raise RenderError(f"memory-channels-processor wrote {written} memories for {len(memories)}")
    return text


def check(text: str, capability: Capability) -> None:
    table = rows(text)
    check_rows(table, WIDTH, location=0, first=1)
    check_memories([row[_NAME] for row in table if row[_RX]], capability)


def _memories(selection: Selection) -> tuple[list[dict[str, str]], dict[Channel, int]]:
    memories: dict[tuple[str, int, int], dict[str, str]] = {}
    numbers: dict[Channel, int] = {}
    for channel in selection.channels:
        if channel in numbers:
            continue
        flag = _FLAGS.get(channel.mode)
        if flag is None:
            raise RenderError(f"channel {channel.name}: the FT5D renderer carries FM and C4FM, not {channel.mode}")
        key = (channel.name, channel.rx_hz, channel.tx_hz)
        if key not in memories:
            memories[key] = _row(len(memories) + 1, channel, selection.radio.capability)
        memory = memories[key]
        if memory[flag] == "True":
            raise RenderError(f"channel {channel.name}: another {channel.mode} channel has its name and frequencies")
        memory[flag] = "True"
        if channel.mode is Mode.FM:
            memory["ctcss_tx"], memory["ctcss_rx"] = _ctcss(channel)
        numbers[channel] = int(memory["scan_group"])
    return list(memories.values()), numbers


def _row(number: int, channel: Channel, capability: Capability) -> dict[str, str]:
    row = dict.fromkeys(COLUMNS, "")
    row.update(dict.fromkeys(("fm", "c4fm", "dmr", "dstar", "loc_exact", "skip"), "False"))
    band = capability.band_of(channel)
    row.update(
        callsign=channel.name,
        band=band.name if band is not None else "",
        freq_tx=_mhz(channel.tx_hz),
        freq_rx=_mhz(channel.rx_hz),
        scan_group=str(number),
        source_id=channel.source,
    )
    return row


def _ctcss(channel: Channel) -> tuple[str, str]:
    tx, rx = channel.tone_tx, channel.tone_rx
    if isinstance(tx, Dcs) or isinstance(rx, Dcs):
        raise RenderError(f"channel {channel.name}: memory-channels-processor's FT5D output carries no DCS")
    if rx is not None and rx != tx:
        raise RenderError(
            f"channel {channel.name}: memory-channels-processor's FT5D output takes an RX tone "
            "only equal to the TX tone"
        )
    return _hz(tx), _hz(rx)


def _hz(tone: Ctcss | None) -> str:
    return "" if tone is None else f"{tone.hz:g}"


def _banks(selection: Selection, numbers: dict[Channel, int]) -> Sequence[str]:
    if len(selection.zones) > BANKS:
        raise RenderError(f"{len(selection.zones)} zones, the FT5D has {BANKS} banks")
    filters = [
        f"{bank}:scan_group=={number}"
        for bank, zone in enumerate(selection.zones, 1)
        for number in dict.fromkeys(numbers[channel] for channel in zone.channels)
    ]
    return ["--yaesu-bank", *filters] if filters else []


def _csv(memories: Sequence[dict[str, str]]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(memories)
    return out.getvalue()


def _mhz(hz: int) -> str:
    return f"{hz / 1_000_000:.6f}"
