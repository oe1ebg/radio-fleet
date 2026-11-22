"""The owner's sources (R3): own lists, talkgroups, overrides of upstream channels and DMR templates.

Frequencies are written in MHz and bandwidth in kHz, as in the upstream lists; everything else uses the
names of the channel model.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TypedDict

from radio_fleet import config
from radio_fleet.config import Node
from radio_fleet.model import Channel, Ctcss, Dcs, Mode, Tone

MHZ, KHZ = 1_000_000, 1_000

_OVERRIDE_KEYS = ("name", "rx", "tx", "tone_tx", "tone_rx", "bandwidth", "color_code", "power", "tags")
_CHANNEL_KEYS = (*_OVERRIDE_KEYS, "mode", "time_slot", "tx_talkgroup", "rx_group_list")


class ChannelFields(TypedDict, total=False):
    name: str
    rx_hz: int
    tx_hz: int
    mode: Mode
    tone_tx: Tone
    tone_rx: Tone
    bandwidth_hz: int
    color_code: int
    time_slot: int
    tx_talkgroup: str
    rx_group_list: str
    power: str
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OwnList:
    name: str
    channels: tuple[Channel, ...]


@dataclass(frozen=True, slots=True)
class Override:
    """Changes the upstream channels of one callsign, of every mode or of one."""

    callsign: str
    reason: str
    changes: ChannelFields
    mode: Mode | None = None

    def matches(self, channel: Channel) -> bool:
        return channel.name == self.callsign and self.mode in (None, channel.mode)


@dataclass(frozen=True, slots=True)
class AppliedOverride:
    channel: str
    mode: Mode
    override: Override


@dataclass(frozen=True, slots=True)
class TemplateChannel:
    """One channel a DMR template makes of a repeater; its name is appended to the callsign."""

    name: str
    time_slot: int
    tx_talkgroup: str
    rx_group_list: str | None


@dataclass(frozen=True, slots=True)
class Sources:
    directory: Path
    talkgroups: Mapping[str, int]
    rx_group_lists: Mapping[str, tuple[str, ...]]
    own_lists: Mapping[str, OwnList]
    overrides: tuple[Override, ...]
    dmr_templates: Mapping[str, tuple[TemplateChannel, ...]]


def load(sources_dir: Path) -> Sources:
    """Read `sources/`; a missing file reads as empty. A profile that names what is missing is refused
    by `Fleet.check_references`."""
    talkgroups, rx_group_lists = _talkgroups(_load(sources_dir / "talkgroups.yaml"))
    names = _Names(talkgroups, rx_group_lists)
    return Sources(
        directory=sources_dir,
        talkgroups=talkgroups,
        rx_group_lists=rx_group_lists,
        own_lists=_own_lists(sorted((sources_dir / "own").glob("*.yaml")), names),
        overrides=_overrides(_load(sources_dir / "overrides.yaml")),
        dmr_templates=_dmr_templates(_load(dmr_templates_path(sources_dir)), names),
    )


def own_list_path(sources_dir: Path, name: str) -> Path:
    """An own list is the file named after it, so a profile's `own_lists` entry names one file."""
    return sources_dir / "own" / f"{name}.yaml"


def dmr_templates_path(sources_dir: Path) -> Path:
    return sources_dir / "dmr_templates.yaml"


def apply_overrides(
    channels: Iterable[Channel], overrides: Sequence[Override]
) -> tuple[list[Channel], list[AppliedOverride]]:
    """Apply every matching override in file order; overrides match by the upstream callsign."""
    result: list[Channel] = []
    applied: list[AppliedOverride] = []
    for channel in channels:
        changed = channel
        for override in overrides:
            if override.matches(channel):
                changed = replace(changed, **override.changes)
                applied.append(AppliedOverride(channel.name, channel.mode, override))
        result.append(changed)
    return result, applied


def expand_dmr(channels: Iterable[Channel], template: Sequence[TemplateChannel]) -> list[Channel]:
    """Replace each DMR channel by one channel per template entry; other modes pass unchanged."""
    result: list[Channel] = []
    for channel in channels:
        if channel.mode is not Mode.DMR:
            result.append(channel)
            continue
        result.extend(
            replace(
                channel,
                name=f"{channel.name} {entry.name}",
                time_slot=entry.time_slot,
                tx_talkgroup=entry.tx_talkgroup,
                rx_group_list=entry.rx_group_list,
            )
            for entry in template
        )
    return result


_EMPTY = Node(None, "", "")


def _load(path: Path) -> Node:
    try:
        return config.load(path)
    except FileNotFoundError:
        return Node(None, str(path), "")


@dataclass(frozen=True, slots=True)
class _Names:
    talkgroups: Mapping[str, int]
    rx_group_lists: Mapping[str, tuple[str, ...]]

    def talkgroup(self, node: Node) -> str:
        name = node.text()
        if name not in self.talkgroups:
            raise node.error(f"talkgroup {name!r} is not defined in talkgroups.yaml")
        return name

    def rx_group_list(self, node: Node) -> str:
        name = node.text()
        if name not in self.rx_group_lists:
            raise node.error(f"RX group list {name!r} is not defined in talkgroups.yaml")
        return name


