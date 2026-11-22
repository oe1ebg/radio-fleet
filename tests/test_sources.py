import json
from pathlib import Path

import pytest

from radio_fleet import sources
from radio_fleet.config import ConfigError
from radio_fleet.model import Channel, Ctcss, Dcs, Mode

TALKGROUPS = """
talkgroups: {TG1: 1, TG2: 2}
rx_group_lists: {Both: [TG1, TG2]}
"""
TEMPLATES = """
templates:
  standard:
    - {name: TS1 TG1, time_slot: 1, tx_talkgroup: TG1, rx_group_list: Both}
    - {name: TS2 TG2, time_slot: 2, tx_talkgroup: TG2}
"""


def write(directory: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        (directory / name).parent.mkdir(parents=True, exist_ok=True)
        (directory / name).write_text(text)
    return directory


def test_an_override_without_a_reason_is_refused(tmp_path: Path) -> None:
    write(tmp_path, {"overrides.yaml": "overrides:\n  - {callsign: XX0FM, set: {power: Low}}\n"})
    with pytest.raises(ConfigError, match=r"overrides\.yaml: overrides\[0\]: 'reason' is required"):
        sources.load(tmp_path)


def test_an_override_changes_the_channels_of_its_callsign_and_mode(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "overrides.yaml": """
overrides:
  - {callsign: XX0MM, mode: FM, reason: list has the old tone, set: {tone_tx: {ctcss: 77.0}, tx: 438.0}}
"""
        },
    )
    fm = Channel("XX0MM", 430_400_000, 438_000_000, Mode.FM, tone_tx=Ctcss(88.5))
    dmr = Channel("XX0MM", 430_400_000, 438_000_000, Mode.DMR)
    other = Channel("XX0FM", 145_600_000, 145_000_000, Mode.FM)
    (override,) = sources.load(tmp_path).overrides
    channels, applied = sources.apply_overrides([fm, dmr, other], [override])
    assert channels == [Channel("XX0MM", 430_400_000, 438_000_000, Mode.FM, tone_tx=Ctcss(77.0)), dmr, other]
    assert [(a.channel, a.mode, a.override.reason) for a in applied] == [("XX0MM", Mode.FM, "list has the old tone")]


def test_a_dmr_repeater_expands_to_the_template_channels(tmp_path: Path) -> None:
    write(tmp_path, {"talkgroups.yaml": TALKGROUPS, "dmr_templates.yaml": TEMPLATES})
    template = sources.load(tmp_path).dmr_templates["standard"]
    repeater = Channel("XX0DM", 438_962_500, 431_462_500, Mode.DMR, color_code=1, source="synthetic-db")
    fm = Channel("XX0FM", 145_600_000, 145_000_000, Mode.FM)
    assert sources.expand_dmr([repeater, fm], template) == [
        Channel(
            "XX0DM TS1 TG1",
            438_962_500,
            431_462_500,
            Mode.DMR,
            color_code=1,
            time_slot=1,
            tx_talkgroup="TG1",
            rx_group_list="Both",
            source="synthetic-db",
        ),
        Channel(
            "XX0DM TS2 TG2",
            438_962_500,
            431_462_500,
            Mode.DMR,
            color_code=1,
            time_slot=2,
            tx_talkgroup="TG2",
            source="synthetic-db",
        ),
        fm,
    ]


def test_an_own_list_reads_into_channels_with_the_list_tags(tmp_path: Path) -> None:
    own = """
name: synthetic
tags: [own]
channels:
  - {name: S1, rx: 145.5125, mode: FM, tone_tx: {dcs: 23}, bandwidth: 12.5, tags: [quiet]}
  - {name: D1, rx: 433.4, tx: 433.45, mode: DMR, color_code: 1, time_slot: 2, tx_talkgroup: TG1, rx_group_list: Both}
"""
    write(tmp_path, {"talkgroups.yaml": TALKGROUPS, "own/synthetic.yaml": own})
    s1, d1 = sources.load(tmp_path).own_lists["synthetic"].channels
    assert (s1.rx_hz, s1.tx_hz, s1.tone_tx, s1.bandwidth_hz, s1.tags, s1.source) == (
        145_512_500,
        145_512_500,
        Dcs(23),
        12_500,
        ("own", "quiet"),
        "synthetic",
    )
    assert (d1.tx_hz, d1.time_slot, d1.tx_talkgroup, d1.rx_group_list) == (433_450_000, 2, "TG1", "Both")


EVERY_KEY = {
    "name": "D1",
    "rx": 433.4,
    "tx": 433.45,
    "mode": "DMR",
    "tone_tx": {"ctcss": 77.0},
    "tone_rx": {"dcs": 23},
    "bandwidth": 12.5,
    "color_code": 1,
    "time_slot": 2,
    "tx_talkgroup": "TG1",
    "rx_group_list": "Both",
    "power": "Low",
    "tags": ["quiet"],
}


def test_every_channel_key_is_read_into_its_field(tmp_path: Path) -> None:
    assert set(EVERY_KEY) == set(sources._CHANNEL_KEYS)
    write(tmp_path, {"talkgroups.yaml": TALKGROUPS, "own/a.yaml": json.dumps({"name": "a", "channels": [EVERY_KEY]})})
    (channel,) = sources.load(tmp_path).own_lists["a"].channels
    assert channel == Channel(
        "D1",
        433_400_000,
        433_450_000,
        Mode.DMR,
        tone_tx=Ctcss(77.0),
        tone_rx=Dcs(23),
        bandwidth_hz=12_500,
        color_code=1,
        time_slot=2,
        tx_talkgroup="TG1",
        rx_group_list="Both",
        power="Low",
        tags=("quiet",),
        source="a",
    )


@pytest.mark.parametrize(
    ("files", "message"),
    [
        ({"own/a.yaml": "name: a\nchannels: [{name: X, rx: 145.5, mode: DMR, tx_talkgroup: TG7}]\n"}, "'TG7'"),
        ({"own/a.yaml": "name: a\nchannels: [{name: X, rx: 145.5, mode: AM}]\n"}, "mode must be one of"),
        ({"own/a.yaml": "name: a\nchannels: [{name: X, rx: 145.5, mode: FM, shift: 1}]\n"}, "unknown key 'shift'"),
        ({"own/a.yaml": "name: b\nchannels: []\n"}, r"own/a\.yaml: name: the list in a\.yaml must be named 'a'"),
        ({"overrides.yaml": "overrides: [{callsign: X, reason: r, set: {mode: DMR}}]\n"}, "unknown key 'mode'"),
        ({"dmr_templates.yaml": "templates: {t: [{name: A, time_slot: 3, tx_talkgroup: TG1}]}\n"}, "from 1 to 2"),
    ],
)
def test_invalid_sources_are_refused_with_their_place(tmp_path: Path, files: dict[str, str], message: str) -> None:
    write(tmp_path, {"talkgroups.yaml": TALKGROUPS, **files})
    with pytest.raises(ConfigError, match=message):
        sources.load(tmp_path)
