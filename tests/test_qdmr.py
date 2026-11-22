from pathlib import Path
from typing import Any

import pytest

from radio_fleet import fleet, snapshot, sources
from radio_fleet.model import Channel, Ctcss, Dcs, Mode
from radio_fleet.render import qdmr
from radio_fleet.selection import Selection, Zone, select

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"

# Hand-made objects with values YAML 1.1 reads differently than qdmr (Off, No, 023), a group call
# contact for TG9 to reuse, a private call with a talkgroup's number, and generated objects of an
# earlier build.
BASE = """\
version: 0.12.0
settings: {defaultID: id1, power: High}
radioIDs:
  - dmr: {id: id1, name: XX0SYN, number: 9990001}
contacts:
  - dmr: {id: cont1, name: Local 9, ring: false, type: GroupCall, number: 9}
  - dmr: {id: cont2, name: Person, ring: false, type: PrivateCall, number: 232}
  - dmr: {id: gen_tg91, name: TG91, ring: false, type: GroupCall, number: 91}
groupLists:
  - {id: grp1, name: Local, contacts: [cont1]}
channels:
  - fm: {id: ch1, name: No, rxFrequency: 145.500 MHz, txFrequency: 145.500 MHz, vox: Off, rxTone: {dcs: 023}}
  - fm: {id: gen_ch9, name: Old, rxFrequency: 145.6 MHz, txFrequency: 145.6 MHz}
positioning:
  - dmr: {id: aprs1, name: DMR APRS, period: 300 s, contact: cont2}
zones:
  - {id: zone1, name: Hand, A: [ch1]}
  - {id: gen_zone7, name: Old, A: [gen_ch9]}
scanLists:
  - {id: gen_scan1, name: Old, channels: [gen_ch9]}
"""


def example_selection(radio_id: str = "d878uv2plus") -> tuple[Selection, sources.Sources]:
    own = sources.load(EXAMPLES / "sources")
    radio = fleet.load(EXAMPLES / "fleet.yaml", EXAMPLES).radios[radio_id]
    upstream = snapshot.read(snapshot.path_for(EXAMPLES / "snapshots", "oevsv-repeater-db"))
    return select(radio, upstream, own), own


def items(document: object, key: str) -> list[Any]:
    assert isinstance(document, dict)
    value = document[key]
    assert isinstance(value, list)
    return value


def object_id(item: dict[str, Any]) -> str:
    inner = next(iter(item.values())) if len(item) == 1 else item
    return str(inner["id"])


def test_rendering_twice_and_rendering_onto_the_output_give_the_same_file() -> None:
    selection, own = example_selection()
    first = qdmr.render(selection, own, BASE)
    assert qdmr.render(selection, own, BASE) == first
    assert qdmr.render(selection, own, first) == first


def test_hand_made_objects_and_settings_are_unchanged() -> None:
    selection, own = example_selection()
    out = qdmr.render(selection, own, BASE)
    base, rendered = qdmr.load(BASE), qdmr.load(out)
    assert isinstance(base, dict) and isinstance(rendered, dict)
    for key, value in base.items():
        if key in ("contacts", "groupLists", "channels", "zones", "scanLists"):
            hand_made = [item for item in value if not object_id(item).startswith("gen_")]
            assert [item for item in rendered[key] if not object_id(item).startswith("gen_")] == hand_made
        else:
            assert rendered[key] == value
    assert "name: 'No'" in out
    assert "vox: 'Off'" in out
    assert "dcs: '023'" in out
    assert "rxFrequency: 145.500 MHz" in out


def test_a_rebuild_replaces_exactly_the_generated_objects() -> None:
    selection, own = example_selection()
    rendered = qdmr.load(qdmr.render(selection, own, BASE))
    ids = {key: [object_id(item) for item in items(rendered, key)] for key in ("contacts", "channels", "zones")}
    assert ids["contacts"] == ["cont1", "cont2", "gen_tg99", "gen_tg232"]
    assert ids["channels"] == ["ch1", *(f"gen_ch{i}" for i in range(1, len(selection.channels) + 1))]
    assert ids["zones"] == ["zone1", *(f"gen_zone{i}" for i in range(1, len(selection.zones) + 1))]
    assert items(rendered, "scanLists") == []


def test_an_existing_group_call_contact_with_the_same_number_is_reused() -> None:
    selection, own = example_selection()
    rendered = qdmr.load(qdmr.render(selection, own, BASE))
    channels = {item["dmr"]["name"]: item["dmr"] for item in items(rendered, "channels") if "dmr" in item}
    assert channels["XX1BB 2 TG9"]["contact"] == "cont1"
    assert channels["XX1BB 1 TG232"]["contact"] == "gen_tg232"
    group_lists = {group["name"]: group for group in items(rendered, "groupLists")}
    assert group_lists["Austria"] == {"id": "gen_grp1", "name": "Austria", "contacts": ["gen_tg232", "cont1"]}


def render_channels(*channels: Channel) -> list[dict[str, Any]]:
    selection, own = example_selection()
    zone = Zone("All", channels)
    rendered = qdmr.load(qdmr.render(Selection(selection.radio, channels, (zone,), (), ()), own, BASE))
    assert items(rendered, "zones")[-1] == {
        "id": "gen_zone1",
        "name": "All",
        "A": ["gen_ch1", "gen_ch2"][: len(channels)],
    }
    return [item for item in items(rendered, "channels") if object_id(item).startswith("gen_")]


def test_fm_and_dmr_channels_carry_their_fields() -> None:
    fm = Channel("XX0FM", 145_600_000, 145_000_000, Mode.FM, tone_tx=Ctcss(88.5), tone_rx=Dcs(23), bandwidth_hz=12_500)
    dmr = Channel(
        "XX0DM TS2", 438_962_500, 431_462_500, Mode.DMR, color_code=1, time_slot=2, tx_talkgroup="TG91", power="Low"
    )
    assert render_channels(fm, dmr) == [
        {
            "fm": {
                "id": "gen_ch1",
                "name": "XX0FM",
                "rxFrequency": "145.6 MHz",
                "txFrequency": "145 MHz",
                "bandwidth": "Narrow",
                "rxTone": {"dcs": "023N"},
                "txTone": {"ctcss": "88.5 Hz"},
            }
        },
        {
            "dmr": {
                "id": "gen_ch2",
                "name": "XX0DM TS2",
                "rxFrequency": "438.9625 MHz",
                "txFrequency": "431.4625 MHz",
                "power": "Low",
                "colorCode": 1,
                "timeSlot": "TS2",
                "contact": "gen_tg91",
            }
        },
    ]


@pytest.mark.parametrize(
    ("channel", "message"),
    [
        (Channel("XX0FM", 145_600_000, 145_000_000, Mode.FM, power="5W"), "power '5W' is not one of Max, High"),
        (Channel("XX0YS", 145_600_000, 145_000_000, Mode.C4FM), "qdmr carries FM and DMR, not C4FM"),
    ],
)
def test_a_channel_qdmr_cannot_carry_is_refused(channel: Channel, message: str) -> None:
    with pytest.raises(qdmr.RenderError, match=message):
        render_channels(channel)


@pytest.mark.parametrize(
    ("base", "message"), [("channels: {name: Hand}\n", "not a qdmr codeplug"), ("channels: [\n", "not valid YAML")]
)
def test_a_base_that_is_not_a_codeplug_is_refused(base: str, message: str) -> None:
    selection, own = example_selection()
    with pytest.raises(qdmr.RenderError, match=message):
        qdmr.render(selection, own, base)
