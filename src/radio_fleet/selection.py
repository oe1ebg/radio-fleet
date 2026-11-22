"""Selection (R4): the channels, zones and scan lists one radio carries, and every channel it cannot carry, with
the reason."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

from radio_fleet import geo
from radio_fleet.config import ConfigError
from radio_fleet.fleet import POWER_RENDERERS, RX_ONLY_RENDERERS, Capability, DistanceRegion, GroupRule, Radio, Region
from radio_fleet.model import Channel
from radio_fleet.sources import AppliedOverride, Override, Sources, TemplateChannel, apply_overrides, expand_dmr


@dataclass(frozen=True, slots=True)
class Drop:
    """A channel the radio does not carry, a channel a zone or scan list does not take, or a zone or scan list
    the radio does not get."""

    name: str
    reason: str


@dataclass(frozen=True, slots=True)
class Group:
    """A zone or a scan list. Its members are the hand-made channels of the base, by name, then `channels`."""

    name: str
    channels: tuple[Channel, ...]
    base_channels: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Selection:
    radio: Radio
    channels: tuple[Channel, ...]
    zones: tuple[Group, ...]
    scan_lists: tuple[Group, ...]
    drops: tuple[Drop, ...]
    overrides: tuple[AppliedOverride, ...]
    unmatched_overrides: tuple[Override, ...] = ()
    """The overrides for this radio that match no upstream channel, in or outside its region."""


def select(radio: Radio, upstream: Sequence[Channel], sources: Sources) -> Selection:
    """Own lists come first, in the profile's order, then the upstream channels of the region.

    The region applies to upstream channels only. It reads the callsign, and so do the overrides and the
    choice of the DMR template. An upstream channel takes its name from the profile before the overrides,
    which can set another one, and the DMR template appends to it.
    """
    capability = radio.capability

    def band_name(channel: Channel) -> str | None:
        band = capability.band_of(channel)
        return band.name if band is not None else None

    drops: list[Drop] = []
    regional: list[Channel] = []
    for channel in upstream:
        reason = _outside(radio.region, channel)
        if reason:
            drops.append(Drop(channel.name, reason))
        else:
            regional.append(_upstream_named(radio, channel, band_name(channel)))
    overrides = [override for override in sources.overrides if override.applies_to(radio.id)]
    unmatched = tuple(o for o in overrides if not any(o.matches(c, band_name(c)) for c in upstream))
    regional, applied = apply_overrides(regional, overrides, band_name)

    def template_of(channel: Channel) -> tuple[TemplateChannel, ...] | None:
        name = radio.template_for(channel.callsign)
        return sources.dmr_templates[name] if name is not None else None

    regional = expand_dmr(regional, template_of)
    own = [channel for name in radio.own_lists for channel in sources.own_lists[name].channels]

    kept: list[Channel] = []
    for channel in [*own, *regional]:
        reason = _unfit(radio, channel)
        if reason is None and len(kept) == capability.channels:
            reason = f"channel limit of {capability.channels} reached"
        if reason:
            drops.append(Drop(channel.name, reason))
        else:
            kept.append(_fitted(radio, channel))
    zones = _groups("zone", radio.zones, capability.zones, capability.zone_channels, capability, kept, drops)
    scan_lists = _groups(
        "scan list", radio.scan_lists, capability.scan_lists, capability.scan_list_channels, capability, kept, drops
    )
    return Selection(radio, tuple(kept), zones, scan_lists, tuple(drops), tuple(applied), unmatched)


def _outside(region: Region, channel: Channel) -> str | None:
    callsign = channel.callsign or ""
    if callsign in region.exclude:
        return f"excluded: {region.exclude[callsign]}"
    area = region.area_of(channel.mode)
    if isinstance(area, DistanceRegion):
        if channel.position is None:
            return "no position to place it in the region"
        km = geo.distance_km(area.centre, channel.position)
        return f"{km:.0f} km from {area.locator}, beyond {area.max_km:g} km" if km > area.max_km else None
    if callsign.startswith(area.prefixes):
        return None
    return f"callsign outside the region prefixes {', '.join(area.prefixes)}"


def _upstream_named(radio: Radio, channel: Channel, band: str | None) -> Channel:
    name = radio.upstream_name.format(callsign=channel.callsign or "", band=band or "", site=channel.site or "")
    return replace(channel, name=" ".join(name.split()) or channel.name)


def _unfit(radio: Radio, channel: Channel) -> str | None:
    capability = radio.capability
    if channel.mode not in capability.modes:
        return f"mode {channel.mode} not supported"
    if capability.band_of(channel) is None:
        return f"RX {mhz(channel.rx_hz)} MHz outside the RX bands"
    if channel.rx_only:
        if radio.renderer not in RX_ONLY_RENDERERS:
            return f"receive-only, and the {radio.renderer} renderer cannot write a channel that never transmits"
        return None
    if not any(band.transmits(channel.tx_hz) for band in capability.bands):
        return f"TX {mhz(channel.tx_hz)} MHz outside the TX bands"
    return None


def _fitted(radio: Radio, channel: Channel) -> Channel:
    """The channel as the radio holds it: its name rewritten and cut, the profile's power level when it has
    none, and a receive-only channel's TX frequency at its RX frequency."""
    name = channel.name
    for old, new in radio.name_replacements:
        name = name.replace(old, new)
    name = name[: radio.capability.name_length].rstrip()
    if channel.power is not None and radio.fixed_power is not None:
        raise ConfigError(
            f"radios.{radio.id}.power: {radio.fixed_power!r} is the power of every channel, but channel "
            f"{channel.name!r} from {channel.source} sets the level {channel.power}; make power a level and map "
            "the levels in power_levels"
        )
    power = channel.power if channel.power is not None else radio.power
    if power is not None and radio.renderer in POWER_RENDERERS and radio.power_value(power) is None:
        raise ConfigError(
            f"radios.{radio.id}.power_levels: no value for the power {power} of channel {channel.name!r} "
            f"from {channel.source}"
        )
    tx_hz = channel.rx_hz if channel.rx_only else channel.tx_hz
    return replace(channel, name=name, power=power, tx_hz=tx_hz)


def _groups(
    kind: str,
    rules: Sequence[GroupRule],
    limit: int | None,
    member_limit: int | None,
    capability: Capability,
    channels: Sequence[Channel],
    drops: list[Drop],
) -> tuple[Group, ...]:
    """The zones or scan lists of the rules; a limit of `None` is no limit."""
    groups: list[Group] = []
    for rule in rules:
        members = [channel for channel in channels if rule.matches(channel, capability.band_of(channel))]
        if not members and not rule.base_channels:
            drops.append(Drop(f"{kind} {rule.name}", "matches no channel"))
            continue
        if len(groups) == limit:
            drops.append(Drop(f"{kind} {rule.name}", f"{kind} limit of {limit} reached"))
            continue
        base, generated = list(rule.base_channels), [channel.name for channel in members]
        if member_limit is not None:
            reason = f"not in {kind} {rule.name}: it holds {member_limit} channels at most"
            drops.extend(Drop(name, reason) for name in [*base, *generated][member_limit:])
            base, members = base[:member_limit], members[: max(member_limit - len(base), 0)]
        groups.append(Group(rule.name, tuple(members), tuple(base)))
    return tuple(groups)


def mhz(hz: int) -> str:
    return f"{hz / 1_000_000:.5f}"
