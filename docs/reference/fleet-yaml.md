# `fleet.yaml` reference

`fleet.yaml` in the data root names the upstream sources, the tools and one profile per radio. `examples/fleet.yaml` is a complete example.

The file is read strictly: an unknown key, a missing required key or a value of the wrong type is an error that names the file and the key path, for example:

```text
fleet select: fleet.yaml: radios.uv5r-mini.capability: unknown key 'name_len'
```

Paths in the file are relative to the data root, also when `--fleet` names a file elsewhere. An absolute path is used as it is. Frequencies are in MHz.

## Top level

| Key | Type | Required | Meaning |
|---|---|---|---|
| `sources` | list of strings | yes | The memory-channels-processor sources, at least one, such as `oevsv-repeater-db`. Each one has a snapshot `snapshots/<source>.csv`. |
| `radios` | mapping | yes | One profile per radio. The key is the radio id. |
| `tools` | mapping | no | `jayt` and `hytera`. |
| `equipment` | string | no | The directory that `fleet publish` copies to. `fleet publish` needs it. |

## `tools`

| Key | Type | Meaning |
|---|---|---|
| `tools.jayt.path` | string | The jayt executable, relative to the data root or absolute. A bare name such as `jayt` is the file in the data root, not a `PATH` lookup. |
| `tools.jayt.commit` | string | The git commit jayt was built from: 7 to 40 lowercase hex digits. Quote it, so YAML reads it as text. |
| `tools.hytera.export` | list of strings | The export command line of the Hytera tool. It must name exactly `{base}` and `{document}`. |
| `tools.hytera.import` | list of strings | The import command line. It must name exactly `{document}`, `{output}`, `{base}` and `{factory}`. |

The Hytera command lines run in the data root. A placeholder can be a whole argument or part of one; it is replaced by the absolute path of the file. Both `path` and `commit` of `tools.jayt` are required, and both `export` and `import` of `tools.hytera`.

## A radio profile

| Key | Type | Required | Meaning |
|---|---|---|---|
| `model` | string | yes | The radio model, shown in the output and the change report. |
| `renderer` | string | yes | `qdmr`, `chirp`, `ft5d`, `jayt` or `hytera`. |
| `capability` | mapping | yes | What the radio can carry. |
| `region` | mapping | yes | Which upstream channels the radio gets. |
| `base` | string | qdmr, jayt, hytera | The base file. qdmr: the base codeplug YAML. jayt: the radio file. hytera: the `.rcdx` file. |
| `dmrconf_radio` | string | qdmr | The radio key of `dmrconf verify --radio`. Only the `qdmr` renderer takes it. |
| `factory` | string | hytera | An unmodified factory `.rcdx` image. Only the `hytera` renderer takes it. |
| `own_lists` | list of strings | no | The own lists, by name, in order. Default: none. |
| `dmr_template` | string | no | A template of `sources/dmr_templates.yaml`. Default: none. |
| `zones` | list | no | Zone rules. Default: none. |
| `power` | string | chirp | The power of every channel that sets none. |
| `naming` | mapping | no | Name replacements. |

A file that a profile names (`base`, `factory`, an own list, the file of the template) must exist. If one is missing, every `select` and `build` fails, for every radio, with the file name:

```text
fleet select: fleet.yaml: radios.d168uv.base: no file bases/qdmr/d168uv.yaml
```

### `capability`

| Key | Type | Required | Meaning |
|---|---|---|---|
| `bands` | list | yes | At least one band. Band names must be unique. |
| `bands[].name` | string | yes | The band name, such as `2m`. Zone rules refer to it. |
| `bands[].rx` | `[low, high]` | yes | The RX range in MHz, both ends included. `low` must be less than `high`. |
| `bands[].tx` | `[low, high]` | no | The TX range in MHz. Without it, the band only receives. |
| `modes` | string or list | yes | Any of `FM`, `DMR`, `C4FM`, `D-STAR`. |
| `channels` | integer, 1 to 100000 | yes | The number of memory channels. |
| `name_length` | integer, 1 to 64 | yes | The longest channel name. |
| `zones` | integer, 0 to 100000 | no, default 0 | The number of zones (banks on the FT5D). |
| `zone_channels` | integer, 0 to 100000 | no, default 0 | The channels per zone. |
| `scan_lists` | integer, 0 to 100000 | no, default 0 | Read, but no renderer uses it yet. |

