"""The canonical channel model every source reads into and every renderer reads from."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class Mode(StrEnum):
    FM = "FM"
    DMR = "DMR"
    C4FM = "C4FM"
    DSTAR = "D-STAR"


class Power(StrEnum):
    """A channel's power level; each radio profile maps the levels to the radio's own values."""

    MAX = "Max"
    HIGH = "High"
    MID = "Mid"
    LOW = "Low"
    MIN = "Min"


@dataclass(frozen=True, slots=True, order=True)
class Watts:
    value: Decimal

    def __str__(self) -> str:
        return f"{self.value.normalize():f}W"


TUNING_STEPS_HZ = (
    1_000,
    2_500,
    5_000,
    6_250,
    9_000,
    10_000,
    12_500,
    15_000,
    20_000,
    25_000,
    30_000,
    50_000,
    100_000,
    125_000,
    200_000,
)
"""The tuning steps of CHIRP (its `chirp_common.TUNING_STEPS`)."""


@dataclass(frozen=True, slots=True)
class Ctcss:
    hz: float


@dataclass(frozen=True, slots=True)
class Dcs:
    code: int


Tone = Ctcss | Dcs


@dataclass(frozen=True, slots=True)
class Position:
    lat: float
    lon: float


@dataclass(frozen=True, slots=True)
class Channel:
    """One memory channel. `tx_hz` and `tone_tx` are what the radio transmits; a receive-only channel
    (`rx_only`) never transmits. `callsign` and `site` (the upstream list's name of the repeater) are set
    on upstream channels only. `power` is a level or watts on a channel as read, and the radio's value of
    it on a selected channel. `step_hz` (a tuning step), `skip` (True: never scanned, False: always scanned)
    and `note` are set by the owner's lists and overrides; None leaves them to the radio's profile."""

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
    power: Power | Watts | str | None = None
    tags: tuple[str, ...] = ()
    source: str = ""
    position: Position | None = None
    rx_only: bool = False
    callsign: str | None = None
    site: str | None = None
    step_hz: int | None = None
    skip: bool | None = None
    note: str | None = None
