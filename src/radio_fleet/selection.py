"""Selection (R4): the channels and zones one radio carries, and every channel it cannot carry, with the reason."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

from radio_fleet import geo
from radio_fleet.fleet import Capability, DistanceRegion, Radio, Region
from radio_fleet.model import Channel
from radio_fleet.sources import AppliedOverride, Sources, apply_overrides, expand_dmr


@dataclass(frozen=True, slots=True)
class Drop:
    """A channel the radio does not carry, a channel a zone does not take, or a zone the radio does not get."""

    name: str
    reason: str


@dataclass(frozen=True, slots=True)
class Zone:
    name: str
    channels: tuple[Channel, ...]


@dataclass(frozen=True, slots=True)
class Selection:
    radio: Radio
    channels: tuple[Channel, ...]
    zones: tuple[Zone, ...]
    drops: tuple[Drop, ...]
    overrides: tuple[AppliedOverride, ...]


def select(radio: Radio, upstream: Sequence[Channel], sources: Sources) -> Selection:
    """Own lists come first, in the profile's order, then the upstream channels of the region.

    The region applies to upstream channels only, before any override, so it reads the callsign.
    """
    drops: list[Drop] = []
    regional: list[Channel] = []
    for channel in upstream:
        reason = _outside(radio.region, channel)
        if reason:
            drops.append(Drop(channel.name, reason))
        else:
            regional.append(channel)
    regional, applied = apply_overrides(regional, sources.overrides)
    if radio.dmr_template is not None:
        regional = expand_dmr(regional, sources.dmr_templates[radio.dmr_template])
    own = [channel for name in radio.own_lists for channel in sources.own_lists[name].channels]

    capability = radio.capability
    kept: list[Channel] = []
    for channel in [*own, *regional]:
        reason = _unfit(capability, channel)
        if reason is None and len(kept) == capability.channels:
            reason = f"channel limit of {capability.channels} reached"
        if reason:
            drops.append(Drop(channel.name, reason))
        else:
            kept.append(_named(radio, channel))
    return Selection(radio, tuple(kept), _zones(radio, kept, drops), tuple(drops), tuple(applied))


def _outside(region: Region, channel: Channel) -> str | None:
    if isinstance(region, DistanceRegion):
        if channel.position is None:
            return "no position to place it in the region"
        km = geo.distance_km(region.centre, channel.position)
        return f"{km:.0f} km from {region.locator}, beyond {region.max_km:g} km" if km > region.max_km else None
    if channel.name.startswith(region.prefixes):
        return None
    return f"callsign outside the region prefixes {', '.join(region.prefixes)}"


def _unfit(capability: Capability, channel: Channel) -> str | None:
    if channel.mode not in capability.modes:
        return f"mode {channel.mode} not supported"
    if capability.band_of(channel) is None:
        return f"RX {mhz(channel.rx_hz)} MHz outside the RX bands"
    if not any(band.transmits(channel.tx_hz) for band in capability.bands):
        return f"TX {mhz(channel.tx_hz)} MHz outside the TX bands"
    return None


def _named(radio: Radio, channel: Channel) -> Channel:
    name = channel.name
    for old, new in radio.name_replacements:
        name = name.replace(old, new)
    name = name[: radio.capability.name_length].rstrip()
    power = channel.power if channel.power is not None else radio.power
    return replace(channel, name=name, power=power)


def _zones(radio: Radio, channels: Sequence[Channel], drops: list[Drop]) -> tuple[Zone, ...]:
    capability = radio.capability
    zones: list[Zone] = []
    for rule in radio.zones:
        members = [channel for channel in channels if rule.matches(channel, capability.band_of(channel))]
        if not members:
            drops.append(Drop(f"zone {rule.name}", "matches no channel"))
            continue
        if len(zones) == capability.zones:
            drops.append(Drop(f"zone {rule.name}", f"zone limit of {capability.zones} reached"))
            continue
        limit = capability.zone_channels
        drops.extend(
            Drop(c.name, f"not in zone {rule.name}: it holds {limit} channels at most") for c in members[limit:]
        )
        zones.append(Zone(rule.name, tuple(members[:limit])))
    return tuple(zones)


def mhz(hz: int) -> str:
    return f"{hz / 1_000_000:.5f}"
