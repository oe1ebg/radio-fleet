"""Shared by the CSV outputs: the frequency format and the row and column checks (R10)."""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence

from radio_fleet.fleet import Capability


class CsvCheckError(ValueError):
    pass


def rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text, newline="")))


def mhz(hz: int) -> str:
    return f"{hz / 1_000_000:.6f}"


def check_rows(table: Sequence[Sequence[str]], width: int) -> None:
    """Every row has `width` columns, and the first column numbers the rows from 1 on."""
    for number, row in enumerate(table, 1):
        if len(row) != width:
            raise CsvCheckError(f"row {number}: {len(row)} columns, expected {width}")
        if row[0] != str(number):
            raise CsvCheckError(f"row {number}: location {row[0]!r}, expected {number}")


def check_memories(names: Sequence[str], capability: Capability) -> None:
    """The memories fit the radio: their number and the length of each name."""
    if len(names) > capability.channels:
        raise CsvCheckError(f"{len(names)} memories, the radio has {capability.channels}")
    for name in names:
        if len(name) > capability.name_length:
            raise CsvCheckError(f"name {name!r} is longer than {capability.name_length} characters")
