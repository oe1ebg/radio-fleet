"""Power resolution (R4): levels and watts to the value a radio's renderer writes, with synthetic profiles."""

from decimal import Decimal

import pytest

from radio_fleet import power
from radio_fleet.model import Power, Watts
from radio_fleet.power import PowerError, PowerRange, RadioPower, Resolved


def watts(value: str) -> Watts:
    return Watts(Decimal(value))


LEVELS = RadioPower(
    levels={level: level.value for level in Power},
    watts={Power.MAX: watts("5"), Power.HIGH: watts("5"), Power.MID: watts("2"), Power.LOW: watts("1")},
)
STEPPED = RadioPower(
    watts={Power.HIGH: watts("8"), Power.LOW: watts("2")},
    range=PowerRange(watts("1"), watts("10"), watts("1")),
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [("High", Power.HIGH), ("5W", watts("5")), ("0.5W", watts("0.5")), ("high", None), ("5", None), ("W", None)],
)
def test_a_power_is_a_level_or_watts(text: str, expected: object) -> None:
    assert power.parse(text) == expected


@pytest.mark.parametrize(
    ("request_", "resolved"),
    [
        (Power.MID, Resolved("Mid")),
        (watts("2"), Resolved("Mid")),
        (watts("2.4"), Resolved("Mid", "2.4W -> Mid (2W)")),
        (watts("3.5"), Resolved("Mid", "3.5W -> Mid (2W)")),
        (watts("3.6"), Resolved("Max", "3.6W -> Max (5W)")),
        (watts("0.1"), Resolved("Low", "0.1W -> Low (1W)")),
        (watts("25"), Resolved("Max", "25W -> Max (5W)")),
    ],
    ids=["level", "exact", "nearest", "tie-to-lower", "nearest-higher", "below", "above"],
)
def test_watts_give_the_nearest_level(request_: power.Request, resolved: Resolved) -> None:
    assert LEVELS.resolve(request_) == resolved


@pytest.mark.parametrize(
    ("request_", "resolved"),
    [
        (Power.HIGH, Resolved("8W")),
        (watts("5"), Resolved("5W")),
        (watts("2.4"), Resolved("2W", "2.4W -> 2W")),
        (watts("2.5"), Resolved("2W", "2.5W -> 2W")),
        (watts("2.6"), Resolved("3W", "2.6W -> 3W")),
        (watts("0.5"), Resolved("1W", "0.5W -> 1W")),
        (watts("25"), Resolved("10W", "25W -> 10W")),
    ],
    ids=["level", "exact", "nearest", "tie-to-lower", "nearest-higher", "below", "above"],
)
def test_watts_give_the_nearest_step_of_a_range(request_: power.Request, resolved: Resolved) -> None:
    assert STEPPED.resolve(request_) == resolved


def test_a_range_steps_from_its_minimum() -> None:
    stepped = PowerRange(watts("0.5"), watts("5"), watts("1.5"))
    assert [str(stepped.nearest(watts(w))) for w in ("1", "1.25", "1.3", "4.9")] == ["0.5W", "0.5W", "2W", "5W"]
    assert (stepped.allows(watts("3.5")), stepped.allows(watts("3"))) == (True, False)


@pytest.mark.parametrize(
    ("profile", "request_", "message"),
    [
        (STEPPED, Power.MAX, "no watts for the power Max"),
        (RadioPower(levels={Power.HIGH: "HIGH"}), Power.LOW, "no value for the power Low"),
        (RadioPower(levels={Power.HIGH: "HIGH"}), watts("5"), "no level with watts for the power 5W"),
    ],
)
def test_a_request_without_its_map_is_refused(profile: RadioPower, request_: power.Request, message: str) -> None:
    with pytest.raises(PowerError, match=message):
        profile.resolve(request_)


def test_watts_pass_unchanged_to_a_watts_renderer_without_a_map() -> None:
    assert RadioPower(watts_native=True).resolve(watts("2.4")) == Resolved("2.4W")
