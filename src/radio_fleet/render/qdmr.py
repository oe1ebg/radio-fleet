"""qdmr renderer (R5): merges a radio's selection into its base qdmr YAML codeplug.

Every generated object has an id that starts with `gen_`; a render first removes every such object of the base,
so rendering over its own output replaces exactly the generated objects and keeps every hand-made one.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from radio_fleet.model import Channel, Ctcss, Mode, Tone
from radio_fleet.selection import Selection
from radio_fleet.sources import Sources

PREFIX = "gen_"
GENERATED_LISTS = ("contacts", "groupLists", "channels", "zones", "scanLists")
POWERS = ("Max", "High", "Mid", "Low", "Min")

# dmrconf's key (`dmrconf --list-radios`) for each radio model it checks.
DMRCONF_RADIOS = {
    "AnyTone D878UV II Plus": "d878uv2",
    "AnyTone D168UV": "d168uv",
}

_Object = dict[str, Any]


class RenderError(ValueError):
    pass


class _Loader(yaml.SafeLoader):
    """YAML 1.2 booleans only: qdmr writes enum values such as `Off` that YAML 1.1 would read as false."""


_Loader.yaml_implicit_resolvers = {
    first: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:bool"]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_Loader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF")
)


def dmrconf_radio(model: str) -> str:
    try:
        return DMRCONF_RADIOS[model]
    except KeyError:
        raise RenderError(f"dmrconf checks no radio {model!r}; it checks {', '.join(DMRCONF_RADIOS)}") from None


def render(selection: Selection, sources: Sources, base: Path) -> str:
    codeplug = _load(base)
    lists = {key: [entry for entry in _list(codeplug, key, base) if not _generated(entry)] for key in GENERATED_LISTS}
    codeplug.update(lists)
    contacts = _Contacts(lists["contacts"], sources.talkgroups)
    group_lists: dict[str, str] = {}
    channel_ids: dict[int, str] = {}
    for number, channel in enumerate(selection.channels, 1):
        if channel.rx_group_list is not None and channel.rx_group_list not in group_lists:
            group_id = f"{PREFIX}grp{len(group_lists) + 1}"
            group_lists[channel.rx_group_list] = group_id
            members = [contacts.id(name) for name in sources.rx_group_lists[channel.rx_group_list]]
            lists["groupLists"].append({"id": group_id, "name": channel.rx_group_list, "contacts": members})
        channel_id = f"{PREFIX}ch{number}"
        # Zones hold the selection's own channel objects; equal channels may appear twice.
        channel_ids[id(channel)] = channel_id
        lists["channels"].append(_channel(channel_id, channel, contacts, group_lists))
    for number, zone in enumerate(selection.zones, 1):
        members = [channel_ids[id(channel)] for channel in zone.channels]
        lists["zones"].append({"id": f"{PREFIX}zone{number}", "name": zone.name, "A": members, "B": []})
    return yaml.safe_dump(codeplug, sort_keys=False, allow_unicode=True, default_flow_style=False, width=1000)


def _load(base: Path) -> _Object:
    with base.open(encoding="utf-8") as f:
        try:
            codeplug = yaml.load(f, Loader=_Loader)
        except yaml.YAMLError as error:
            raise RenderError(f"{base}: {error}") from error
    if not isinstance(codeplug, dict):
        raise RenderError(f"{base}: a qdmr codeplug is a mapping")
    return codeplug


def _list(codeplug: _Object, key: str, base: Path) -> list[Any]:
    value = codeplug.get(key) or []
    if not isinstance(value, list):
        raise RenderError(f"{base}: {key}: expected a list")
    return value


def _body(entry: object) -> Mapping[str, Any]:
    """The fields of a list entry; contacts and channels wrap them in their kind, such as `dmr:` or `fm:`."""
    if not isinstance(entry, dict):
        return {}
    if "id" not in entry and len(entry) == 1:
        (body,) = entry.values()
        return body if isinstance(body, dict) else {}
    return entry


def _generated(entry: object) -> bool:
    object_id = _body(entry).get("id")
    return isinstance(object_id, str) and object_id.startswith(PREFIX)


class _Contacts:
    """Group call contacts by talkgroup; one the base already has for a number is used, not added again."""

    def __init__(self, contacts: list[Any], talkgroups: Mapping[str, int]) -> None:
        self._contacts = contacts
        self._talkgroups = talkgroups
        self._ids: dict[int, str] = {}
        for entry in contacts:
            body = entry.get("dmr") if isinstance(entry, dict) else None
            if isinstance(body, dict) and body.get("type") == "GroupCall" and isinstance(body.get("number"), int):
                self._ids.setdefault(body["number"], str(body["id"]))

    def id(self, talkgroup: str) -> str:
        number = self._talkgroups[talkgroup]
        if number not in self._ids:
            self._ids[number] = f"{PREFIX}tg{number}"
            body = {"id": self._ids[number], "name": talkgroup, "ring": False, "type": "GroupCall", "number": number}
            self._contacts.append({"dmr": body})
        return self._ids[number]


def _channel(channel_id: str, channel: Channel, contacts: _Contacts, group_lists: Mapping[str, str]) -> _Object:
    body: _Object = {
        "id": channel_id,
        "name": channel.name,
        "rxFrequency": _mhz(channel.rx_hz),
        "txFrequency": _mhz(channel.tx_hz),
    }
    if channel.power is not None:
        if channel.power not in POWERS:
            raise RenderError(f"channel {channel.name!r}: power {channel.power!r} is not one of {', '.join(POWERS)}")
        body["power"] = channel.power
    if channel.mode is Mode.FM:
        # A channel without a bandwidth is narrow, as in memory-channels-processor's qdmr output.
        body["bandwidth"] = "Wide" if channel.bandwidth_hz is not None and channel.bandwidth_hz > 12_500 else "Narrow"
        if channel.tone_rx is not None:
            body["rxTone"] = _tone(channel.tone_rx)
        if channel.tone_tx is not None:
            body["txTone"] = _tone(channel.tone_tx)
        return {"fm": body}
    if channel.mode is Mode.DMR:
        if channel.color_code is None or channel.time_slot is None:
            raise RenderError(f"DMR channel {channel.name!r} needs a color code and a time slot")
        body["colorCode"] = channel.color_code
        body["timeSlot"] = f"TS{channel.time_slot}"
        if channel.rx_group_list is not None:
            body["groupList"] = group_lists[channel.rx_group_list]
        if channel.tx_talkgroup is not None:
            body["contact"] = contacts.id(channel.tx_talkgroup)
        return {"dmr": body}
    raise RenderError(f"channel {channel.name!r}: qdmr carries FM and DMR channels, not {channel.mode}")


def _mhz(hz: int) -> str:
    return f"{Decimal(hz) / 1_000_000:f} MHz"


def _tone(tone: Tone) -> _Object:
    return {"ctcss": f"{tone.hz:g} Hz"} if isinstance(tone, Ctcss) else {"dcs": tone.code}
