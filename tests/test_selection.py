from pathlib import Path

import pytest

from radio_fleet import fleet, geo, sources
from radio_fleet.config import ConfigError
from radio_fleet.model import Channel, Ctcss, Mode, Position
from radio_fleet.selection import Drop, select

SOURCES = {
    "talkgroups.yaml": "talkgroups: {TG1: 1, TG2: 2}\n",
    "dmr_templates.yaml": """
templates:
  standard:
    - {name: TS1 TG1, time_slot: 1, tx_talkgroup: TG1}
    - {name: TS2 TG2, time_slot: 2, tx_talkgroup: TG2}
""",
    "overrides.yaml": "overrides: [{callsign: XX1FM, reason: synthetic reason, set: {power: Low}}]\n",
    "own/synthetic.yaml": """
name: synthetic
channels:
  - {name: S1, rx: 145.5, mode: FM}
  - {name: S2, rx: 433.5, mode: FM}
""",
}

FLEET = """
sources: [synthetic-db]
radios:
  dual:
    model: Synthetic dual-band DMR
    renderer: qdmr
    capability:
      bands:
        - {name: 2m, rx: [136, 174], tx: [144, 146]}
        - {name: 70cm, rx: [400, 480], tx: [430, 440]}
      modes: [FM, DMR]
      channels: 5
      zones: 2
      zone_channels: 2
      scan_lists: 2
      scan_list_channels: 3
      name_length: 10
    region: {locator: JJ00mm, max_km: 50}
    own_lists: [synthetic]
    dmr_template: standard
    zones:
      - {name: FM, mode: FM}
      - {name: DMR, mode: DMR, band: 70cm}
      - {name: Empty, tag: nothing}
      - {name: Own, source: synthetic}
    scan_lists:
      - {name: Mixed, mode: FM, base_channel: [Hand 1, Hand 2]}
      - {name: Hand, base_channel: Hand 3}
      - {name: Empty, tag: nothing}
      - {name: DMR, mode: DMR}
    power: High
    naming: {replace: {" TS1 ": " 1 "}}
  mono:
    model: Synthetic 2m FM
    renderer: chirp
    capability:
      bands: [{name: 2m, rx: [136, 174], tx: [144, 146]}]
      modes: [FM]
      channels: 10
      zones: 2
      zone_channels: 3
      name_length: 6
    region: {prefixes: [XX1]}
    own_lists: [synthetic]
    zones:
      - {name: Own, source: synthetic}
      - {name: XX1, channel: ["XX1F*", "XX1?Z"]}
"""

NEAR, FAR = Position(0.5, 1.0), Position(1.5, 2.0)
UPSTREAM = [
    Channel("XX1FM", 145_600_000, 145_000_000, Mode.FM, tone_tx=Ctcss(88.5), source="synthetic-db", position=NEAR),
    Channel("XX1DM", 438_962_500, 431_462_500, Mode.DMR, color_code=1, source="synthetic-db", position=NEAR),
    Channel("XX2FM", 145_700_000, 145_100_000, Mode.FM, source="synthetic-db", position=FAR),
    Channel("XX1NP", 145_650_000, 145_050_000, Mode.FM, source="synthetic-db"),
    Channel("XX1TX", 439_000_000, 445_000_000, Mode.FM, source="synthetic-db", position=NEAR),
    Channel("XX1C4", 145_612_500, 145_012_500, Mode.C4FM, source="synthetic-db", position=NEAR),
    Channel("XX1ZZ", 145_750_000, 145_150_000, Mode.FM, source="synthetic-db", position=NEAR),
]


@pytest.fixture
def synthetic(tmp_path: Path) -> tuple[fleet.Fleet, sources.Sources]:
    for name, text in SOURCES.items():
        (tmp_path / "sources" / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "sources" / name).write_text(text)
    (tmp_path / "fleet.yaml").write_text(FLEET)
    the_fleet, own = fleet.load(tmp_path / "fleet.yaml", tmp_path), sources.load(tmp_path / "sources")
    the_fleet.check_references(own)
    return the_fleet, own


