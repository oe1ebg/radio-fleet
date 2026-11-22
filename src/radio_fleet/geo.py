"""Maidenhead locators and great-circle distances for the region of a radio profile."""

from __future__ import annotations

import math

from radio_fleet.model import Position

# Each character pair of a locator splits the cell of the pair before it: field A-R, square 0-9,
# subsquare a-x, extended square 0-9.
_DIVISIONS = (18, 10, 24, 10)
_EARTH_RADIUS_KM = 6371.0


def locator_position(locator: str) -> Position:
    """The centre of a Maidenhead locator of 2, 4, 6 or 8 characters."""
    if len(locator) not in (2, 4, 6, 8):
        raise ValueError(f"not a Maidenhead locator: {locator!r}")
    lon, lat, width, height = -180.0, -90.0, 360.0, 180.0
    for pair, division in enumerate(_DIVISIONS[: len(locator) // 2]):
        width, height = width / division, height / division
        x, y = (_index(c, pair, division, locator) for c in locator[2 * pair : 2 * pair + 2])
        lon, lat = lon + x * width, lat + y * height
    return Position(lat + height / 2, lon + width / 2)


def _index(char: str, pair: int, division: int, locator: str) -> int:
    index = ord(char) - ord("0") if pair % 2 else ord(char.upper()) - ord("A")
    if not 0 <= index < division:
        raise ValueError(f"not a Maidenhead locator: {locator!r}")
    return index


def distance_km(a: Position, b: Position) -> float:
    lat_a, lat_b = math.radians(a.lat), math.radians(b.lat)
    d_lat, d_lon = lat_b - lat_a, math.radians(b.lon - a.lon)
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat_a) * math.cos(lat_b) * math.sin(d_lon / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(h))
