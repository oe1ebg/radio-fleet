"""`fleet.yaml` (R4): the upstream sources and one profile per radio."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from fnmatch import fnmatchcase
from pathlib import Path

from radio_fleet import config, geo, hytera_tool
from radio_fleet.config import ConfigError, Node
from radio_fleet.model import Channel, Mode, Position
from radio_fleet.sources import MHZ, Sources, dmr_templates_path, own_list_path


class Renderer(StrEnum):
    QDMR = "qdmr"
    CHIRP = "chirp"
    FT5D = "ft5d"
    JAYT = "jayt"
    HYTERA = "hytera"


@dataclass(frozen=True, slots=True)
class Band:
    """RX and TX limits in Hz, both inclusive; a band without TX limits is receive-only."""

    name: str
    rx: tuple[int, int]
    tx: tuple[int, int] | None

    def receives(self, hz: int) -> bool:
        return self.rx[0] <= hz <= self.rx[1]

    def transmits(self, hz: int) -> bool:
        return self.tx is not None and self.tx[0] <= hz <= self.tx[1]


@dataclass(frozen=True, slots=True)
class Capability:
    """`None` is no limit."""

    bands: tuple[Band, ...]
    modes: frozenset[Mode]
    channels: int
    zones: int | None
    zone_channels: int | None
    scan_lists: int | None
    scan_list_channels: int | None
    name_length: int

    def band_of(self, channel: Channel) -> Band | None:
        return next((band for band in self.bands if band.receives(channel.rx_hz)), None)


@dataclass(frozen=True, slots=True)
class DistanceRegion:
    locator: str
    centre: Position
    max_km: float


@dataclass(frozen=True, slots=True)
class PrefixRegion:
    prefixes: tuple[str, ...]


Region = DistanceRegion | PrefixRegion


@dataclass(frozen=True, slots=True)
class GroupRule:
    """A zone (or bank) or a scan list and the channels it takes. Each criterion lists the values it accepts;
    a channel joins when it meets every criterion the rule has. `base_channels` names hand-made channels of
    the base that join first; a rule with base channels and no criterion takes no other channel."""

    name: str
    modes: frozenset[Mode] = frozenset()
    bands: frozenset[str] = frozenset()
    sources: frozenset[str] = frozenset()
    tags: frozenset[str] = frozenset()
    channels: tuple[str, ...] = ()
    base_channels: tuple[str, ...] = ()

    def matches(self, channel: Channel, band: Band | None) -> bool:
        if self.base_channels and not (self.modes or self.bands or self.sources or self.tags or self.channels):
            return False
        return (
            (not self.modes or channel.mode in self.modes)
            and (not self.bands or (band is not None and band.name in self.bands))
            and (not self.sources or channel.source in self.sources)
            and (not self.tags or not self.tags.isdisjoint(channel.tags))
            and (not self.channels or any(fnmatchcase(channel.name, glob) for glob in self.channels))
        )


@dataclass(frozen=True, slots=True)
class Radio:
    id: str
    model: str
    renderer: Renderer
    base: Path | None
    dmrconf_radio: str | None
    factory: Path | None
    capability: Capability
    region: Region
    own_lists: tuple[str, ...]
    dmr_template: str | None
    zones: tuple[GroupRule, ...]
    scan_lists: tuple[GroupRule, ...]
    power: str | None
    name_replacements: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class Tool:
    """An external tool's executable and the commit it was built from."""

    path: Path
    commit: str


@dataclass(frozen=True, slots=True)
class Commands:
    """The export and import command lines of a file tool, with `{name}` placeholders for its files."""

    export: tuple[str, ...]
    import_: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Fleet:
    file: str
    sources: tuple[str, ...]
    radios: Mapping[str, Radio]
    jayt: Tool | None = None
    hytera: Commands | None = None
    equipment: Path | None = None

    def check_references(self, sources: Sources) -> None:
        """Every file a profile names must exist: its own lists, its DMR template's file, its base and its
        factory image."""
        for radio in self.radios.values():
            place = f"{self.file}: radios.{radio.id}"
            for name in radio.own_lists:
                if name not in sources.own_lists:
                    path = own_list_path(sources.directory, name)
                    raise ConfigError(f"{place}.own_lists: no own list {name!r}: no file {path}")
            if radio.dmr_template is not None and radio.dmr_template not in sources.dmr_templates:
                path = dmr_templates_path(sources.directory)
                raise ConfigError(f"{place}.dmr_template: no template {radio.dmr_template!r} in {path}")
            for key, file in (("base", radio.base), ("factory", radio.factory)):
                if file is not None and not file.is_file():
                    raise ConfigError(f"{place}.{key}: no file {file}")


