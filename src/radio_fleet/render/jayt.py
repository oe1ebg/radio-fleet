"""jayt renderer (R8): writes a radio's selection into the channel part of its jayt radio document.

The document is the export of the radio's base file; every key other than `channels` stays as it is, and
`jayt import --template BASE` builds the radio file from it. The channel list is the whole memory: a slot
the document does not list is blank in the file. FT-3185 documents only so far.
"""

from __future__ import annotations

from typing import Any

import yaml

from radio_fleet.fleet import Radio
from radio_fleet.model import Channel, Ctcss, Dcs, Mode, Tone
from radio_fleet.selection import Selection

RADIO = "FT-3185"


class RenderError(ValueError):
    pass


def render(selection: Selection, document: str) -> str:
    """Return the document with the selection as its channels."""
    try:
        parsed = yaml.safe_load(document)
    except yaml.YAMLError as error:
        raise RenderError(f"the document is not valid YAML: {error}") from None
    if not isinstance(parsed, dict) or not isinstance(parsed.get("channels"), list):
        raise RenderError("not a jayt radio document: expected a mapping with a channel list")
    if parsed.get("radio") != RADIO:
        raise RenderError(f"the jayt renderer writes {RADIO} channels, not those of radio {parsed.get('radio')!r}")
    parsed["channels"] = [_channel(selection.radio, channel, slot) for slot, channel in enumerate(selection.channels)]
    return yaml.safe_dump(parsed, sort_keys=False, allow_unicode=True, default_flow_style=False)


def _channel(radio: Radio, channel: Channel, slot: int) -> dict[str, Any]:
    if channel.mode is not Mode.FM:
        raise RenderError(f"channel {channel.name}: the {RADIO} carries FM, not {channel.mode}")
    narrow = channel.bandwidth_hz is not None and channel.bandwidth_hz <= 12_500
    shift = channel.tx_hz - channel.rx_hz
    fields: dict[str, Any] = {
        "slot": slot,
        "name": channel.name,
        "freq_hz": channel.rx_hz,
        "tx_hz": channel.tx_hz,
        "rpt": "SIMP" if shift == 0 else "+" if shift > 0 else "-",
        "offset_hz": abs(shift),
        "mode": "FM-N" if narrow else "FM",
        **_tone(channel),
    }
    power = radio.power_value(channel.power)
    if power is not None:
        fields["tx_power"] = power.upper()
    return fields


def _tone(channel: Channel) -> dict[str, str]:
    """The FT-3185 sends a CTCSS tone, or squelches on the tone it sends, or uses one DCS code both ways."""
    tx, rx = channel.tone_tx, channel.tone_rx
    if tx is None and rx is None:
        return {"tone": "OFF"}
    if isinstance(tx, Ctcss) and rx is None:
        return {"tone": "ENC", "ctcss_hz": f"{tx.hz:.1f}"}
    if isinstance(tx, Ctcss) and rx == tx:
        return {"tone": "TSQ", "ctcss_hz": f"{tx.hz:.1f}", "ctcss_dec_hz": f"{tx.hz:.1f}"}
    if isinstance(tx, Dcs) and rx in (None, tx):
        return {"tone": "DCS", "dcs": f"{tx.code:03d}", "dcs_dec": f"{tx.code:03d}"}
    raise RenderError(f"channel {channel.name}: the {RADIO} cannot carry tone TX {_text(tx)}, tone RX {_text(rx)}")


def _text(tone: Tone | None) -> str:
    if tone is None:
        return "none"
    return f"CTCSS {tone.hz:g}" if isinstance(tone, Ctcss) else f"DCS {tone.code:03d}"
