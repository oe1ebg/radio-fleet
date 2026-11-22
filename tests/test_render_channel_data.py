"""Power levels and receive-only channels as each renderer writes them (R2, R4), with synthetic data."""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml

from radio_fleet import fleet, sources
from radio_fleet.model import Channel, Mode, Power
from radio_fleet.render import chirp, hytera, jayt, qdmr
from radio_fleet.selection import Selection

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
QDMR_BASE = (EXAMPLES / "bases" / "qdmr" / "d878uv2plus.yaml").read_text(encoding="utf-8")
JAYT_DOCUMENT = "radio: FT-3185\nchannels: []\n"
HYTERA_EXPORT = yaml.safe_dump(
    {
        "tables": {
            key: {"entries": []} for key in ("digital_channels", "analog_channels", "contacts", "rx_groups", "zones")
        }
    }
)
CHANNEL = Channel("XX0PW", 145_500_000, 145_500_000, Mode.FM, power=Power.HIGH)


def qdmr_channels(selection: Selection) -> list[dict[str, Any]]:
    own = sources.load(EXAMPLES / "sources")
    document = qdmr.load(qdmr.render(selection, own, QDMR_BASE))
    assert isinstance(document, dict)
    return [item["fm"] for item in document["channels"] if str(item.get("fm", {}).get("id", "")).startswith("gen_")]


def qdmr_power(selection: Selection) -> str:
    return str(qdmr_channels(selection)[0]["power"])


def chirp_power(selection: Selection) -> str:
    return chirp.render(selection).splitlines()[1].split(",")[15]


def jayt_power(selection: Selection) -> str:
    return str(yaml.safe_load(jayt.render(selection, JAYT_DOCUMENT))["channels"][0]["tx_power"])


def hytera_power(selection: Selection) -> str:
    own = sources.load(EXAMPLES / "sources")
    document = yaml.safe_load(hytera.render(selection, own, HYTERA_EXPORT))
    return str(document["tables"]["analog_channels"]["entries"][0]["settings"]["power_level"])


@pytest.mark.parametrize(
    ("radio_id", "value", "written", "power_of"),
    [
        ("d878uv2plus", "Max", "Max", qdmr_power),
        ("uv5r-mini", "3W", "3.0W", chirp_power),
        ("ft3185", "low2", "LOW2", jayt_power),
        ("hp785", "Middle", "Middle", hytera_power),
    ],
)
def test_a_channel_with_power_high_gets_the_radios_mapped_value_in_every_renderer(
    radio_id: str, value: str, written: str, power_of: Callable[[Selection], str]
) -> None:
    radio = fleet.load(EXAMPLES / "fleet.yaml", EXAMPLES).radios[radio_id]
    mapped = replace(radio, power_values={**radio.power_values, Power.HIGH: value})
    assert power_of(Selection(mapped, (CHANNEL,), (), (), (), ())) == written


def test_the_renderers_write_a_receive_only_channel_so_that_the_radio_cannot_transmit() -> None:
    radios = fleet.load(EXAMPLES / "fleet.yaml", EXAMPLES).radios
    listen = replace(CHANNEL, name="Freenet", rx_hz=149_025_000, tx_hz=149_025_000, rx_only=True)
    (written,) = qdmr_channels(Selection(radios["d878uv2plus"], (listen,), (), (), (), ()))
    assert written["rxOnly"] is True
    row = chirp.render(Selection(radios["uv5r-mini"], (listen,), (), (), (), ())).splitlines()[1]
    assert row.split(",")[1:5] == ["Freenet", "149.025000", "off", "0.000000"]
