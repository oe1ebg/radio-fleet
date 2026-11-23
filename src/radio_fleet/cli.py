"""Command line entry point `fleet`."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from radio_fleet import __version__, build, changes, fleet, publish, snapshot, sources
from radio_fleet.config import ConfigError
from radio_fleet.dmrconf import Dmrconf, DmrconfCli
from radio_fleet.hytera_tool import HyteraCli, HyteraTool
from radio_fleet.jayt import Jayt, JaytCli
from radio_fleet.mcp import Fetcher, FetchError, McpCli
from radio_fleet.model import Channel
from radio_fleet.record import override_text, tone, unmatched_text
from radio_fleet.selection import Selection, mhz, select


def main(
    argv: list[str] | None = None,
    fetcher: Fetcher | None = None,
    dmrconf: Dmrconf | None = None,
    jayt: Jayt | None = None,
    hytera: HyteraTool | None = None,
    today: date | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        prog="fleet", description="Build CPS files for every radio from one channel source."
    )
    parser.add_argument("--version", action="version", version=f"fleet {__version__}")
    data_help = (
        "data root: fleet.yaml, sources/, snapshots/, bases/, applied.yaml, build/"
        " (default: $FLEET_DATA, else the current directory)"
    )
    parser.add_argument("--data", type=Path, help=data_help)
    common = argparse.ArgumentParser(add_help=False)
    # SUPPRESS keeps a --data given before the command when the command's own --data is not given.
    common.add_argument("--data", type=Path, default=argparse.SUPPRESS, help=data_help)
    common.add_argument("--fleet", type=Path, help="fleet file (default: DATA/fleet.yaml)")
    with_snapshots = argparse.ArgumentParser(add_help=False)
    with_snapshots.add_argument("--snapshots", type=Path, help="snapshot directory (default: DATA/snapshots)")
    with_sources = argparse.ArgumentParser(add_help=False)
    with_sources.add_argument("--radio", required=True, help="radio id in the fleet file")
    with_sources.add_argument("--sources", type=Path, help="own lists, overrides, templates (default: DATA/sources)")
    commands = parser.add_subparsers(dest="command")

    fetch = commands.add_parser(
        "fetch", parents=[common, with_snapshots], help="snapshot the upstream sources to snapshots/<source>.csv"
    )
    fetch.add_argument(
        "--source",
        action="append",
        dest="sources",
        metavar="SOURCE",
        help="MCP source to fetch (repeatable; default: the sources of the fleet file)",
    )
    fetch.add_argument("--offline", action="store_true", help="read the existing snapshots instead of the network")

    commands.add_parser(
        "select",
        parents=[common, with_snapshots, with_sources],
        help="print the channels, zones, scan lists and drops of one radio",
    )
    commands.add_parser(
        "build",
        parents=[common, with_snapshots, with_sources],
        help="render one radio's file to build/<radio>/, check it with the radio's tool and update build/CHANGES.md",
    )
    commands.add_parser(
        "publish", parents=[common], help="copy build/<radio>/ to <equipment>/<equipment_dir>/generated/<date>/"
    ).add_argument("radio", help="radio id in the fleet file")
    commands.add_parser(
        "applied",
        parents=[common],
        help="record the build of a radio as applied in applied.yaml and print the git tag command for it",
    ).add_argument("radio", help="radio id in the fleet file")

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    data_root = args.data or Path(os.environ.get("FLEET_DATA") or ".")
    fleet_file = args.fleet or data_root / "fleet.yaml"
    try:
        if args.command in ("publish", "applied"):
            return _record(
                args.command, fleet.load(fleet_file, data_root), data_root, args.radio, today or date.today()
            )
        snapshots_dir = args.snapshots or data_root / "snapshots"
        if args.command == "fetch":
            names = args.sources or list(fleet.load(fleet_file, data_root).sources)
            return _fetch(names, snapshots_dir, args.offline, fetcher or McpCli())
        the_fleet = fleet.load(fleet_file, data_root)
        selection, own = _selection(the_fleet, args.sources or data_root / "sources", snapshots_dir, args.radio)
        if args.command == "select":
            _print(selection)
            return 0
        if jayt is None and the_fleet.jayt is not None:
            jayt = JaytCli(the_fleet.jayt.path, the_fleet.jayt.commit)
        if hytera is None and the_fleet.hytera is not None:
            hytera = HyteraCli(the_fleet.hytera.export, the_fleet.hytera.import_, data_root)
        build_dir = data_root / "build"
        try:
            output = build.build(selection, own, build_dir, dmrconf or DmrconfCli(), McpCli(), jayt, hytera)
        except build.BuildError as error:
            print(f"fleet build: {args.radio}: {error}", file=sys.stderr)
            output = None
        reported = _write_changes(the_fleet, build_dir, data_root / "applied.yaml")
        if output is None:
            return 1
        print(f"{args.radio}: {output}")
        return 0 if reported else 1
    except (ConfigError, snapshot.SnapshotError, publish.PublishError) as error:
        print(f"fleet {args.command}: {error}", file=sys.stderr)
        return 1
    except FileNotFoundError as error:
        print(f"fleet {args.command}: no file {error.filename}", file=sys.stderr)
        return 1
    except (OSError, UnicodeDecodeError) as error:
        print(f"fleet {args.command}: {error}", file=sys.stderr)
        return 1


def _fetch(names: list[str], snapshots_dir: Path, offline: bool, fetcher: Fetcher) -> int:
    """Fetch every source, even after one fails, and report each failure."""
    failed = False
    for source in names:
        path = snapshot.path_for(snapshots_dir, source)
        try:
            if not offline:
                snapshot.write(snapshots_dir, source, fetcher.fetch_csv(source))
            channels = snapshot.read(path)
        except FileNotFoundError:
            print(f"fleet fetch: no snapshot for {source!r} at {path}", file=sys.stderr)
            failed = True
        except (FetchError, snapshot.SnapshotError) as error:
            print(f"fleet fetch: {error}", file=sys.stderr)
            failed = True
        except (OSError, UnicodeDecodeError) as error:
            print(f"fleet fetch: {source!r}: {error}", file=sys.stderr)
            failed = True
        else:
            print(f"{source}: {len(channels)} channels in {path}")
    return 1 if failed else 0


def _write_changes(the_fleet: fleet.Fleet, build_dir: Path, applied_file: Path) -> bool:
    """Rewrite CHANGES.md; a failure is reported on its own and never hides the command's result."""
    try:
        changes.write(the_fleet.radios.values(), build_dir, applied_file)
    except (ConfigError, OSError, UnicodeDecodeError) as error:
        print(f"fleet: {changes.FILE} not written: {error}", file=sys.stderr)
        return False
    return True


