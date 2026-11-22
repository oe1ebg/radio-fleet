"""`build/CHANGES.md` (R11): per radio, what its build changes against the last applied build.

The report is made from the build records and `applied.yaml` only, never from a radio file or a base, so
it holds no secret and no base path.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path

from radio_fleet import record
from radio_fleet.config import ConfigError
from radio_fleet.fleet import Radio
from radio_fleet.record import Applied, BuildRecord, ChannelRecord

FILE = "CHANGES.md"


def write(radios: Iterable[Radio], build_dir: Path, applied_file: Path) -> Path:
    applied = record.load_applied(applied_file)
    sections = [_radio_section(radio, build_dir / radio.id, applied.get(radio.id)) for radio in radios]
    path = build_dir / FILE
    build_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(report(sections), encoding="utf-8")
    return path


def report(sections: Sequence[str]) -> str:
    head = "# Changes\n\nEach radio's build in `build/` against its last applied build in `applied.yaml`.\n"
    return "\n".join([head, *sections])


def _radio_section(radio: Radio, directory: Path, applied: Applied | None) -> str:
    try:
        build = record.read_build(directory)
    except ConfigError:
        unreadable = f"The build record {record.RECORD} is unreadable; run `fleet build --radio {radio.id}`."
        return f"{_heading(radio)}{unreadable}\n"
    return _section(radio, build, applied)


def _heading(radio: Radio) -> str:
    return f"## {radio.id}: {radio.model} ({radio.renderer})\n\n"


def _section(radio: Radio, build: BuildRecord | None, applied: Applied | None) -> str:
    if build is None:
        return _heading(radio) + "Not built.\n"
    lines = [_heading(radio).rstrip("\n"), ""]
    before_channels = applied.channels if applied is not None else ()
    repeated = _repeated(before_channels, build.channels)
    before = _keyed(before_channels, repeated)
    after = _keyed(build.channels, repeated)
    added = [_describe(key, after[key]) for key in after if key not in before]
    removed = [_describe(key, before[key]) for key in before if key not in after]
    changed = [_changes(key, before[key], after[key]) for key in after if key in before and before[key] != after[key]]
    if applied is None:
        lines.append(f"First build, nothing applied: {len(build.channels)} channels.")
    else:
        unchanged = len(after) - len(added) - len(changed)
        lines.append(
            f"Against the build applied on {applied.date}: {len(build.channels)} channels, {unchanged} unchanged."
        )
    lines += _list("Added", added)
    lines += _list("Removed", removed)
    lines += _list("Changed", changed)
    lines += _list("Drops", [f"{drop.name}: {drop.reason}" for drop in build.drops])
    lines += _list("Overrides", list(build.overrides))
    return "\n".join([*lines, ""])


Key = tuple[str, str, int]
"""A channel's name, and for a name that repeats its mode and its count within name and mode."""


def _keyed(channels: Sequence[ChannelRecord], repeated: set[str]) -> dict[Key, ChannelRecord]:
    """Channels by name; the channels of a repeated name, such as a multi-mode repeater, by name and mode.

    A name that is unique on both sides is matched by name alone, so a change of mode shows as a change.
    """
    seen: Counter[tuple[str, str]] = Counter()
    keyed = {}
    for channel in channels:
        name = channel["name"]
        if name not in repeated:
            keyed[name, "", 1] = channel
            continue
        mode = channel.get("mode", "")
        seen[name, mode] += 1
        keyed[name, mode, seen[name, mode]] = channel
    return keyed


def _repeated(*sides: Sequence[ChannelRecord]) -> set[str]:
    return {name for side in sides for name, count in Counter(c["name"] for c in side).items() if count > 1}


def _label(key: Key) -> str:
    name, mode, count = key
    if not mode:
        return name
    return f"{name} [{mode}]" if count == 1 else f"{name} [{mode} #{count}]"


def _changes(key: Key, before: ChannelRecord, after: ChannelRecord) -> str:
    fields = [field for field in record.FIELDS if before.get(field) != after.get(field)]
    diffs = [f"{field} {before.get(field, '-')} -> {after.get(field, '-')}" for field in fields]
    return f"{_label(key)}: " + "; ".join(diffs)


def _describe(key: Key, channel: ChannelRecord) -> str:
    return f"{_label(key)}: " + ", ".join(f"{field} {value}" for field, value in channel.items() if field != "name")


def _list(title: str, items: Sequence[str]) -> list[str]:
    return ["", f"### {title} ({len(items)})", "", *([f"- {item}" for item in items] or ["None."])]
