"""`fleet publish` and `fleet applied` (R12).

Neither runs git: tagging the applied build is the owner's step, so `applied` only says the command.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

from radio_fleet import record
from radio_fleet.record import Applied


class PublishError(RuntimeError):
    pass


def publish(build: Path, equipment: Path, folder: Path, radio_id: str, today: date) -> Path:
    """Copy the radio's build to `<equipment>/<folder>/generated/<date>/`; an existing target is refused."""
    _require_build(build, radio_id)
    if not equipment.is_dir():
        raise PublishError(f"no equipment directory {equipment}")
    target = equipment / folder / "generated" / today.isoformat()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.mkdir()
    except FileExistsError:
        raise PublishError(f"{target} exists; publish never overwrites a file") from None
    try:
        _copy(build, target)
    except OSError as error:
        shutil.rmtree(target)
        raise PublishError(f"copying to {target} failed, nothing published: {error}") from error
    return target


def _copy(build: Path, target: Path) -> None:
    for file in sorted(path for path in build.rglob("*") if path.is_file()):
        copy = target / file.relative_to(build)
        copy.parent.mkdir(parents=True, exist_ok=True)
        with file.open("rb") as source, copy.open("xb") as destination:
            shutil.copyfileobj(source, destination)


def applied(build: Path, applied_file: Path, radio_id: str, today: date) -> tuple[Applied, str]:
    """Record the build in `applied.yaml`; return the entry and the git tag the owner sets for it."""
    built = _require_build(build, radio_id)
    entries = record.load_applied(applied_file)
    entry = Applied(today.isoformat(), record.digest(build), built.channels)
    entries[radio_id] = entry
    record.save_applied(applied_file, entries)
    return entry, f"applied/{radio_id}/{entry.date}"


def _require_build(build: Path, radio_id: str) -> record.BuildRecord:
    built = record.read_build(build)
    if built is None:
        raise PublishError(f"no build of {radio_id} in {build}; run `fleet build --radio {radio_id}`")
    return built
