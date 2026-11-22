"""qdmr renderer (R5): merges a radio's selection into its base qdmr YAML codeplug.

Everything of the base stays: settings, radio IDs, positioning, roaming and every hand-made object.
Generated contacts, group lists, channels and zones carry ids that start with `gen_`, so a rebuild first
removes the generated objects of the base and then adds the new ones. Scan lists are not generated (a
profile has no scan list rules), but generated ones are removed like the others.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

import yaml

from radio_fleet.model import Channel, Ctcss, Mode, Tone
from radio_fleet.selection import Selection
from radio_fleet.sources import Sources

PREFIX = "gen_"
POWERS = ("Max", "High", "Mid", "Low", "Min")
_LISTS = ("contacts", "groupLists", "channels", "zones", "scanLists")


class RenderError(ValueError):
    pass


class _Loader(yaml.SafeLoader):
    """Reads plain scalars as qdmr's YAML 1.2 parser does, so a hand-made value keeps its meaning.

    PyYAML follows YAML 1.1, which reads `Off` and `No` as false, `023` as octal and `1:30` as 90.
    This loader reads null, true/false and decimal integers; every other plain scalar stays a string
    and is written back quoted, with its text unchanged.
    """


_Loader.yaml_implicit_resolvers = {}
for _tag, _pattern, _first in (
    ("tag:yaml.org,2002:null", r"^(?:~|null|Null|NULL|)$", ["~", "n", "N", ""]),
    ("tag:yaml.org,2002:bool", r"^(?:true|True|TRUE|false|False|FALSE)$", list("tTfF")),
    ("tag:yaml.org,2002:int", r"^[-+]?(?:0|[1-9][0-9]*)$", list("-+0123456789")),
):
    _Loader.add_implicit_resolver(_tag, re.compile(_pattern), _first)


def load(text: str) -> object:
    return yaml.load(text, Loader=_Loader)


def render(selection: Selection, sources: Sources, base: str) -> str:
    """Return the base codeplug with the generated objects of this selection."""
    try:
        document = load(base)
    except yaml.YAMLError as error:
        raise RenderError(f"the base is not valid YAML: {error}") from None
    if not isinstance(document, dict) or not all(isinstance(document.get(key) or [], list) for key in _LISTS):
        raise RenderError(f"the base is not a qdmr codeplug: expected a mapping with the lists {', '.join(_LISTS)}")
    kept = {key: [item for item in document.get(key) or [] if not _generated(item)] for key in _LISTS}
    generated = _Generator(selection, sources, kept["contacts"]).objects()
    for key in _LISTS:
        if key in document or generated[key]:
            document[key] = kept[key] + generated[key]
    return yaml.safe_dump(document, sort_keys=False, allow_unicode=True, default_flow_style=False)


def _generated(item: object) -> bool:
    """A list item is either an object or, for contacts, channels and positioning, `{type: object}`."""
    if isinstance(item, dict) and len(item) == 1:
        (inner,) = item.values()
        if isinstance(inner, dict):
            item = inner
    return isinstance(item, dict) and str(item.get("id", "")).startswith(PREFIX)


class _Generator:
    def __init__(self, selection: Selection, sources: Sources, contacts: Iterable[object]) -> None:
        self._selection = selection
        self._sources = sources
        self._existing = _group_call_ids(contacts)
        self._contacts: dict[int, dict[str, Any]] = {}
        self._group_lists: dict[str, dict[str, Any]] = {}

    def objects(self) -> dict[str, list[dict[str, Any]]]:
        channel_ids: dict[Channel, str] = {}
        channels: list[dict[str, Any]] = []
        for channel in self._selection.channels:
            if channel in channel_ids:
                continue
            channel_ids[channel] = f"{PREFIX}ch{len(channel_ids) + 1}"
            channels.append(self._channel(channel, channel_ids[channel]))
        zones = [
            {"id": f"{PREFIX}zone{i}", "name": zone.name, "A": [channel_ids[c] for c in zone.channels]}
            for i, zone in enumerate(self._selection.zones, 1)
        ]
        return {
            "contacts": [{"dmr": contact} for contact in self._contacts.values()],
            "groupLists": list(self._group_lists.values()),
            "channels": channels,
            "zones": zones,
            "scanLists": [],
        }

    def _channel(self, channel: Channel, channel_id: str) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "id": channel_id,
            "name": channel.name,
            "rxFrequency": _mhz(channel.rx_hz),
            "txFrequency": _mhz(channel.tx_hz),
        }
        if channel.power is not None:
            if channel.power not in POWERS:
                raise RenderError(f"channel {channel.name}: power {channel.power!r} is not one of {', '.join(POWERS)}")
            fields["power"] = channel.power
        if channel.mode is Mode.FM:
            narrow = channel.bandwidth_hz is not None and channel.bandwidth_hz <= 12_500
            fields["bandwidth"] = "Narrow" if narrow else "Wide"
            if channel.tone_rx is not None:
                fields["rxTone"] = _tone(channel.tone_rx)
            if channel.tone_tx is not None:
                fields["txTone"] = _tone(channel.tone_tx)
            return {"fm": fields}
        if channel.mode is Mode.DMR:
            if channel.color_code is not None:
                fields["colorCode"] = channel.color_code
            if channel.time_slot is not None:
                fields["timeSlot"] = f"TS{channel.time_slot}"
            if channel.rx_group_list is not None:
                fields["groupList"] = self._group_list(channel.rx_group_list)
            if channel.tx_talkgroup is not None:
                fields["contact"] = self._contact(channel.tx_talkgroup)
            return {"dmr": fields}
        raise RenderError(f"channel {channel.name}: qdmr carries FM and DMR, not {channel.mode}")

    def _contact(self, talkgroup: str) -> str:
        number = self._sources.talkgroups[talkgroup]
        if number in self._existing:
            return self._existing[number]
        contact = self._contacts.setdefault(
            number,
            {"id": f"{PREFIX}tg{number}", "name": talkgroup, "ring": False, "type": "GroupCall", "number": number},
        )
        return str(contact["id"])

    def _group_list(self, name: str) -> str:
        if name not in self._group_lists:
            contacts = [self._contact(talkgroup) for talkgroup in self._sources.rx_group_lists[name]]
            group_id = f"{PREFIX}grp{len(self._group_lists) + 1}"
            self._group_lists[name] = {"id": group_id, "name": name, "contacts": contacts}
        return str(self._group_lists[name]["id"])


def _group_call_ids(contacts: Iterable[object]) -> Mapping[int, str]:
    """The hand-made group call contacts by number; the first one of a number is reused."""
    ids: dict[int, str] = {}
    for item in contacts:
        contact = item.get("dmr") if isinstance(item, dict) else None
        if not isinstance(contact, dict) or contact.get("type") != "GroupCall":
            continue
        number, contact_id = str(contact.get("number", "")), contact.get("id")
        if number.isdigit() and isinstance(contact_id, str):
            ids.setdefault(int(number), contact_id)
    return ids


def _mhz(hz: int) -> str:
    whole, fraction = divmod(hz, 1_000_000)
    return f"{whole}.{fraction:06d}".rstrip("0").rstrip(".") + " MHz"


def _tone(tone: Tone) -> dict[str, str]:
    if isinstance(tone, Ctcss):
        return {"ctcss": f"{tone.hz:g} Hz"}
    return {"dcs": f"{tone.code:03d}N"}