def test_selection_of_a_synthetic_fleet(synthetic: tuple[fleet.Fleet, sources.Sources]) -> None:
    the_fleet, own = synthetic
    dual = select(the_fleet.radios["dual"], UPSTREAM, own)
    assert [(c.name, c.mode, c.time_slot, c.tx_talkgroup, c.power) for c in dual.channels] == [
        ("S1", Mode.FM, None, None, "High"),
        ("S2", Mode.FM, None, None, "High"),
        ("XX1FM", Mode.FM, None, None, "Low"),
        ("XX1DM 1 TG", Mode.DMR, 1, "TG1", "High"),
        ("XX1DM TS2", Mode.DMR, 2, "TG2", "High"),
    ]
    assert [(z.name, [c.name for c in z.channels]) for z in dual.zones] == [
        ("FM", ["S1", "S2"]),
        ("DMR", ["XX1DM 1 TG", "XX1DM TS2"]),
    ]
    far_km = geo.distance_km(geo.locator_position("JJ00mm"), FAR)
    assert list(dual.drops) == [
        Drop("XX2FM", f"{far_km:.0f} km from JJ00mm, beyond 50 km"),
        Drop("XX1NP", "no position to place it in the region"),
        Drop("XX1TX", "TX 445.00000 MHz outside the TX bands"),
        Drop("XX1C4", "mode C4FM not supported"),
        Drop("XX1ZZ", "channel limit of 5 reached"),
        Drop("XX1FM", "not in zone FM: it holds 2 channels at most"),
        Drop("zone Empty", "matches no channel"),
        Drop("zone Own", "zone limit of 2 reached"),
        Drop("S2", "not in scan list Mixed: it holds 3 channels at most"),
        Drop("XX1FM", "not in scan list Mixed: it holds 3 channels at most"),
        Drop("scan list Empty", "matches no channel"),
        Drop("scan list DMR", "scan list limit of 2 reached"),
    ]
    assert [(s.name, s.base_channels, [c.name for c in s.channels]) for s in dual.scan_lists] == [
        ("Mixed", ("Hand 1", "Hand 2"), ["S1"]),
        ("Hand", ("Hand 3",), []),
    ]
    assert [(a.channel, a.override.reason) for a in dual.overrides] == [("XX1FM", "synthetic reason")]

    mono = select(the_fleet.radios["mono"], UPSTREAM, own)
    assert [(c.name, c.power) for c in mono.channels] == [
        ("S1", None),
        ("XX1FM", "Low"),
        ("XX1NP", None),
        ("XX1ZZ", None),
    ]
    assert [(z.name, [c.name for c in z.channels]) for z in mono.zones] == [
        ("Own", ["S1"]),
        ("XX1", ["XX1FM", "XX1ZZ"]),
    ]
    assert mono.scan_lists == ()
    assert list(mono.drops) == [
        Drop("XX2FM", "callsign outside the region prefixes XX1"),
        Drop("S2", "RX 433.50000 MHz outside the RX bands"),
        Drop("XX1DM", "mode DMR not supported"),
        Drop("XX1TX", "RX 439.00000 MHz outside the RX bands"),
        Drop("XX1C4", "mode C4FM not supported"),
    ]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            ("[synthetic]\n    dmr_template", "[missing]\n    dmr_template"),
            r"radios\.dual\.own_lists: no own list 'missing': no file \S*sources/own/missing\.yaml",
        ),
        (
            ("dmr_template: standard", "dmr_template: missing"),
            r"radios\.dual\.dmr_template: no template 'missing' in \S*sources/dmr_templates\.yaml",
        ),
        (
            ("renderer: qdmr\n", "renderer: qdmr\n    base: bases/missing.yaml\n"),
            r"radios\.dual\.base: no file \S*bases/missing\.yaml",
        ),
    ],
)
def test_a_profile_naming_a_missing_file_is_refused_with_the_file(
    tmp_path: Path, synthetic: tuple[fleet.Fleet, sources.Sources], change: tuple[str, str], message: str
) -> None:
    (tmp_path / "fleet.yaml").write_text(FLEET.replace(*change))
    with pytest.raises(ConfigError, match=message):
        fleet.load(tmp_path / "fleet.yaml", tmp_path).check_references(synthetic[1])


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (("{locator: JJ00mm, max_km: 50}", "{locator: ZZ99, max_km: 50}"), "radios.dual.region.locator"),
        (("{locator: JJ00mm, max_km: 50}", "{locator: JJ00mm}"), "either {locator, max_km} or {prefixes}"),
        (("band: 70cm", "band: 23cm"), "no band '23cm'"),
        (("renderer: qdmr", "renderer: cps"), "renderer must be one of"),
        (("rx: [400, 480]", "rx: [480, 400]"), r"\[low, high\]"),
        (
            (
                "{name: Own, source: synthetic}\n      - {name: XX1",
                "{name: Own, base_channel: Hand}\n      - {name: XX1",
            ),
            r"radios\.mono\.zones\S*base_channel: only the qdmr renderer takes base channels",
        ),
        (
            (
                "    zones:\n      - {name: Own, source: synthetic}\n      - {name: XX1",
                "    scan_lists:\n      - {name: XX1",
            ),
            r"radios\.mono\.scan_lists: only the qdmr renderer takes scan lists",
        ),
    ],
)
def test_an_invalid_fleet_file_is_refused_with_its_place(tmp_path: Path, change: tuple[str, str], message: str) -> None:
    (tmp_path / "fleet.yaml").write_text(FLEET.replace(*change))
    with pytest.raises(ConfigError, match=message):
        fleet.load(tmp_path / "fleet.yaml", tmp_path)


