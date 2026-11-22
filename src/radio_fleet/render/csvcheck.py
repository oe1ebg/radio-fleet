"""The row and column checks of the CSV outputs (R10): what the radio's import tool would refuse or cut."""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence

from radio_fleet.fleet import Capability


class CsvCheckError(ValueError):
    pass


def rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text, newline="")))


def check_rows(table: Sequence[Sequence[str]], width: int, location: int, first: int) -> None:
    """Every row has `width` columns, and the column `location` numbers the rows from `first` on."""
    for number, row in enumerate(table, first):
        if len(row) != width:
            raise CsvCheckError(f"row {number}: {len(row)} columns, expected {width}")
        if row[location] != str(number):
            raise CsvCheckError(f"row {number}: location {row[location]!r}, expected {number}")


def check_memories(names: Sequence[str], capability: Capability) -> None:
    """The memories fit the radio: their number and the length of each name."""
    if len(names) > capability.channels:
        raise CsvCheckError(f"{len(names)} memories, the radio has {capability.channels}")
    for name in names:
        if len(name) > capability.name_length:
            raise CsvCheckError(f"name {name!r} is longer than {capability.name_length} characters")
