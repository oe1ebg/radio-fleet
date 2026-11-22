from pathlib import Path
from typing import Any

import pytest

from radio_fleet import fleet, snapshot, sources
from radio_fleet.model import Channel, Ctcss, Dcs, Mode, Power
from radio_fleet.render import qdmr
from radio_fleet.selection import Group, Selection, select

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"

# Hand-made objects with values YAML 1.1 reads differently than qdmr (Off, No, 023), qdmr's own tags,
# a channel that the example's DMR zone and scan list take by name, a group call contact for TG9 to
# reuse, a private call with a talkgroup's number, and generated objects of an earlier build.
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
  - dmr: {id: ch2, name: Hotspot, rxFrequency: 433.6125 MHz, txFrequency: 433.6125 MHz, timeout: !default ""}
  - fm: {id: gen_ch9, name: Old, rxFrequency: 145.6 MHz, txFrequency: 145.6 MHz}
positioning:
  - dmr: {id: aprs1, name: DMR APRS, period: 300 s, contact: cont2}
zones:
  - {id: zone1, name: Hand, A: [ch1]}
  - {id: gen_zone7, name: Old, A: [gen_ch9]}
scanLists:
  - {id: scan1, name: Hand, primary: !selected "", channels: [ch1]}
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
    assert "timeout: !default ''" in out
    assert "primary: !selected ''" in out


def test_a_rebuild_replaces_exactly_the_generated_objects() -> None:
    selection, own = example_selection()
    rendered = qdmr.load(qdmr.render(selection, own, BASE))
    keys = ("contacts", "channels", "zones", "scanLists")
    ids = {key: [object_id(item) for item in items(rendered, key)] for key in keys}
    assert ids["contacts"] == ["cont1", "cont2", "gen_tg99", "gen_tg232"]
    assert ids["channels"] == ["ch1", "ch2", *(f"gen_ch{i}" for i in range(1, len(selection.channels) + 1))]
    assert ids["zones"] == ["zone1", *(f"gen_zone{i}" for i in range(1, len(selection.zones) + 1))]
    assert ids["scanLists"] == ["scan1", "gen_scan1", "gen_scan2"]


def test_scan_lists_take_hand_made_channels_by_name_and_channels_refer_to_their_first_scan_list() -> None:
    selection, own = example_selection()
    rendered = qdmr.load(qdmr.render(selection, own, BASE))
    names = {object_id(item): next(iter(item.values()))["name"] for item in items(rendered, "channels")}
    scan_lists = {scan["name"]: [names[i] for i in scan["channels"]] for scan in items(rendered, "scanLists")}
    assert scan_lists == {
        "Hand": ["No"],
        "FM": ["2m Call", "70cm Call", "PMR 1", "Freenet 1", "XX1AA", "XX1CC", "XX3DD"],
        "DMR": ["Hotspot", "DMR Simplex", "XX1BB 1 TG232", "XX1BB 2 TG9"],
    }
    zones = {zone["name"]: [names[i] for i in zone["A"]] for zone in items(rendered, "zones")}
    assert zones["DMR"] == ["Hotspot", "DMR Simplex", "XX1BB 1 TG232", "XX1BB 2 TG9"]
    refs = {inner["name"]: inner.get("scanListRef") for item in items(rendered, "channels") for inner in item.values()}
    assert refs == {
        "No": None,
        "Hotspot": None,
        "2m Call": "gen_scan1",
        "70cm Call": "gen_scan1",
        "PMR 1": "gen_scan1",
        "Freenet 1": "gen_scan1",
        "DMR Simplex": "gen_scan2",
        "XX1AA": "gen_scan1",
        "XX1BB 1 TG232": "gen_scan2",
        "XX1BB 2 TG9": "gen_scan2",
        "XX1CC": "gen_scan1",
        "XX3DD": "gen_scan1",
    }


@pytest.mark.parametrize(
    ("base", "message"),
    [
        (BASE.replace("name: Hotspot", "name: Hot"), "zone DMR: no hand-made channel named 'Hotspot' in the base"),
        (BASE.replace("name: No", "name: Hotspot"), "zone DMR: 2 hand-made channels named 'Hotspot' in the base"),
    ],
)
def test_a_base_channel_that_names_no_single_hand_made_channel_is_refused(base: str, message: str) -> None:
    selection, own = example_selection()
    with pytest.raises(qdmr.RenderError, match=message):
        qdmr.render(selection, own, base)


def test_an_existing_group_call_contact_with_the_same_number_is_reused() -> None:
    selection, own = example_selection()
    rendered = qdmr.load(qdmr.render(selection, own, BASE))
    channels = {item["dmr"]["name"]: item["dmr"] for item in items(rendered, "channels") if "dmr" in item}
    assert channels["XX1BB 2 TG9"]["contact"] == "cont1"
    assert channels["XX1BB 1 TG232"]["contact"] == "gen_tg232"
    group_lists = {group["name"]: group for group in items(rendered, "groupLists")}
    assert group_lists["Austria"] == {"id": "gen_grp1", "name": "Austria", "contacts": ["gen_tg232", "cont1"]}


def test_a_channel_in_two_scan_lists_refers_to_the_first() -> None:
    selection, own = example_selection()
    channels = selection.channels[:2]
    scan_lists = (Group("One", channels[1:]), Group("Both", channels))
    rendered = qdmr.load(qdmr.render(Selection(selection.radio, channels, (), scan_lists, (), ()), own, BASE))
    refs = [inner.get("scanListRef") for item in items(rendered, "channels") for inner in item.values()]
    assert refs[-2:] == ["gen_scan2", "gen_scan1"]


def render_channels(*channels: Channel) -> list[dict[str, Any]]:
    selection, own = example_selection()
    zone = Group("All", channels)
    rendered = qdmr.load(qdmr.render(Selection(selection.radio, channels, (zone,), (), (), ()), own, BASE))
    assert items(rendered, "zones")[-1] == {
        "id": "gen_zone1",
        "name": "All",
        "A": ["gen_ch1", "gen_ch2"][: len(channels)],
    }
    return [item for item in items(rendered, "channels") if object_id(item).startswith("gen_")]


def test_fm_and_dmr_channels_carry_their_fields() -> None:
    fm = Channel("XX0FM", 145_600_000, 145_000_000, Mode.FM, tone_tx=Ctcss(88.5), tone_rx=Dcs(23), bandwidth_hz=12_500)
    dmr = Channel(
        "XX0DM TS2", 438_962_500, 431_462_500, Mode.DMR, color_code=1, time_slot=2, tx_talkgroup="TG91", power=Power.LOW
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