def _talkgroups(root: Node) -> tuple[dict[str, int], dict[str, tuple[str, ...]]]:
    fields = root.fields((), ["talkgroups", "rx_group_lists"])
    talkgroups = {
        name: node.integer(1, 16_777_215) for name, node in fields.get("talkgroups", _EMPTY).entries().items()
    }
    names = _Names(talkgroups, {})
    rx_group_lists = {
        name: tuple(names.talkgroup(item) for item in node.items())
        for name, node in fields.get("rx_group_lists", _EMPTY).entries().items()
    }
    return talkgroups, rx_group_lists


def _own_lists(paths: Iterable[Path], names: _Names) -> dict[str, OwnList]:
    lists: dict[str, OwnList] = {}
    for path in paths:
        root = config.load(path)
        fields = root.fields(["name", "channels"], ["tags"])
        name = fields["name"].text()
        if name != path.stem:
            raise fields["name"].error(f"the list in {path.name} must be named {path.stem!r}")
        tags = fields["tags"].texts() if "tags" in fields else ()
        lists[name] = OwnList(name, tuple(_own_channel(node, name, tags, names) for node in fields["channels"].items()))
    return lists


def _own_channel(node: Node, list_name: str, list_tags: tuple[str, ...], names: _Names) -> Channel:
    values = _channel_fields(node.fields(["name", "rx", "mode"], _CHANNEL_KEYS), names)
    channel = Channel(
        name=values["name"], rx_hz=values["rx_hz"], tx_hz=values["rx_hz"], mode=values["mode"], source=list_name
    )
    values["tags"] = (*list_tags, *values.get("tags", ()))
    return replace(channel, **values)


def _overrides(root: Node) -> tuple[Override, ...]:
    return tuple(_override(node) for node in root.fields((), ["overrides"]).get("overrides", _EMPTY).items())


def _override(node: Node) -> Override:
    fields = node.fields(["callsign", "reason", "set"], ["mode"])
    changes = fields["set"].fields((), _OVERRIDE_KEYS)
    if not changes:
        raise fields["set"].error("an override changes at least one field")
    return Override(
        callsign=fields["callsign"].text(),
        reason=fields["reason"].text(),
        changes=_channel_fields(changes, _Names({}, {})),
        mode=_mode(fields["mode"]) if "mode" in fields else None,
    )


def _dmr_templates(root: Node, names: _Names) -> dict[str, tuple[TemplateChannel, ...]]:
    templates = root.fields((), ["templates"]).get("templates", _EMPTY).entries()
    return {name: tuple(_template_channel(item, names) for item in node.items()) for name, node in templates.items()}


def _template_channel(node: Node, names: _Names) -> TemplateChannel:
    fields = node.fields(["name", "time_slot", "tx_talkgroup"], ["rx_group_list"])
    return TemplateChannel(
        name=fields["name"].text(),
        time_slot=fields["time_slot"].integer(1, 2),
        tx_talkgroup=names.talkgroup(fields["tx_talkgroup"]),
        rx_group_list=names.rx_group_list(fields["rx_group_list"]) if "rx_group_list" in fields else None,
    )


def _channel_fields(fields: Mapping[str, Node], names: _Names) -> ChannelFields:
    values = ChannelFields()
    for key, node in fields.items():
        match key:
            case "name":
                values["name"] = node.text()
            case "rx":
                values["rx_hz"] = node.hz(MHZ)
            case "tx":
                values["tx_hz"] = node.hz(MHZ)
            case "mode":
                values["mode"] = _mode(node)
            case "tone_tx":
                values["tone_tx"] = _tone(node)
            case "tone_rx":
                values["tone_rx"] = _tone(node)
            case "bandwidth":
                values["bandwidth_hz"] = node.hz(KHZ)
            case "color_code":
                values["color_code"] = node.integer(0, 15)
            case "time_slot":
                values["time_slot"] = node.integer(1, 2)
            case "tx_talkgroup":
                values["tx_talkgroup"] = names.talkgroup(node)
            case "rx_group_list":
                values["rx_group_list"] = names.rx_group_list(node)
            case "power":
                values["power"] = node.text()
            case "tags":
                values["tags"] = node.texts()
            case _:
                raise AssertionError(f"channel key {key!r} has no reader")
    return values


def _mode(node: Node) -> Mode:
    try:
        return Mode(node.text())
    except ValueError:
        raise node.error(f"mode must be one of {', '.join(Mode)}") from None


def _tone(node: Node) -> Tone:
    fields = node.fields((), ["ctcss", "dcs"])
    if len(fields) != 1:
        raise node.error("a tone is either {ctcss: Hz} or {dcs: code}")
    if "ctcss" in fields:
        return Ctcss(float(fields["ctcss"].number()))
    return Dcs(fields["dcs"].integer(1, 777))
