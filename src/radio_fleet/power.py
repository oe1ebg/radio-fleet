"""Power (R4): a channel asks for a level or for watts, and the radio's profile resolves the request to the
value its renderer writes."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import ROUND_HALF_DOWN, Decimal

from radio_fleet.model import Power, Watts

WATTS = re.compile(r"(\d+(?:\.\d+)?)\s*W")

Request = Power | Watts


def parse(text: str) -> Request | None:
    """A level or watts, such as `High` or `0.5W`; None for any other text."""
    if text in tuple(Power):
        return Power(text)
    match = WATTS.fullmatch(text)
    return Watts(Decimal(match.group(1))) if match else None


class PowerError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PowerRange:
    """The watts a radio sets from `low` to `high` in steps of `step`; `high` is `low` plus whole steps."""

    low: Watts
    high: Watts
    step: Watts

    def allows(self, watts: Watts) -> bool:
        return self.low <= watts <= self.high and (watts.value - self.low.value) % self.step.value == 0

    def nearest(self, watts: Watts) -> Watts:
        """The nearest step; a tie goes to the lower one."""
        clamped = min(max(watts, self.low), self.high)
        steps = ((clamped.value - self.low.value) / self.step.value).to_integral_value(ROUND_HALF_DOWN)
        return Watts(self.low.value + steps * self.step.value)


@dataclass(frozen=True, slots=True)
class Resolved:
    value: str
    """What the renderer writes."""
    note: str | None = None
    """How the value differs from the requested watts, such as `25W -> Max (5W)`."""


@dataclass(frozen=True, slots=True)
class RadioPower:
    """How one radio's profile turns a request into its renderer's value.

    `levels` is the renderer's value of each level and `watts` the watts that `power_levels` gives a level.
    With a `range`, the renderer writes watts. A `fixed` value, a radio value as `power` was before levels and
    watts, is the value of every channel and refuses a channel's own request. `watts_native` passes watts
    unchanged to a renderer that writes watts, when the profile maps no level to watts.
    """

    default: Request | None = None
    levels: Mapping[Power, str] = field(default_factory=dict)
    watts: Mapping[Power, Watts] = field(default_factory=dict)
    range: PowerRange | None = None
    fixed: str | None = None
    watts_native: bool = False

    def resolve(self, request: Request) -> Resolved:
        if isinstance(request, Watts):
            return self._watts(request)
        if self.range is not None:
            watts = self.watts.get(request)
            if watts is None:
                raise PowerError(f"no watts for the power {request}")
            return Resolved(str(watts))
        value = self.levels.get(request)
        if value is None:
            raise PowerError(f"no value for the power {request}")
        return Resolved(value)

    def _watts(self, watts: Watts) -> Resolved:
        if self.range is not None:
            nearest = self.range.nearest(watts)
            return Resolved(str(nearest), None if nearest == watts else f"{watts} -> {nearest}")
        if self.watts:
            # Max first, so that of two levels with the same watts the higher one wins.
            mapped = [level for level in Power if level in self.watts]
            level = min(mapped, key=lambda level: (abs(self.watts[level].value - watts.value), self.watts[level]))
            got = self.watts[level]
            return Resolved(self.levels[level], None if got == watts else f"{watts} -> {level} ({got})")
        if self.watts_native:
            return Resolved(str(watts))
        raise PowerError(f"no level with watts for the power {watts}")
