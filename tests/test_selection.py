from dataclasses import replace
from pathlib import Path

import pytest

from radio_fleet import fleet, geo, sources
from radio_fleet.config import ConfigError
from radio_fleet.model import Channel, Ctcss, Mode, Position, Power
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
    power_levels: {Low: 1W}
    zones:
      - {name: Own, source: synthetic}
      - {name: XX1, channel: ["XX1F*", "XX1?Z"]}
"""

NEAR, FAR = Position(0.5, 1.0), Position(1.5, 2.0)
UPSTREAM = [
    replace(channel, callsign=channel.name)
    for channel in (
        Channel("XX1FM", 145_600_000, 145_000_000, Mode.FM, tone_tx=Ctcss(88.5), source="synthetic-db", position=NEAR),
        Channel("XX1DM", 438_962_500, 431_462_500, Mode.DMR, color_code=1, source="synthetic-db", position=NEAR),
        Channel("XX2FM", 145_700_000, 145_100_000, Mode.FM, source="synthetic-db", position=FAR),
        Channel("XX1NP", 145_650_000, 145_050_000, Mode.FM, source="synthetic-db"),
        Channel("XX1TX", 439_000_000, 445_000_000, Mode.FM, source="synthetic-db", position=NEAR),
        Channel("XX1C4", 145_612_500, 145_012_500, Mode.C4FM, source="synthetic-db", position=NEAR),
        Channel("XX1ZZ", 145_750_000, 145_150_000, Mode.FM, source="synthetic-db", position=NEAR),
    )
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


STEP = """
sources: [synthetic-db]
radios:
  qdmr:
    model: Synthetic qdmr radio
    renderer: qdmr
    capability: &capability
      bands:
        - {name: 2m, rx: [136, 174], tx: [144, 146]}
        - {name: 70cm, rx: [400, 480], tx: [430, 440]}
      modes: [FM, DMR]
      channels: 20
      name_length: 16
    region:
      locator: JJ00mm
      max_km: 50
      modes: {DMR: {prefixes: [XX1]}}
      exclude: {XX1EX: synthetic exclusion}
    own_lists: [listen]
    dmr_template: standard
    dmr_templates: {XX1D: other, XX1DX: exact}
    power: High
    power_levels: {High: Mid}
    naming: {upstream: "{callsign} {band}"}
  chirp:
    model: Synthetic CHIRP radio
    renderer: chirp
    capability: *capability
    region: {prefixes: [XX1]}
    own_lists: [listen]
    power: High
    power_levels: {High: 5W, Low: 1W}
"""
STEP_SOURCES = {
    "talkgroups.yaml": "talkgroups: {TG1: 1, TG2: 2, TG3: 3}\n",
    "dmr_templates.yaml": """
templates:
  standard: [{name: S, time_slot: 1, tx_talkgroup: TG1}]
  other: [{name: O, time_slot: 2, tx_talkgroup: TG2}]
  exact: [{name: E, time_slot: 1, tx_talkgroup: TG3}]
""",
    "own/listen.yaml": "name: listen\nchannels: [{name: Freenet, rx: 149.025, mode: FM, rx_only: true}]\n",
    "overrides.yaml": """
overrides:
  - {callsign: XX1AB, band: 70cm, reason: 70cm tone, set: {tone_tx: {ctcss: 77.0}}, clear: [tone_rx]}
  - {callsign: XX1AB, radios: chirp, reason: low power on the CHIRP radio, set: {power: Low}}
  - {callsign: XX1GONE, mode: FM, reason: stale, clear: tone_tx}
