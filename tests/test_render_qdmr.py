import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import DMR_REPEATER, FM_REPEATER, mcp_row

from radio_fleet import fleet, sources
from radio_fleet.render import qdmr
from radio_fleet.selection import Selection, select
from radio_fleet.snapshot import channels_from_rows

FLEET = """
sources: [synthetic-db]
radios:
  anytone:
    model: AnyTone D878UV II Plus
    renderer: qdmr
    base: base.yaml
    capability:
      bands:
        - {name: 2m, rx: [136, 174], tx: [144, 146]}
        - {name: 70cm, rx: [400, 480], tx: [430, 440]}
      modes: [FM, DMR]
      channels: 100
      zones: 10
      zone_channels: 10
      name_length: 16
    region: {prefixes: [XX0]}
    own_lists: [simplex]
    dmr_template: standard
    zones:
      - {name: FM, mode: FM}
      - {name: DMR, mode: DMR}
    power: High
"""

SOURCES = {
    "talkgroups.yaml": "talkgroups: {TG9: 9, TG99: 99, TG232: 232}\nrx_group_lists: {Austria: [TG232, TG9]}\n",
    "dmr_templates.yaml": (
        "templates:\n  standard:\n"
        "    - {name: TS1 TG232, time_slot: 1, tx_talkgroup: TG232, rx_group_list: Austria}\n"
        "    - {name: TS2 TG9, time_slot: 2, tx_talkgroup: TG9}\n"
    ),
    "own/simplex.yaml": (
        "name: simplex\nchannels:\n"
        "  - {name: DMR Simplex, rx: 433.45, mode: DMR, color_code: 1, time_slot: 1, tx_talkgroup: TG99}\n"
    ),
}

# Hand-made objects, an AnyTone-style `Off` enum, and generated objects of an earlier build.
BASE = """
version: 0.12.0
settings: {introLine1: Synthetic, defaultID: id1, anytone: {autoRepeaterDirectionA: Off}}
radioIDs:
  - dmr: {id: id1, name: XX0XXX, number: 9990001}
contacts:
  - dmr: {id: cont1, name: Worldwide, ring: false, type: GroupCall, number: 9}
  - dmr: {id: gen_tg5, name: Stale, ring: false, type: GroupCall, number: 5}
groupLists:
  - {id: grp1, name: Worldwide, contacts: [cont1]}
channels:
  - fm: {id: ch1, name: APRS, rxFrequency: 144.8 MHz, txFrequency: 144.8 MHz}
  - fm: {id: gen_ch1, name: Stale, rxFrequency: 145.5 MHz, txFrequency: 145.5 MHz}
zones:
  - {id: zone1, name: APRS, A: [ch1], B: []}
  - {id: gen_zone1, name: Stale, A: [gen_ch1], B: []}
scanLists:
  - {id: scan1, name: APRS, channels: [ch1]}
  - {id: gen_scan1, name: Stale, channels: [gen_ch1]}
positioning:
  - aprs: {id: aprs1, name: APRS, period: 300, revert: ch1, path: [WIDE1-1]}
"""

DCS_REPEATER = mcp_row(
    callsign="XX0DC", freq_tx="431.025", freq_rx="438.625", dtcs_tx="23", fm="True", bandwidth="25", lat="0", long="0"
)


def setup(tmp_path: Path, own_list: str = SOURCES["own/simplex.yaml"]) -> tuple[Selection, sources.Sources, Path]:
    for name, text in {**SOURCES, "own/simplex.yaml": own_list}.items():
        (tmp_path / "sources" / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "sources" / name).write_text(text)
    (tmp_path / "base.yaml").write_text(BASE)
    (tmp_path / "fleet.yaml").write_text(FLEET)
    own = sources.load(tmp_path / "sources")
    radio = fleet.load(tmp_path / "fleet.yaml", tmp_path).radios["anytone"]
    upstream = list(channels_from_rows([DCS_REPEATER, DMR_REPEATER, FM_REPEATER]))
    return select(radio, upstream, own), own, tmp_path / "base.yaml"


def load(text: str) -> dict[str, Any]:
    codeplug = yaml.load(text, Loader=qdmr._Loader)
    assert isinstance(codeplug, dict)
    return codeplug


def without_generated(codeplug: dict[str, Any]) -> dict[str, Any]:
    return {
        key: [entry for entry in value if not qdmr._generated(entry)] if key in qdmr.GENERATED_LISTS else value
        for key, value in codeplug.items()
    }