def test_a_profile_without_zone_or_scan_list_limits_keeps_all_its_zones_and_scan_lists(
    tmp_path: Path, synthetic: tuple[fleet.Fleet, sources.Sources]
) -> None:
    limits = "      zones: 2\n      zone_channels: 2\n      scan_lists: 2\n      scan_list_channels: 3\n"
    assert limits in FLEET
    (tmp_path / "fleet.yaml").write_text(FLEET.replace(limits, ""))
    dual = select(fleet.load(tmp_path / "fleet.yaml", tmp_path).radios["dual"], UPSTREAM, synthetic[1])
    assert [(z.name, len(z.channels)) for z in dual.zones] == [("FM", 3), ("DMR", 2), ("Own", 2)]
    assert [(s.name, len(s.base_channels) + len(s.channels)) for s in dual.scan_lists] == [
        ("Mixed", 5),
        ("Hand", 1),
        ("DMR", 2),
    ]
    group_drops = [
        d for d in dual.drops if d.name.startswith(("zone ", "scan list ")) or d.reason.startswith("not in ")
    ]
    assert group_drops == [
        Drop("zone Empty", "matches no channel"),
        Drop("scan list Empty", "matches no channel"),
    ]


def test_locator_centre_and_distance() -> None:
    centre = geo.locator_position("JJ00mm")
    assert (centre.lat, centre.lon) == pytest.approx((0.5 + 1 / 48, 1 + 1 / 24))
    assert geo.locator_position("JJ00") == Position(0.5, 1.0)
    assert geo.distance_km(Position(0, 0), Position(0, 1)) == pytest.approx(111.19, abs=0.01)


def test_base_channels_beyond_the_scan_list_member_limit_leave_no_room_for_generated_channels(
    tmp_path: Path, synthetic: tuple[fleet.Fleet, sources.Sources]
) -> None:
    (tmp_path / "fleet.yaml").write_text(FLEET.replace("scan_list_channels: 3", "scan_list_channels: 1"))
    dual = select(fleet.load(tmp_path / "fleet.yaml", tmp_path).radios["dual"], UPSTREAM, synthetic[1])
    mixed = dual.scan_lists[0]
    assert (mixed.name, mixed.base_channels, mixed.channels) == ("Mixed", ("Hand 1",), ())
    reason = "not in scan list Mixed: it holds 1 channels at most"
    assert [d.name for d in dual.drops if d.reason == reason] == ["Hand 2", "S1", "S2", "XX1FM"]