""",
}
STEP_UPSTREAM = [
    replace(channel, callsign=channel.name, source="synthetic-db", position=channel.position or NEAR)
    for channel in (
        Channel("XX1AB", 145_600_000, 145_000_000, Mode.FM, tone_rx=Ctcss(88.5)),
        Channel("XX1AB", 438_650_000, 431_050_000, Mode.FM, tone_rx=Ctcss(88.5)),
        Channel("XX1EX", 145_650_000, 145_050_000, Mode.FM),
        Channel("XX1DA", 438_900_000, 431_300_000, Mode.DMR, position=FAR),
        Channel("XX1DX", 438_925_000, 431_325_000, Mode.DMR),
        Channel("XX2DM", 438_950_000, 431_350_000, Mode.DMR),
        Channel("XX1FA", 145_700_000, 145_100_000, Mode.FM, position=FAR),
    )
]


def step(tmp_path: Path, fleet_text: str = STEP) -> tuple[fleet.Fleet, sources.Sources]:
    for name, text in STEP_SOURCES.items():
        (tmp_path / "sources" / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "sources" / name).write_text(text)
    (tmp_path / "fleet.yaml").write_text(fleet_text)
    the_fleet, own = fleet.load(tmp_path / "fleet.yaml", tmp_path), sources.load(tmp_path / "sources")
    the_fleet.check_references(own)
    return the_fleet, own


def test_channel_data_of_step_8b_reaches_the_selection(tmp_path: Path) -> None:
    the_fleet, own = step(tmp_path)
    radio = the_fleet.radios["qdmr"]
    selection = select(radio, STEP_UPSTREAM, own)
    described = [
        (c.name, c.tx_hz, c.rx_only, c.tone_tx, c.tone_rx, c.tx_talkgroup, radio.power_value(c.power))
        for c in selection.channels
    ]
    assert described == [
        ("Freenet", 149_025_000, True, None, None, None, "Mid"),
        ("XX1AB 2m", 145_000_000, False, None, Ctcss(88.5), None, "Mid"),
        ("XX1AB 70cm", 431_050_000, False, Ctcss(77.0), None, None, "Mid"),
        ("XX1DA 70cm O", 431_300_000, False, None, None, "TG2", "Mid"),
        ("XX1DX 70cm E", 431_325_000, False, None, None, "TG3", "Mid"),
    ]
    far_km = geo.distance_km(geo.locator_position("JJ00mm"), FAR)
    assert list(selection.drops) == [
        Drop("XX1EX", "excluded: synthetic exclusion"),
        Drop("XX2DM", "callsign outside the region prefixes XX1"),
        Drop("XX1FA", f"{far_km:.0f} km from JJ00mm, beyond 50 km"),
    ]
    assert [(a.channel, a.band, a.override.reason) for a in selection.overrides] == [("XX1AB", "70cm", "70cm tone")]
    assert [o.reason for o in selection.unmatched_overrides] == ["stale"]

    chirp = select(the_fleet.radios["chirp"], STEP_UPSTREAM, own)
    assert [(c.name, c.power) for c in chirp.channels if c.callsign == "XX1AB"] == [
        ("XX1AB", Power.LOW),
        ("XX1AB", Power.LOW),
    ]


@pytest.mark.parametrize(
    ("renderer", "kept"),
    [("qdmr", True), ("chirp", True), ("ft5d", False), ("jayt", False), ("hytera", False)],
)
def test_a_receive_only_channel_outside_the_tx_bands_is_kept_where_the_renderer_can_write_it(
    tmp_path: Path, renderer: str, kept: bool
) -> None:
    text = STEP.replace("renderer: chirp", f"renderer: {renderer}")
    if renderer != "chirp":
        text = text.replace("    power: High\n    power_levels: {High: 5W, Low: 1W}\n", "")
    the_fleet, own = step(tmp_path, text)
    selection = select(the_fleet.radios["chirp"], [], own)
    if kept:
        assert [(c.name, c.rx_only, c.tx_hz) for c in selection.channels] == [("Freenet", True, 149_025_000)]
    else:
        reason = f"receive-only, and the {renderer} renderer cannot write a channel that never transmits"
        assert list(selection.drops) == [Drop("Freenet", reason)]


def test_a_power_level_the_profile_does_not_map_fails_with_the_profile_and_the_list(tmp_path: Path) -> None:
    the_fleet, own = step(
        tmp_path, STEP.replace("    power: High\n    power_levels: {High: Mid}\n", "    power: Low\n")
    )
    assert the_fleet.radios["qdmr"].power_value(Power.LOW) == "Low"
    the_fleet, own = step(tmp_path, STEP.replace("{High: 5W, Low: 1W}", "{Low: 1W}"))
    with pytest.raises(
        ConfigError, match=r"radios\.chirp\.power_levels: no value for the power High of channel 'Freenet' from listen"
    ):
        select(the_fleet.radios["chirp"], [], own)


def test_a_power_that_is_not_a_level_is_the_radio_value_of_every_level(tmp_path: Path) -> None:
    the_fleet, own = step(
        tmp_path, STEP.replace("    power: High\n    power_levels: {High: 5W, Low: 1W}\n", "    power: 5W\n")
    )
    chirp = the_fleet.radios["chirp"]
    assert (chirp.power, [chirp.power_value(level) for level in Power]) == (Power.HIGH, ["5W"] * 5)
    kept = select(chirp, [c for c in STEP_UPSTREAM if c.callsign != "XX1AB"], own).channels
    assert {chirp.power_value(channel.power) for channel in kept} == {"5W"}


@pytest.mark.parametrize(("renderer", "fixed"), [("chirp", "5W"), ("hytera", "Middle"), ("jayt", "LOW2")])
def test_a_power_that_is_not_a_level_refuses_a_channel_with_its_own_level(
    tmp_path: Path, renderer: str, fixed: str
) -> None:
    the_fleet, own = step(
        tmp_path,
        STEP.replace("renderer: chirp", f"renderer: {renderer}").replace(
            "    power: High\n    power_levels: {High: 5W, Low: 1W}\n", f"    power: {fixed}\n"
        ),
    )
    with pytest.raises(
        ConfigError,
        match=rf"radios\.chirp\.power: '{fixed}' is the power of every channel, but channel 'XX1AB' from "
        r"synthetic-db sets the level Low; make power a level",
    ):
        select(the_fleet.radios["chirp"], STEP_UPSTREAM, own)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            ("power_levels: {High: 5W, Low: 1W}", "power_levels: {High: 5W, Low: High}"),
            r"radios\.chirp\.power_levels\.Low: the chirp renderer takes the power as watts",
        ),
        (
            ("power_levels: {High: Mid}", "power_levels: {Top: Mid}"),
            r"radios\.qdmr\.power_levels\.Top: power levels are Max",
        ),
        (
            ("power: High\n    power_levels: {High: Mid}", "power: Mid\n    power_levels: {High: 5W}"),
            r"radios\.qdmr\.power_levels\.High: the qdmr renderer takes the power as Max",
        ),
        (
            ("power: High\n    power_levels: {High: 5W, Low: 1W}", "power: 5W\n    power_levels: {Low: 1W}"),
            r"radios\.chirp\.power: with power_levels, power is a level",
        ),
        (("renderer: chirp", "renderer: ft5d"), r"radios\.chirp\.power_levels: the ft5d renderer writes no power"),
        (
            ("exclude: {XX1EX: synthetic exclusion}", "exclude: {XX1EX: ''}"),
            r"radios\.qdmr\.region\.exclude\.XX1EX: expected a non-empty string",
        ),
        (("{DMR: {prefixes: [XX1]}}", "{AM: {prefixes: [XX1]}}"), r"radios\.qdmr\.region\.modes\.AM: modes are FM"),
        (
            ("{DMR: {prefixes: [XX1]}}", "{DMR: {prefixes: [XX1], max_km: 5}}"),
            r"radios\.qdmr\.region\.modes\.DMR: a region is either",
        ),
        (
            ('"{callsign} {band}"', '"{callsign} {freq}"'),
            r"radios\.qdmr\.naming\.upstream: a name takes only the fields \{callsign\}, \{band\}, \{site\}, "
            r"not \{freq\}",
        ),
    ],
)
def test_invalid_step_8b_keys_are_refused_with_their_place(
    tmp_path: Path, change: tuple[str, str], message: str
) -> None:
    assert change[0] in STEP
    (tmp_path / "fleet.yaml").write_text(STEP.replace(*change))
    with pytest.raises(ConfigError, match=message):
        fleet.load(tmp_path / "fleet.yaml", tmp_path)


@pytest.mark.parametrize(
    ("file", "change", "message"),
    [
        (
            "fleet.yaml",
            ("{XX1D: other,", "{XX1D: missing,"),
            r"radios\.qdmr\.dmr_templates\.XX1D: no template 'missing'",
        ),
        (
            "sources/overrides.yaml",
            ("radios: chirp", "radios: [chirp, nothing]"),
            r"overrides\.yaml: overrides\[1\]\.radios: no radio 'nothing' in \S*fleet\.yaml",
        ),
    ],
)
def test_a_template_or_radio_that_is_not_there_is_refused(
    tmp_path: Path, file: str, change: tuple[str, str], message: str
) -> None:
    step(tmp_path)
    path = tmp_path / file
    path.write_text(path.read_text().replace(*change))
    with pytest.raises(ConfigError, match=message):
        fleet.load(tmp_path / "fleet.yaml", tmp_path).check_references(sources.load(tmp_path / "sources"))


def test_the_site_can_name_an_upstream_channel(tmp_path: Path) -> None:
    the_fleet, own = step(tmp_path, STEP.replace('"{callsign} {band}"', '"{site} {band}"'))
    channel = replace(STEP_UPSTREAM[0], site="Hill")
    assert [c.name for c in select(the_fleet.radios["qdmr"], [channel], own).channels] == ["Freenet", "Hill 2m"]