def load(path: Path, data_root: Path) -> Fleet:
    """Paths in the file, such as bases, are relative to the data root (R13), not to the file."""
    fields = config.load(path).fields(["sources", "radios"], ["tools", "equipment"])
    sources = fields["sources"].texts()
    if not sources:
        raise fields["sources"].error("name at least one source")
    radios = {radio_id: _radio(radio_id, node, data_root) for radio_id, node in fields["radios"].entries().items()}
    tools = fields["tools"].fields((), ["jayt", "hytera"]) if "tools" in fields else {}
    jayt = _tool(tools["jayt"], data_root) if "jayt" in tools else None
    hytera = _commands(tools["hytera"]) if "hytera" in tools else None
    equipment = data_root / fields["equipment"].text() if "equipment" in fields else None
    return Fleet(str(path), sources, radios, jayt, hytera, equipment)


_COMMIT = re.compile(r"[0-9a-f]{7,40}")


def _tool(node: Node, data_root: Path) -> Tool:
    fields = node.fields(["path", "commit"])
    commit = fields["commit"].text()
    if not _COMMIT.fullmatch(commit):
        raise fields["commit"].error("expected a git commit: 7 to 40 hex digits")
    # Absolute, so that a bare name such as `jayt` is the file in the data root and not a PATH lookup.
    return Tool((data_root / fields["path"].text()).absolute(), commit)


def _commands(node: Node) -> Commands:
    fields = node.fields(hytera_tool.FILES)
    return Commands(_command(fields["export"], "export"), _command(fields["import"], "import"))


def _command(node: Node, command: str) -> tuple[str, ...]:
    """A list of arguments that names exactly the command's files, each as `{name}`."""
    files = hytera_tool.FILES[command]
    argv = node.texts()
    named = {name for arg in argv for name in hytera_tool.PLACEHOLDER.findall(arg)}
    if not argv or named != set(files):
        placeholders = ", ".join(f"{{{name}}}" for name in files)
        raise node.error(f"expected a list of arguments with exactly the placeholders {placeholders}")
    return argv


def _radio(radio_id: str, node: Node, data_root: Path) -> Radio:
    fields = node.fields(
        ["model", "renderer", "capability", "region"],
        ["base", "dmrconf_radio", "factory", "own_lists", "dmr_template", "zones", "scan_lists", "power", "naming"],
    )
    capability = _capability(fields["capability"])
    try:
        renderer = Renderer(fields["renderer"].text())
    except ValueError:
        raise fields["renderer"].error(f"renderer must be one of {', '.join(Renderer)}") from None
    if renderer is not Renderer.QDMR and "dmrconf_radio" in fields:
        raise fields["dmrconf_radio"].error("only the qdmr renderer takes a dmrconf radio")
    if renderer is not Renderer.HYTERA and "factory" in fields:
        raise fields["factory"].error("only the hytera renderer takes a factory image")
    rules = {
        key: tuple(_group_rule(item, capability, renderer) for item in fields[key].items()) if key in fields else ()
        for key in ("zones", "scan_lists")
    }
    return Radio(
        id=radio_id,
        model=fields["model"].text(),
        renderer=renderer,
        base=data_root / fields["base"].text() if "base" in fields else None,
        dmrconf_radio=fields["dmrconf_radio"].text() if "dmrconf_radio" in fields else None,
        factory=data_root / fields["factory"].text() if "factory" in fields else None,
        capability=capability,
        region=_region(fields["region"]),
        own_lists=fields["own_lists"].texts() if "own_lists" in fields else (),
        dmr_template=fields["dmr_template"].text() if "dmr_template" in fields else None,
        zones=rules["zones"],
        scan_lists=rules["scan_lists"],
        power=fields["power"].text() if "power" in fields else None,
        name_replacements=_naming(fields["naming"]) if "naming" in fields else (),
    )


