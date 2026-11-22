"""What a build and an applied build leave behind (R11, R12): the build record in `build/<radio>/` and the
data root's `applied.yaml`.

A channel is recorded as its name and the fields the radio holds, each as text, so that two builds compare
by name and field whatever renderer wrote the file. The power is the radio's value, as the selection
holds it.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from radio_fleet import config
from radio_fleet.config import Node
from radio_fleet.model import Channel, Ctcss, Dcs, Tone
from radio_fleet.selection import Drop, Selection, mhz
from radio_fleet.sources import AppliedOverride, Override

RECORD = "selection.yaml"


def _text(value: object) -> str | None:
    return None if value is None else str(value)


_FIELDS: dict[str, Callable[[Channel], str | None]] = {
    "rx": lambda channel: mhz(channel.rx_hz),
    "tx": lambda channel: mhz(channel.tx_hz),
    "mode": lambda channel: str(channel.mode),
    "tone_tx": lambda channel: None if channel.tone_tx is None else tone(channel.tone_tx),
    "tone_rx": lambda channel: None if channel.tone_rx is None else tone(channel.tone_rx),
    "bandwidth": lambda channel: None if channel.bandwidth_hz is None else f"{channel.bandwidth_hz / 1000:g} kHz",
    "color_code": lambda channel: _text(channel.color_code),
    "time_slot": lambda channel: _text(channel.time_slot),
    "tx_talkgroup": lambda channel: _text(channel.tx_talkgroup),
    "rx_group_list": lambda channel: _text(channel.rx_group_list),
    "power": lambda channel: channel.power,
    "rx_only": lambda channel: "yes" if channel.rx_only else None,
}
FIELDS = tuple(_FIELDS)
"""The fields of a channel record besides its name, in the order they are written and compared."""

ChannelRecord = Mapping[str, str]
"""`name` and the fields of FIELDS the channel has."""


@dataclass(frozen=True, slots=True)
class BuildRecord:
    channels: tuple[ChannelRecord, ...]
    drops: tuple[Drop, ...]
    overrides: tuple[str, ...]
    unmatched_overrides: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Applied:
    date: str
    digest: str
    channels: tuple[ChannelRecord, ...]


def channel_record(channel: Channel) -> dict[str, str]:
    values = {field: text(channel) for field, text in _FIELDS.items()}
    return {"name": channel.name} | {field: value for field, value in values.items() if value is not None}


def tone(tone: Tone) -> str:
    return f"CTCSS {tone.hz:g}" if isinstance(tone, Ctcss) else f"DCS {tone.code:03d}"


def override_text(applied: AppliedOverride) -> str:
    """An applied override: the channel it changed, by callsign, mode and band, and its changes."""
    target = " ".join(part for part in (applied.channel, applied.mode, applied.band) if part)
    return f"{target}: {_changes(applied.override)}"


def unmatched_text(override: Override) -> str:
    """An override that matches nothing: what it matches, by callsign and the mode and band it names."""
    target = " ".join(part for part in (override.callsign, override.mode, override.band) if part)
    return f"{target}: {_changes(override)}"


def _changes(override: Override) -> str:
    changes = [f"{key}={_value(value, key)}" for key, value in override.changes.items()]
    changes += [f"{field}=-" for field in override.clear]
    return f"{', '.join(changes)} ({override.reason})"


def _value(value: object, key: str) -> str:
    if isinstance(value, Ctcss | Dcs):
        return tone(value)
    if key in ("rx_hz", "tx_hz") and isinstance(value, int):
        return f"{mhz(value)} MHz"
    if key == "bandwidth_hz" and isinstance(value, int):
        return f"{value / 1000:g} kHz"
    if isinstance(value, tuple):
        return ",".join(map(str, value))
    return str(value)


def write_build(selection: Selection, directory: Path) -> None:
    document = {
        "channels": [channel_record(channel) for channel in selection.channels],
        "drops": [{"name": drop.name, "reason": drop.reason} for drop in selection.drops],
        "overrides": [override_text(applied) for applied in selection.overrides],
        "unmatched_overrides": [unmatched_text(override) for override in selection.unmatched_overrides],
    }
    directory.mkdir(parents=True, exist_ok=True)
    (directory / RECORD).write_text(_dump(document), encoding="utf-8")


def read_build(directory: Path) -> BuildRecord | None:
    """None when the radio has no complete build."""
    path = directory / RECORD
    if not path.is_file():
        return None
    fields = config.load(path).fields(["channels", "drops", "overrides"], ["unmatched_overrides"])
    drops = []
    for item in fields["drops"].items():
        drop = item.fields(["name", "reason"])
        drops.append(Drop(drop["name"].text(), drop["reason"].text()))
    unmatched = fields["unmatched_overrides"].texts() if "unmatched_overrides" in fields else ()
    return BuildRecord(_channels(fields["channels"]), tuple(drops), fields["overrides"].texts(), unmatched)


def load_applied(path: Path) -> dict[str, Applied]:
    """The applied build of each radio; none when the file does not exist yet."""
    if not path.exists():
        return {}
    applied = {}
    for radio_id, node in config.load(path).entries().items():
        fields = node.fields(["date", "digest", "channels"])
        applied[radio_id] = Applied(fields["date"].text(), fields["digest"].text(), _channels(fields["channels"]))
    return applied


def save_applied(path: Path, applied: Mapping[str, Applied]) -> None:
    document = {
        radio_id: {"date": entry.date, "digest": entry.digest, "channels": [dict(c) for c in entry.channels]}
        for radio_id, entry in applied.items()
    }
    partial = path.with_name(path.name + ".partial")
    partial.write_text(_dump(document), encoding="utf-8")
    os.replace(partial, path)


def digest(directory: Path) -> str:
    """The SHA-256 of every file of a build, by its path in the build and its content."""
    files = sorted((path.relative_to(directory).as_posix(), path) for path in directory.rglob("*") if path.is_file())
    total = hashlib.sha256()
    for name, path in files:
        total.update(name.encode() + b"\0" + hashlib.sha256(path.read_bytes()).digest())
    return f"sha256:{total.hexdigest()}"


def _channels(node: Node) -> tuple[ChannelRecord, ...]:
    return tuple({key: value.text() for key, value in item.fields(["name"], FIELDS).items()} for item in node.items())


def _dump(document: object) -> str:
    return yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=1000)
