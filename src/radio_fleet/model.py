"""The canonical channel model every source reads into and every renderer reads from."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Mode(StrEnum):
    FM = "FM"
    DMR = "DMR"
    C4FM = "C4FM"
    DSTAR = "D-STAR"


@dataclass(frozen=True, slots=True)
class Ctcss:
    hz: float


@dataclass(frozen=True, slots=True)
class Dcs:
    code: int


Tone = Ctcss | Dcs


@dataclass(frozen=True, slots=True)
class Channel:
    """One memory channel. `tx_hz` and `tone_tx` are what the radio transmits."""

    name: str
    rx_hz: int
    tx_hz: int
    mode: Mode
    tone_tx: Tone | None = None
    tone_rx: Tone | None = None
    bandwidth_hz: int | None = None
    color_code: int | None = None
    time_slot: int | None = None
    tx_talkgroup: str | None = None
    rx_group_list: str | None = None
    power: str | None = None
    tags: tuple[str, ...] = ()
    source: str = ""