def _capability(node: Node) -> Capability:
    fields = node.fields(
        ["bands", "modes", "channels", "name_length"], ["zones", "zone_channels", "scan_lists", "scan_list_channels"]
    )
    bands = tuple(_band(item) for item in fields["bands"].items())
    if not bands:
        raise fields["bands"].error("name at least one band")
    if len({band.name for band in bands}) != len(bands):
        raise fields["bands"].error("band names must be unique")

    def limit(key: str) -> int | None:
        return fields[key].integer(0, 100_000) if key in fields else None

    return Capability(
        bands=bands,
        modes=frozenset(_modes(fields["modes"])),
        channels=fields["channels"].integer(1, 100_000),
        zones=limit("zones"),
        zone_channels=limit("zone_channels"),
        scan_lists=limit("scan_lists"),
        scan_list_channels=limit("scan_list_channels"),
        name_length=fields["name_length"].integer(1, 64),
    )


def _band(node: Node) -> Band:
    fields = node.fields(["name", "rx"], ["tx"])
    return Band(
        name=fields["name"].text(),
        rx=_range(fields["rx"]),
        tx=_range(fields["tx"]) if "tx" in fields else None,
    )


def _range(node: Node) -> tuple[int, int]:
    items = node.items()
    if len(items) != 2:
        raise node.error("a range is [low, high] in MHz")
    low, high = (item.hz(MHZ) for item in items)
    if low >= high:
        raise node.error("a range is [low, high] in MHz")
    return low, high


def _region(node: Node) -> Region:
    fields = node.fields((), ["locator", "max_km", "prefixes"])
    if "prefixes" in fields and len(fields) == 1:
        return PrefixRegion(fields["prefixes"].texts())
    if set(fields) == {"locator", "max_km"}:
        locator = fields["locator"].text()
        try:
            centre = geo.locator_position(locator)
        except ValueError as error:
            raise fields["locator"].error(str(error)) from None
        return DistanceRegion(locator, centre, float(fields["max_km"].number()))
    raise node.error("a region is either {locator, max_km} or {prefixes}")


def _group_rule(node: Node, capability: Capability, renderer: Renderer) -> GroupRule:
    fields = node.fields(["name"], ["mode", "band", "source", "tag", "channel", "base_channel"])
    if renderer is not Renderer.QDMR and "base_channel" in fields:
        raise fields["base_channel"].error("only the qdmr renderer takes base channels")

    def values(key: str) -> tuple[str, ...]:
        if key not in fields:
            return ()
        node = fields[key]
        return (node.text(),) if isinstance(node.value, str) else node.texts()

    bands = frozenset(values("band"))
    unknown = bands - {band.name for band in capability.bands}
    if unknown:
        raise fields["band"].error(f"no band {sorted(unknown)[0]!r} in the capability")
    return GroupRule(
        name=fields["name"].text(),
        modes=frozenset(_modes(fields["mode"])) if "mode" in fields else frozenset(),
        bands=bands,
        sources=frozenset(values("source")),
        tags=frozenset(values("tag")),
        channels=values("channel"),
        base_channels=values("base_channel"),
    )


def _modes(node: Node) -> list[Mode]:
    names = (node.text(),) if isinstance(node.value, str) else node.texts()
    try:
        return [Mode(name) for name in names]
    except ValueError:
        raise node.error(f"modes are {', '.join(Mode)}") from None


def _naming(node: Node) -> tuple[tuple[str, str], ...]:
    """`replace: {old: new}` rewrites channel names in order before they are cut to the name length."""
    pairs: list[tuple[str, str]] = []
    for old, new in node.fields(["replace"])["replace"].entries().items():
        if not isinstance(new.value, str):
            raise new.error("expected a string")
        pairs.append((old, new.value))
    return tuple(pairs)
