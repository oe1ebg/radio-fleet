"""`build/CHANGES.md` (R11): per radio, what its build changes against the last applied build.

The report is made from the build records and `applied.yaml` only, never from a radio file or a base, so
it holds no secret and no base path.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path

from radio_fleet import record
from radio_fleet.fleet import Radio
from radio_fleet.record import Applied, BuildRecord, ChannelRecord

FILE = "CHANGES.md"


def write(radios: Iterable[Radio], build_dir: Path, applied_file: Path) -> Path:
    applied = record.load_applied(applied_file)
    sections = [_section(radio, record.read_build(build_dir / radio.id), applied.get(radio.id)) for radio in radios]
    path = build_dir / FILE
    build_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(report(sections), encoding="utf-8")
    return path


def report(sections: Sequence[str]) -> str:
    head = "# Changes\n\nEach radio's build in `build/` against its last applied build in `applied.yaml`.\n"
    return "\n".join([head, *sections])


def _section(radio: Radio, build: BuildRecord | None, applied: Applied | None) -> str:
    lines = [f"## {radio.id}: {radio.model} ({radio.renderer})", ""]
    if build is None:
        return "\n".join([*lines, "Not built.", ""])
    before = _keyed(applied.channels if applied is not None else ())
    after = _keyed(build.channels)
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


def _keyed(channels: Iterable[ChannelRecord]) -> dict[str, ChannelRecord]:
    """Channels by name; a name that repeats is told apart by its count, `name (2)`."""
    seen: Counter[str] = Counter()
    keyed = {}
    for channel in channels:
        name = channel["name"]
        seen[name] += 1
        keyed[name if seen[name] == 1 else f"{name} ({seen[name]})"] = channel
    return keyed


def _changes(key: str, before: ChannelRecord, after: ChannelRecord) -> str:
    fields = [field for field in record.FIELDS if before.get(field) != after.get(field)]
    return f"{key}: " + "; ".join(f"{field} {before.get(field, '-')} -> {after.get(field, '-')}" for field in fields)


def _describe(key: str, channel: ChannelRecord) -> str:
    return f"{key}: " + ", ".join(f"{key} {value}" for key, value in channel.items() if key != "name")


def _list(title: str, items: Sequence[str]) -> list[str]:
    return ["", f"### {title} ({len(items)})", "", *([f"- {item}" for item in items] or ["None."])]