def test_rendering_twice_gives_the_same_file(tmp_path: Path) -> None:
    selection, own, base = setup(tmp_path)
    first = qdmr.render(selection, own, base)
    assert qdmr.render(selection, own, base) == first
    base.write_text(first)
    assert qdmr.render(selection, own, base) == first


def test_hand_made_objects_settings_and_positioning_are_unchanged(tmp_path: Path) -> None:
    selection, own, base = setup(tmp_path)
    rendered = load(qdmr.render(selection, own, base))
    assert without_generated(rendered) == without_generated(load(BASE))
    assert rendered["settings"]["anytone"]["autoRepeaterDirectionA"] == "Off"
    assert "Stale" not in str(rendered)


def test_the_selection_becomes_generated_channels_contacts_group_lists_and_zones(tmp_path: Path) -> None:
    selection, own, base = setup(tmp_path)
    rendered = load(qdmr.render(selection, own, base))
    generated = {key: [e for e in rendered[key] if qdmr._generated(e)] for key in qdmr.GENERATED_LISTS}

    assert generated["contacts"] == [
        {"dmr": {"id": "gen_tg99", "name": "TG99", "ring": False, "type": "GroupCall", "number": 99}},
        {"dmr": {"id": "gen_tg232", "name": "TG232", "ring": False, "type": "GroupCall", "number": 232}},
    ]
    # TG9 reuses the hand-made contact cont1 with the same number.
    assert generated["groupLists"] == [{"id": "gen_grp1", "name": "Austria", "contacts": ["gen_tg232", "cont1"]}]
    assert generated["channels"] == [
        {
            "dmr": {
                "id": "gen_ch1",
                "name": "DMR Simplex",
                "rxFrequency": "433.45 MHz",
                "txFrequency": "433.45 MHz",
                "power": "High",
                "colorCode": 1,
                "timeSlot": "TS1",
                "contact": "gen_tg99",
            }
        },
        {
            "fm": {
                "id": "gen_ch2",
                "name": "XX0DC",
                "rxFrequency": "438.625 MHz",
                "txFrequency": "431.025 MHz",
                "power": "High",
                "bandwidth": "Wide",
                "txTone": {"dcs": 23},
            }
        },
        {
            "dmr": {
                "id": "gen_ch3",
                "name": "XX0DM TS1 TG232",
                "rxFrequency": "438.9625 MHz",
                "txFrequency": "431.4625 MHz",
                "power": "High",
                "colorCode": 1,
                "timeSlot": "TS1",
                "groupList": "gen_grp1",
                "contact": "gen_tg232",
            }
        },
        {
            "dmr": {
                "id": "gen_ch4",
                "name": "XX0DM TS2 TG9",
                "rxFrequency": "438.9625 MHz",
                "txFrequency": "431.4625 MHz",
                "power": "High",
                "colorCode": 1,
                "timeSlot": "TS2",
                "contact": "cont1",
            }
        },
        {
            "fm": {
                "id": "gen_ch5",
                "name": "XX0FM",
                "rxFrequency": "145.6 MHz",
                "txFrequency": "145 MHz",
                "power": "High",
                "bandwidth": "Narrow",
                "rxTone": {"ctcss": "88.5 Hz"},
                "txTone": {"ctcss": "88.5 Hz"},
            }
        },
    ]
    assert generated["zones"] == [
        {"id": "gen_zone1", "name": "FM", "A": ["gen_ch2", "gen_ch5"], "B": []},
        {"id": "gen_zone2", "name": "DMR", "A": ["gen_ch1", "gen_ch3", "gen_ch4"], "B": []},
    ]
    assert generated["scanLists"] == []


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (("color_code: 1, ", ""), "DMR channel 'DMR Simplex' needs a color code and a time slot"),
        (("time_slot: 1, ", ""), "DMR channel 'DMR Simplex' needs a color code and a time slot"),
        (("mode: DMR", "mode: DMR, power: Turbo"), "power 'Turbo' is not one of Max, High, Mid, Low, Min"),
    ],
)
def test_a_channel_qdmr_cannot_carry_is_refused_by_name(tmp_path: Path, edit: tuple[str, str], message: str) -> None:
    selection, own, base = setup(tmp_path, SOURCES["own/simplex.yaml"].replace(*edit))
    with pytest.raises(qdmr.RenderError, match=re.escape(message)):
        qdmr.render(selection, own, base)