def _record(command: str, the_fleet: fleet.Fleet, data_root: Path, radio_id: str, today: date) -> int:
    radio = _radio(the_fleet, radio_id)
    build_dir = data_root / "build"
    if command == "publish":
        if the_fleet.equipment is None:
            raise ConfigError(f"{the_fleet.file}: `fleet publish` needs the equipment directory: equipment: DIR")
        target = publish.publish(build_dir / radio_id, the_fleet.equipment, radio.equipment_dir, radio_id, today)
        print(f"{radio_id}: {target}")
        return 0
    applied_file = data_root / "applied.yaml"
    entry, tag = publish.applied(build_dir / radio_id, applied_file, radio_id, today)
    reported = _write_changes(the_fleet, build_dir, applied_file)
    print(f"{radio_id}: {entry.digest} in {applied_file}")
    print(f"git tag {tag}")
    return 0 if reported else 1


def _selection(
    the_fleet: fleet.Fleet, sources_dir: Path, snapshots_dir: Path, radio_id: str
) -> tuple[Selection, sources.Sources]:
    own = sources.load(sources_dir)
    the_fleet.check_references(own)
    radio = _radio(the_fleet, radio_id)
    upstream: list[Channel] = []
    for source in the_fleet.sources:
        path = snapshot.path_for(snapshots_dir, source)
        if not path.exists():
            raise snapshot.SnapshotError(f"no snapshot for {source!r} at {path}; run `fleet fetch`")
        upstream.extend(snapshot.read(path))
    return select(radio, upstream, own), own


def _radio(the_fleet: fleet.Fleet, radio_id: str) -> fleet.Radio:
    radio = the_fleet.radios.get(radio_id)
    if radio is None:
        raise ConfigError(f"{the_fleet.file}: no radio {radio_id!r}; radios: {', '.join(the_fleet.radios)}")
    return radio


def _print(selection: Selection) -> None:
    radio = selection.radio
    print(
        f"{radio.id} ({radio.model}): {len(selection.channels)} channels, {len(selection.zones)} zones, "
        f"{len(selection.scan_lists)} scan lists"
    )
    for channel in selection.channels:
        print(f"  {_describe(channel)}")
    for kind, groups in (("zone", selection.zones), ("scan list", selection.scan_lists)):
        for group in groups:
            members = [*(f"{name} (base)" for name in group.base_channels), *(c.name for c in group.channels)]
            print(f"{kind} {group.name}: {', '.join(members)}")
    print(f"drops: {len(selection.drops)}")
    for drop in selection.drops:
        print(f"  {drop.name}: {drop.reason}")
    print(f"overrides: {len(selection.overrides)}")
    for applied in selection.overrides:
        print(f"  {override_text(applied)}")
    print(f"overrides that match nothing: {len(selection.unmatched_overrides)}")
    for override in selection.unmatched_overrides:
        print(f"  {unmatched_text(override)}")
    print(f"power set to the nearest value: {len(selection.power_notes)}")
    for note in selection.power_notes:
        print(f"  {note}")


def _describe(channel: Channel) -> str:
    parts = [f"{channel.name:<16}", f"RX {mhz(channel.rx_hz)}", f"TX {mhz(channel.tx_hz)}", str(channel.mode)]
    if channel.tone_tx is not None:
        parts.append(f"tone TX {tone(channel.tone_tx)}")
    if channel.tone_rx is not None:
        parts.append(f"tone RX {tone(channel.tone_rx)}")
    if channel.color_code is not None:
        parts.append(f"CC{channel.color_code}")
    if channel.time_slot is not None:
        parts.append(f"TS{channel.time_slot}")
    if channel.tx_talkgroup is not None:
        parts.append(f"talkgroup {channel.tx_talkgroup}")
    if channel.rx_group_list is not None:
        parts.append(f"RX group {channel.rx_group_list}")
    if channel.power is not None:
        parts.append(f"power {channel.power}")
    if channel.rx_only:
        parts.append("RX only")
    parts.append(f"[{channel.source}]")
    return " ".join(parts)


if __name__ == "__main__":
    raise SystemExit(main())
