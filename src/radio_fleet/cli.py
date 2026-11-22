"""Command line entry point `fleet`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from radio_fleet import __version__, snapshot
from radio_fleet.mcp import Fetcher, FetchError, McpCli

DEFAULT_SOURCES = ("oevsv-repeater-db",)


def main(argv: list[str] | None = None, fetcher: Fetcher | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fleet", description="Build CPS files for every radio from one channel source."
    )
    parser.add_argument("--version", action="version", version=f"fleet {__version__}")
    commands = parser.add_subparsers(dest="command")

    fetch = commands.add_parser("fetch", help="snapshot the upstream sources to snapshots/<source>.csv")
    fetch.add_argument(
        "--source",
        action="append",
        dest="sources",
        metavar="SOURCE",
        help=f"MCP source to fetch (repeatable; default: {', '.join(DEFAULT_SOURCES)})",
    )
    fetch.add_argument(
        "--snapshots", type=Path, default=Path("snapshots"), help="snapshot directory (default: snapshots)"
    )
    fetch.add_argument("--offline", action="store_true", help="read the existing snapshots instead of the network")

    args = parser.parse_args(argv)
    if args.command == "fetch":
        return _fetch(args.sources or list(DEFAULT_SOURCES), args.snapshots, args.offline, fetcher or McpCli())
    parser.print_help()
    return 0


def _fetch(sources: list[str], snapshots_dir: Path, offline: bool, fetcher: Fetcher) -> int:
    for source in sources:
        path = snapshot.path_for(snapshots_dir, source)
        try:
            if not offline:
                snapshot.write(snapshots_dir, source, fetcher.fetch_csv(source))
            channels = snapshot.read(path)
        except FileNotFoundError:
            print(f"fleet fetch: no snapshot for {source!r} at {path}", file=sys.stderr)
            return 1
        except (FetchError, snapshot.SnapshotError) as error:
            print(f"fleet fetch: {error}", file=sys.stderr)
            return 1
        print(f"{source}: {len(channels)} channels in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
