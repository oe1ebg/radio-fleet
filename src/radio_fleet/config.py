"""Strict reading of the YAML configuration: every key known, every value typed, every error names its place."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml


class ConfigError(ValueError):
    pass


def load(path: Path) -> Node:
    """Raises FileNotFoundError when the file is missing, ConfigError when it is not valid YAML."""
    with path.open(encoding="utf-8") as f:
        try:
            return Node(yaml.safe_load(f), str(path), "")
        except yaml.YAMLError as error:
            raise ConfigError(f"{path}: {error}") from error


@dataclass(frozen=True, slots=True)
class Node:
    """One YAML value and where it is: the file and the key path inside it."""

    value: object
    file: str
    path: str

    def error(self, message: str) -> ConfigError:
        return ConfigError(f"{self.file}: {self.path}: {message}" if self.path else f"{self.file}: {message}")

    def fields(self, required: Iterable[str] = (), optional: Iterable[str] = ()) -> dict[str, Node]:
        """A mapping with fixed keys; unknown keys and missing required keys are refused."""
        entries = self.entries()
        required = tuple(required)
        unknown = sorted(set(entries) - set(required) - set(optional))
        if unknown:
            raise self.error(f"unknown key {unknown[0]!r}")
        for key in required:
            if key not in entries:
                raise self.error(f"{key!r} is required")
        return entries

    def entries(self) -> dict[str, Node]:
        """A mapping with free keys, such as names; an empty value reads as an empty mapping."""
        if self.value is None:
            return {}
        if not isinstance(self.value, dict):
            raise self.error("expected a mapping")
        entries: dict[str, Node] = {}
        for key, value in self.value.items():
            if not isinstance(key, str):
                raise self.error(f"key {key!r} is not a string")
            entries[key] = Node(value, self.file, _join(self.path, key))
        return entries

    def items(self) -> list[Node]:
        """A list; an empty value reads as an empty list."""
        if self.value is None:
            return []
        if not isinstance(self.value, list):
            raise self.error("expected a list")
        return [Node(value, self.file, f"{self.path}[{i}]") for i, value in enumerate(self.value)]

    def text(self) -> str:
        if not isinstance(self.value, str) or not self.value:
            raise self.error("expected a non-empty string")
        return self.value

    def texts(self) -> tuple[str, ...]:
        return tuple(item.text() for item in self.items())

    def integer(self, low: int, high: int) -> int:
        if isinstance(self.value, bool) or not isinstance(self.value, int) or not low <= self.value <= high:
            raise self.error(f"expected a whole number from {low} to {high}")
        return self.value

    def number(self) -> Decimal:
        """A positive number; YAML floats go through their shortest text, so 431.4625 stays exact."""
        if isinstance(self.value, bool) or not isinstance(self.value, int | float | str):
            raise self.error("expected a number")
        try:
            value = Decimal(str(self.value))
        except InvalidOperation:
            raise self.error("expected a number") from None
        if not value.is_finite() or value <= 0:
            raise self.error("expected a positive number")
        return value

    def hz(self, unit: int) -> int:
        """A frequency given in `unit` Hz (MHz: 1_000_000, kHz: 1_000), as whole Hz."""
        return round(self.number() * unit)


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key
