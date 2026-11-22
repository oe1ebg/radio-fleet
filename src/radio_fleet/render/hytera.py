"""Hytera renderer (R9): edits the lossless YAML export of a radio's base `.rcdx` (the Hytera tool's).

The renderer edits the digital and analog channels, contacts, RX group lists and zones and leaves every
other value of the export as it is. Each build starts from a fresh export of the base, so nothing of an
earlier build is in the document. A record is found by its name in its table: a base record with the name
of a generated one is edited in place and keeps its other settings; any other name is added as a new
record (an entry without `index`, which the import builds from the factory image's defaults). A talkgroup
reuses a base group call contact with its number. The import refuses what the file cannot hold, such as a
name longer than 16 characters or a table beyond its capacity, and names the path.
"""

from __future__ import annotations

from typing import Any

import yaml

from radio_fleet.model import Channel, Ctcss, Mode, Tone
from radio_fleet.selection import Selection
from radio_fleet.sources import Sources

POWERS = ("High", "Middle", "Low")
_TABLES = ("digital_channels", "analog_channels", "contacts", "rx_groups", "zones")
_KINDS = {Mode.DMR: "digital", Mode.FM: "analog"}

Entry = dict[str, Any]


class RenderError(ValueError):
    pass


def render(selection: Selection, sources: Sources, base: str) -> str:
    """Return the exported base with the channels, contacts, RX group lists and zones of this selection."""
    try:
        document = yaml.safe_load(base)
    except yaml.YAMLError as error:
        raise RenderError(f"the export is not valid YAML: {error}") from None
    tables = document.get("tables") if isinstance(document, dict) else None
    _Editor(sources, {key: _entries(tables, key) for key in _TABLES}).edit(selection)
    return yaml.safe_dump(document, sort_keys=False, allow_unicode=True, default_flow_style=False)


def _entries(tables: object, key: str) -> list[Entry]:
    table = tables.get(key) if isinstance(tables, dict) else None
    entries = table.get("entries") if isinstance(table, dict) else None
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        raise RenderError(f"the export is not a Hytera codeplug: expected the tables {', '.join(_TABLES)}")
    return entries


class _Editor:
    def __init__(self, sources: Sources, tables: dict[str, list[Entry]]) -> None:
        self._sources = sources
        self._tables = tables

    def edit(self, selection: Selection) -> None:
        kinds: dict[Channel, str] = {}
        named: dict[tuple[str, str], Channel] = {}
        for channel in selection.channels:
            if channel in kinds:
                continue
            kind = _kind(channel)
            if named.setdefault((kind, channel.name), channel) != channel:
                raise RenderError(f"two {kind} channels are named {channel.name!r}")
            kinds[channel] = kind
            self._channel(kind, channel)
        for zone in selection.zones:
            members = dict.fromkeys((kinds[channel], channel.name) for channel in zone.channels)
            self._zone(zone.name, list(members))

    def _entry(self, table: str, name: str) -> Entry:
        entries = self._tables[table]
        found = next((entry for entry in entries if entry.get("name") == name), None)
        if found is None:
            found = {"name": name}
            entries.append(found)
        return found

    def _channel(self, kind: str, channel: Channel) -> None:
        entry = self._entry(f"{kind}_channels", channel.name)
        for key, hz in (("rx", channel.rx_hz), ("tx", channel.tx_hz)):
            entry[f"{key}_hz"] = hz
            entry.pop(f"{key}_mhz", None)
        settings = entry.setdefault("settings", {})
        if channel.power is not None:
            if channel.power not in POWERS:
                raise RenderError(f"channel {channel.name}: power {channel.power!r} is not one of {', '.join(POWERS)}")
            settings["power_level"] = channel.power
        if kind == "analog":
            narrow = channel.bandwidth_hz is not None and channel.bandwidth_hz <= 12_500
            settings["channel_spacing"] = "12.5" if narrow else "25"
            _set_tone(settings, "tx_tone", channel.tone_tx)
            _set_tone(settings, "rx_tone", channel.tone_rx)
            settings["rx_squelch_mode"] = "Carrier" if channel.tone_rx is None else "CTCSS/CDCSS"
            return
        if channel.color_code is not None:
            settings["color_code"] = channel.color_code
        if channel.time_slot is not None:
            settings["slot_operation"] = f"Slot {channel.time_slot}"
        references = entry.setdefault("references", {})
        contact = self._contact(channel.tx_talkgroup) if channel.tx_talkgroup is not None else None
        group = self._rx_group(channel.rx_group_list) if channel.rx_group_list is not None else None
        _refer(references, "tx_contact", contact)
        _refer(references, "rx_group_list", group)

    def _contact(self, talkgroup: str) -> str:
        number = self._sources.talkgroups[talkgroup]
        contacts = self._tables["contacts"]
        for entry in contacts:
            if entry.get("call_type") == "group" and entry.get("dmr_id") == number:
                return str(entry["name"])
        if any(entry.get("name") == talkgroup for entry in contacts):
            raise RenderError(f"contact {talkgroup!r} of the base is not the group call {number}")
        contacts.append({"name": talkgroup, "call_type": "group", "dmr_id": number})
        return talkgroup

    def _rx_group(self, name: str) -> str:
        contacts = [self._contact(talkgroup) for talkgroup in self._sources.rx_group_lists[name]]
        entry = self._entry("rx_groups", name)
        kept = {member.get("name"): member for member in entry.get("members") or []}
        entry["members"] = [kept.get(contact, {"name": contact}) for contact in dict.fromkeys(contacts)]
        return name

    def _zone(self, name: str, members: list[tuple[str, str]]) -> None:
        entry = self._entry("zones", name)
        kept = {(member.get("kind"), member.get("name")): member for member in entry.get("members") or []}
        entry["members"] = [kept.get(member, {"kind": member[0], "name": member[1]}) for member in members]


def _kind(channel: Channel) -> str:
    kind = _KINDS.get(channel.mode)
    if kind is None:
        raise RenderError(f"channel {channel.name}: Hytera carries FM and DMR, not {channel.mode}")
    return kind


def _refer(references: Entry, key: str, name: str | None) -> None:
    """Point a reference at a record by name; a base reference keeps its raw index, which the import reads
    as stale once the name changed."""
    reference = references.get(key)
    if not isinstance(reference, dict):
        references[key] = {"name": name}
    elif reference.get("name") != name:
        references[key] = {**reference, "name": name}


def _set_tone(settings: Entry, key: str, tone: Tone | None) -> None:
    if tone is None:
        current = settings.get(key)
        if not (isinstance(current, dict) and current.get("mode") == "none"):
            settings[key] = {"mode": "none", "default_ctcss_hz": None}
    elif isinstance(tone, Ctcss):
        settings[key] = {"mode": "CTCSS", "hz": tone.hz}
    else:
        settings[key] = {"mode": "CDCSS", "code": f"{tone.code:03d}"}
