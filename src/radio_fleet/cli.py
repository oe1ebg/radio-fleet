"""Command line entry point `fleet`."""

from __future__ import annotations

import argparse

from radio_fleet import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fleet", description="Build CPS files for every radio from one channel source."
    )
    parser.add_argument("--version", action="version", version=f"fleet {__version__}")
    parser.parse_args(argv)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