Selection drops a channel when:

- its mode is not in `modes`: `mode DMR not supported`
- its RX frequency is in no RX range: `RX 1297.50000 MHz outside the RX bands`
- its TX frequency is in no TX range of any band: `TX 445.00000 MHz outside the TX bands`
- `channels` channels are already selected: `channel limit of 200 reached`

### `region`

Exactly one of:

| Form | Meaning |
|---|---|
| `{locator: JJ00mm, max_km: 80}` | The upstream channels within `max_km` of the centre of the Maidenhead locator (2, 4, 6 or 8 characters). A channel without a position is dropped: `no position to place it in the region`. Otherwise: `310 km from JJ00mm, beyond 80 km`. |
| `{prefixes: [XX1, XX3]}` | The upstream channels whose callsign starts with one of the prefixes. Otherwise: `callsign outside the region prefixes XX1, XX3`. |

The region applies to upstream channels only, before overrides and the DMR template.

### `zones`

A list of rules. Each rule makes one zone (one bank on the FT5D), in list order.

| Key | Type | Meaning |
|---|---|---|
| `name` | string, required | The zone name. |
| `mode` | string or list | The channel's mode is one of these. |
| `band` | string or list | The channel's RX frequency is in one of these bands of `capability.bands`. |
| `source` | string or list | The channel's source is one of these: an own list name or an upstream source. |
| `tag` | string or list | The channel has at least one of these tags. |
| `channel` | string or list | The channel's name matches one of these patterns. `*` matches any text and `?` one character; case counts. |

A channel joins a zone when it meets every key that the rule has. A rule with only a `name` takes every channel. The `channel` patterns match the name after `naming` and the cut to `name_length`.

Zone drops:

- `zone NAME: matches no channel`
- `zone NAME: zone limit of N reached`, when `capability.zones` zones exist already
- `CHANNEL: not in zone NAME: it holds N channels at most`, for the channels beyond `capability.zone_channels`

A channel that a zone does not take stays in the radio.

### `power`

The value depends on the renderer. A channel's own `power` (from an own list or an override) wins over the profile's.

| Renderer | Values |
|---|---|
| `qdmr` | `Max`, `High`, `Mid`, `Low`, `Min` |
| `chirp` | watts: a number and `W`, such as `5W` or `0.5W`. Every channel needs a power. |
| `jayt` | `LOW`, `LOW2`, `LOW3`, `HIGH`, in any case |
| `hytera` | `High`, `Middle`, `Low` |
| `ft5d` | not used |

Any other value fails the build of that radio.

### `naming`

```yaml
naming: {replace: {" TS1 ": " 1 ", " TS2 ": " 2 "}}
```

`replace` maps a text to its replacement. The replacements run in order on every channel name. Then the name is cut to `capability.name_length`, and trailing spaces are removed.

## Renderers

| Renderer | Carries | Needs | Uses zones |
|---|---|---|---|
| `qdmr` | FM, DMR | `base`, `dmrconf_radio`, dmrconf | yes, as qdmr zones |
| `chirp` | FM | `power` in watts | no |
| `ft5d` | FM, C4FM | memory-channels-processor (installed with radio-fleet) | yes, as banks 1 to 24 |
| `jayt` | FM, FT-3185 only | `base`, `tools.jayt` | no |
| `hytera` | FM, DMR | `base`, `factory`, `tools.hytera` | yes |

A channel of a mode that the renderer does not carry fails the build. Keep `capability.modes` within the renderer's modes, so that selection drops such channels instead.
