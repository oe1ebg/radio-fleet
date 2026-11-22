"""Yaesu FT5D renderer (R7): a radio's selection as the ADMS-14 import CSV, written by MCP's `yaesu-ft5d` output.

The selection goes to MCP as rows in MCP's CSV columns, read through MCP's csv source:
- MCP drops rows with the same frequencies and callsign and moves simplex rows last, so `callsign` holds
  the memory number (`M001`, which ADMS shows in the comment) and `scan_group` the position, which
  `--sort scan_group` restores; `--name-format name` names the memory after `name`, the channel's name;
- each zone of the selection is one bank. `comment` lists a row's banks as `;b01;b03;` and
  `--yaesu-bank N:comment~=;bNN;` turns bank N on for the rows that list it;
- MCP's template writes the name unquoted, carries CTCSS but no DCS, and only the CTCSS of TX; `unfit`
  names the channels it cannot write, which the selection drops.

`MEMORIES` and `BANKS` are the rows and bank columns of the import file; the profile's channel and zone
limits must fit in them.
"""

from __future__ import annotations

import csv
import io

from radio_fleet.dmrconf import CheckError
from radio_fleet.mcp import Converter
from radio_fleet.model import Channel, Ctcss, Mode
from radio_fleet.selection import Selection
from radio_fleet.snapshot import COLUMNS

MEMORIES = 900
BANKS = 24
# Location, 51 memory fields, comment and the trailing 0 of MCP's template.
WIDTH = 54
_FIRST_BANK = 28


class RenderError(ValueError):
    pass


def unfit(channel: Channel) -> str | None:
    """Why MCP's yaesu-ft5d output cannot carry the channel, or None."""
    if channel.mode not in (Mode.FM, Mode.C4FM):
        return f"the FT5D carries FM and C4FM, not {channel.mode}"
    if set(channel.name) & {",", '"'}:
        return 'MCP writes the FT5D name unquoted, so it cannot hold , or "'
    tx, rx = channel.tone_tx, channel.tone_rx
    if not (tx is None or isinstance(tx, Ctcss)) or not (rx is None or rx == tx):
        return "MCP's yaesu-ft5d output carries one CTCSS tone, no DCS"
    return None


def render(selection: Selection, mcp: Converter) -> str:
    capability = selection.radio.capability
    if capability.channels > MEMORIES or capability.zones > BANKS:
        raise RenderError(
            f"the profile's capability has {capability.channels} channels and {capability.zones} zones, "
            f"the FT5D import has {MEMORIES} memories and {BANKS} banks"
        )
    rows = [_row(position, channel, selection) for position, channel in enumerate(selection.channels, 1)]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    options = ["--name-format", "name", "--sort", "scan_group"]
    if selection.zones:
        banks = range(1, len(selection.zones) + 1)
        options += ["--yaesu-bank", *(f"{bank}:comment~=;b{bank:02d};" for bank in banks)]
    return mcp.convert(out.getvalue(), "yaesu-ft5d", options)


def check(text: str, selection: Selection) -> None:
    """Raise CheckError unless the file has the FT5D's memories and one filled row per channel, in order,
    with the banks of the channel's zones."""
    lines = text.splitlines()
    if len(lines) != MEMORIES:
        raise CheckError(f"CSV check failed: {len(lines)} rows, the FT5D import has {MEMORIES}")
    filled: list[list[str]] = []
    for number, line in enumerate(lines, 1):
        fields = line.split(",")
        if len(fields) != WIDTH or fields[0] != str(number):
            raise CheckError(f"CSV check failed: row {number} is not memory {number} with {WIDTH} columns")
        if fields[2]:
            filled.append(fields)
    if len(filled) != len(selection.channels):
        raise CheckError(f"CSV check failed: {len(filled)} memories for {len(selection.channels)} channels")
    for fields, channel in zip(filled, selection.channels, strict=True):
        banks = _banks(channel, selection)
        expected = ["ON" if bank in banks else "OFF" for bank in range(1, BANKS + 1)]
        if fields[_FIRST_BANK : _FIRST_BANK + BANKS] != expected:
            raise CheckError(f"CSV check failed: memory {fields[0]} is not in banks {banks or 'none'}")


def _banks(channel: Channel, selection: Selection) -> list[int]:
    return [bank for bank, zone in enumerate(selection.zones, 1) if channel in zone.channels]


def _row(position: int, channel: Channel, selection: Selection) -> dict[str, str]:
    reason = unfit(channel)
    if reason is not None:
        raise RenderError(f"channel {channel.name}: {reason}")
    tx, rx = channel.tone_tx, channel.tone_rx
    band = selection.radio.capability.band_of(channel)
    banks = _banks(channel, selection)
    ctcss = f"{tx.hz:g}" if isinstance(tx, Ctcss) else ""
    return {
        **dict.fromkeys(COLUMNS, ""),
        **dict.fromkeys(("dmr", "dstar", "skip", "loc_exact"), "False"),
        "callsign": f"M{position:03d}",
        "name": channel.name,
        "band": band.name if band is not None else "",
        "freq_tx": _mhz(channel.tx_hz),
        "freq_rx": _mhz(channel.rx_hz),
        "ctcss_tx": ctcss,
        "ctcss_rx": ctcss if rx is not None else "",
        "fm": str(channel.mode is Mode.FM),
        "c4fm": str(channel.mode is Mode.C4FM),
        "comment": ";" + "".join(f"b{bank:02d};" for bank in banks),
        "scan_group": str(position),
    }


def _mhz(hz: int) -> str:
    return f"{hz / 1_000_000:.6f}"
