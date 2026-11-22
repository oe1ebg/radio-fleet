"""Command line entry point `fleet`."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from radio_fleet import __version__, fleet, snapshot, sources
from radio_fleet.config import ConfigError
from radio_fleet.dmrconf import CheckError, DmrconfCli, Verifier
from radio_fleet.fleet import Renderer
from radio_fleet.mcp import Fetcher, FetchError, McpCli
from radio_fleet.model import Channel, Ctcss, Dcs, Tone
from radio_fleet.render import qdmr
from radio_fleet.selection import Selection, mhz, select


def main(argv: list[str] | None = None, fetcher: Fetcher | None = None, verifier: Verifier | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fleet", description="Build CPS files for every radio from one channel source."
    )
    parser.add_argument("--version", action="version", version=f"fleet {__version__}")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--data",
        type=Path,
        help="data root: fleet.yaml, sources/, snapshots/, bases/ (default: $FLEET_DATA, else the current directory)",
    )
    common.add_argument("--fleet", type=Path, help="fleet file (default: DATA/fleet.yaml)")
    common.add_argument("--snapshots", type=Path, help="snapshot directory (default: DATA/snapshots)")
    commands = parser.add_subparsers(dest="command")

    fetch = commands.add_parser(
        "fetch", parents=[common], help="snapshot the upstream sources to snapshots/<source>.csv"
    )
    fetch.add_argument(
        "--source",
        action="append",
        dest="sources",
        metavar="SOURCE",
        help="MCP source to fetch (repeatable; default: the sources of the fleet file)",
    )
    fetch.add_argument("--offline", action="store_true", help="read the existing snapshots instead of the network")

    select_command = commands.add_parser(
        "select", parents=[common], help="print the channels, zones and drops of one radio"
    )
    select_command.add_argument("--radio", required=True, help="radio id in the fleet file")
    select_command.add_argument("--sources", type=Path, help="own lists, overrides, templates (default: DATA/sources)")

    build = commands.add_parser(
        "build", parents=[common], help="render one radio's file to DATA/build/<radio>/ and check it"
    )
    build.add_argument("--radio", required=True, help="radio id in the fleet file")
    build.add_argument("--sources", type=Path, help="own lists, overrides, templates (default: DATA/sources)")

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    data_root = args.data or Path(os.environ.get("FLEET_DATA") or ".")
    fleet_file = args.fleet or data_root / "fleet.yaml"
    snapshots_dir = args.snapshots or data_root / "snapshots"
    try:
        if args.command == "fetch":
            names = args.sources or list(fleet.load(fleet_file, data_root).sources)
            return _fetch(names, snapshots_dir, args.offline, fetcher or McpCli())
        the_fleet = fleet.load(fleet_file, data_root)
        own = sources.load(args.sources or data_root / "sources")
        selection = _selection(the_fleet, own, snapshots_dir, args.radio)
        if args.command == "select":
            _print(selection)
            return 0
        return _build(selection, own, data_root / "build", verifier or DmrconfCli())
    except (ConfigError, snapshot.SnapshotError, qdmr.RenderError) as error:
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


def _selection(the_fleet: fleet.Fleet, own: sources.Sources, snapshots_dir: Path, radio_id: str) -> Selection:
    the_fleet.check_references(own)
    radio = the_fleet.radios.get(radio_id)
    if radio is None:
        raise ConfigError(f"{the_fleet.file}: no radio {radio_id!r}; radios: {', '.join(the_fleet.radios)}")
    upstream: list[Channel] = []
    for source in the_fleet.sources:
        path = snapshot.path_for(snapshots_dir, source)
        if not path.exists():
            raise ConfigError(f"no snapshot for {source!r} at {path}; run `fleet fetch`")
        upstream.extend(snapshot.read(path))
    return select(radio, upstream, own)


def _build(selection: Selection, own: sources.Sources, build_dir: Path, verifier: Verifier) -> int:
    """Write the radio's file and check it; a file that fails its check is removed, so build/ holds only checked
    files."""
    radio = selection.radio
    if radio.renderer is not Renderer.QDMR:
        raise ConfigError(f"{radio.id}: the {radio.renderer} renderer is not built yet")
    if radio.base is None:
        raise ConfigError(f"{radio.id}: the qdmr renderer needs a base file")
    dmrconf_radio = qdmr.dmrconf_radio(radio.model)
    text = qdmr.render(selection, own, radio.base)
    out = build_dir / radio.id / f"{radio.id}.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    try:
        messages = verifier.verify(out, dmrconf_radio)
    except CheckError as error:
        out.unlink()
        print(f"fleet build: {radio.id}: dmrconf verify failed:\n{error}", file=sys.stderr)
        return 1
    for message in messages:
        print(f"{radio.id}: dmrconf: {message}", file=sys.stderr)
    print(
        f"{radio.id}: {len(selection.channels)} channels, {len(selection.zones)} zones, "
        f"{len(selection.drops)} drops in {out}; dmrconf verify -R {dmrconf_radio} passed"
    )
    return 0


def _print(selection: Selection) -> None:
    radio = selection.radio
    print(f"{radio.id} ({radio.model}): {len(selection.channels)} channels, {len(selection.zones)} zones")
    for channel in selection.channels:
        print(f"  {_describe(channel)}")
    for zone in selection.zones:
        print(f"zone {zone.name}: {', '.join(channel.name for channel in zone.channels)}")
    print(f"drops: {len(selection.drops)}")
    for drop in selection.drops:
        print(f"  {drop.name}: {drop.reason}")
    print(f"overrides: {len(selection.overrides)}")
    for applied in selection.overrides:
        override = applied.override
        changes = ", ".join(f"{key}={_value(value, key)}" for key, value in override.changes.items())
        print(f"  {applied.channel} {applied.mode}: {changes} ({override.reason})")


def _describe(channel: Channel) -> str:
    parts = [f"{channel.name:<16}", f"RX {mhz(channel.rx_hz)}", f"TX {mhz(channel.tx_hz)}", str(channel.mode)]
    if channel.tone_tx is not None:
        parts.append(f"tone TX {_tone(channel.tone_tx)}")
    if channel.tone_rx is not None:
        parts.append(f"tone RX {_tone(channel.tone_rx)}")
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
    parts.append(f"[{channel.source}]")
    return " ".join(parts)


def _value(value: object, key: str) -> str:
    if isinstance(value, Ctcss | Dcs):
        return _tone(value)
    if key in ("rx_hz", "tx_hz") and isinstance(value, int):
        return f"{mhz(value)} MHz"
    if key == "bandwidth_hz" and isinstance(value, int):
        return f"{value / 1000:g} kHz"
    if isinstance(value, tuple):
        return ",".join(map(str, value))
    return str(value)


def _tone(tone: Tone) -> str:
    return f"CTCSS {tone.hz:g}" if isinstance(tone, Ctcss) else f"DCS {tone.code:03d}"


if __name__ == "__main__":
    raise SystemExit(main())
