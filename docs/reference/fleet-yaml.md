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
| `dmr_template` | string | no | The template of `sources/dmr_templates.yaml` for every upstream DMR repeater. Default: none. |
| `dmr_templates` | mapping | no | Other templates by callsign or callsign prefix, such as `{XX1BB: local, XX3: south}`. The longest key that a callsign starts with wins over `dmr_template`. Default: none. |
| `zones` | list | no | Zone rules. Default: none. |
| `scan_lists` | list | qdmr | Scan-list rules. Default: none. Only the `qdmr` renderer takes them. |
| `power` | string | no | The power of every channel that sets none: a level or watts. See [`power`](#power). |
| `power_levels` | mapping | no | The watts, or the radio's value, of each power level. The `chirp` renderer needs it for every level its channels have, and `jayt` for `Mid`. See [`power`](#power). |
| `power_range` | mapping | no | `{min, max, step}` in watts, for a radio that sets watts in steps. No renderer writes it yet. See [`power`](#power). |
| `naming` | mapping | no | The names of upstream channels, and name replacements. |

A file that a profile names (`base`, `factory`, an own list, the file of the templates) must exist, and so must every template that `dmr_template` and `dmr_templates` name. If one is missing, every `select` and `build` fails, for every radio, with the file name:

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
| `zones` | integer, 0 to 100000 | no, default no limit | The number of zones (banks on the FT5D). |
| `zone_channels` | integer, 0 to 100000 | no, default no limit | The channels per zone. |
| `scan_lists` | integer, 0 to 100000 | no, default no limit | The number of scan lists. |
| `scan_list_channels` | integer, 0 to 100000 | no, default no limit | The channels per scan list. |

Selection drops a channel when:

- its mode is not in `modes`: `mode DMR not supported`
- its RX frequency is in no RX range: `RX 1297.50000 MHz outside the RX bands`
- it is receive-only and the renderer cannot write a receive-only channel: `receive-only, and the ft5d renderer cannot write a channel that never transmits`
- it is not receive-only and its TX frequency is in no TX range of any band: `TX 445.00000 MHz outside the TX bands`
- `channels` channels are already selected: `channel limit of 200 reached`

### `region`

The region is an area and, optionally, another area for some modes and the callsigns to exclude:

```yaml
region:
  locator: JJ00mm
  max_km: 80
  modes: {DMR: {locator: JJ00mm, max_km: 150}, C4FM: {prefixes: [XX1]}}
  exclude: {XX1CC: "DCS, which the radio's output cannot carry"}
```

An area is exactly one of:

| Form | Meaning |
|---|---|
| `{locator: JJ00mm, max_km: 80}` | The upstream channels within `max_km` of the centre of the Maidenhead locator (2, 4, 6 or 8 characters). A channel without a position is dropped: `no position to place it in the region`. Otherwise: `310 km from JJ00mm, beyond 80 km`. |
| `{prefixes: [XX1, XX3]}` | The upstream channels whose callsign starts with one of the prefixes. Otherwise: `callsign outside the region prefixes XX1, XX3`. |

| Key | Type | Meaning |
|---|---|---|
| `modes` | mapping | A mode (`FM`, `DMR`, `C4FM`, `D-STAR`) and the area of its channels. A mode that is not named takes the region's area. |
| `exclude` | mapping | A callsign and the reason. The radio never gets the upstream channels of that callsign. The drop is `excluded: <reason>`. |

The region applies to upstream channels only, before overrides and the DMR template. It reads the callsign of the snapshot.

### `zones` and `scan_lists`

Two lists of rules. Each rule of `zones` makes one zone (one bank on the FT5D), each rule of `scan_lists` one scan list, in list order. Both take the same keys.

| Key | Type | Meaning |
|---|---|---|
| `name` | string, required | The zone name. |
| `mode` | string or list | The channel's mode is one of these. |
| `band` | string or list | The channel's RX frequency is in one of these bands of `capability.bands`. |
| `source` | string or list | The channel's source is one of these: an own list name or an upstream source. |
| `tag` | string or list | The channel has at least one of these tags. |
| `channel` | string or list | The channel's name matches one of these patterns. `*` matches any text and `?` one character; case counts. |
| `base_channel` | string or list | `qdmr` only. Hand-made channels of the base, by their exact name. They come first, in this order. |

A channel joins a zone or scan list when it meets every key that the rule has. A rule with only a `name` takes every channel; a rule with only a `name` and `base_channel` takes only those base channels. The `channel` patterns match the name after `naming` and the cut to `name_length`. A `base_channel` name that no hand-made channel of the base has, or more than one has, fails the build: `zone DMR: no hand-made channel named 'Hotspot' in the base`.

Drops, where KIND is `zone` or `scan list`:

- `KIND NAME: matches no channel`, for a rule that takes no channel and has no `base_channel`
- `KIND NAME: KIND limit of N reached`, when `capability.zones` zones or `capability.scan_lists` scan lists exist already
- `CHANNEL: not in KIND NAME: it holds N channels at most`, for the channels beyond `capability.zone_channels` or `capability.scan_list_channels`, base channels counted first

A limit that is not given is no limit. A channel that a zone or scan list does not take stays in the radio.

### `power`

A channel asks for a power in one of two forms: a level, `Max`, `High`, `Mid`, `Low` or `Min`, or watts, a number and `W`, such as `5W` or `0.5W`. The request comes from the channel (an own list, an override or a DMR template entry; an override wins over the template) or else from the profile's `power`. The shared levels are only these five; a radio's own names, such as AnyTone's Turbo, stay in its profile, mapped to `Max`.

A profile describes the radio's power in one of two forms.

**Named levels.** `power_levels` maps each level to watts, or to the radio's own value:

```yaml
power: High
power_levels: {Max: 5W, High: 5W, Mid: 2W, Low: 1W, Min: 0.5W}
```

- A level gives the renderer's value of the level: the level itself for `qdmr`, its watts for `chirp`, and the Hytera level for `hytera` (see the table below). A level that `power_levels` maps to a radio value, such as `High: Mid` for `qdmr` or `Low: LOW2` for `jayt`, gives that value.
- Watts give the nearest level that `power_levels` maps to watts. A tie goes to the lower watts; watts below the lowest level give the lowest, and watts above the highest give the highest. Of two levels with the same watts, the higher level wins.

**A stepped range**, for a radio that sets real watts, such as the Yaesu FTX-1 in 1 W steps:

```yaml
power_range: {min: 1W, max: 10W, step: 1W}
power_levels: {Max: 10W, High: 10W, Mid: 5W, Low: 2W, Min: 1W}
```

- `max` must be `min` plus whole steps, and every watts of `power_levels` must be a step of the range.
- A level gives its watts from `power_levels`. Watts give the nearest step inside the range: a tie goes to the lower step, watts below `min` give `min` and watts above `max` give `max`.
- No renderer writes a stepped range yet: the FTX-1 renderer waits for jayt. `fleet.yaml` reads and checks `power_range`, then refuses it with `radios.R.power_range: the R renderer writes no stepped power range yet`.

When the radio's watts differ from the watts a channel asks for, the selection reports it as a line, not an error: `fleet select` prints it under `power set to the nearest value`, and `build/CHANGES.md` under `Power set to the nearest value`. The line names the channel, the requested watts and the result: `XX1AA: 25W -> Max (5W)` for named levels, `XX1AA: 2.4W -> 2W` for a range. The profile's own `power` is reported once, as `power of the profile: 25W -> Max (5W)`.

| Renderer | Values of `power_levels` | Levels that `power_levels` leaves out |
|---|---|---|
| `qdmr` | watts, or `Max`, `High`, `Mid`, `Low`, `Min` | the level itself |
| `chirp` | watts. Every channel needs a power. | no value |
| `jayt` | `LOW`, `LOW2`, `LOW3`, `HIGH`, in any case; no watts | `Max` and `High`: `HIGH`; `Low` and `Min`: `LOW`; `Mid`: no value |
| `hytera` | watts, or `High`, `Middle`, `Low` | `Max` and `High`: `High`; `Mid`: `Middle`; `Low` and `Min`: `Low` |
| `ft5d` | none: the FT5D renderer writes no power, and `power` takes only a level or watts | |

A request that the profile cannot resolve is an error that names the profile:

- `fleet.yaml` is refused when a value is not one of the renderer's, naming the key, such as `radios.uv5r-mini.power_levels.Low: the chirp renderer takes the power as watts, such as 5W, not 'High'`, and when the profile's own `power` has no value: `radios.d878uv2plus.power: no level with watts for the power 5W in power_levels`.
- A channel whose level has no value, or whose watts find no level with watts, fails `fleet select` and `fleet build`, naming the profile, the channel and its own list or source: `radios.uv5r-mini.power_levels: no value for the power Mid of channel 'Hill 2m' from hills`, `radios.d878uv2plus.power_levels: no level with watts for the power 5W of channel 'Hill 2m' from hills`.

Profiles and lists from before the levels build unchanged:

- A `chirp` profile without `power_levels` writes the watts of a channel, or of its `power`, such as `power: 5W`, as they are. A level on such a profile fails, as above.
- A `power` that is neither a level nor watts, such as `power: LOW2` for `jayt`, is the radio's value of every channel. Such a profile takes no `power_levels`, and a channel that sets its own power fails `fleet select` and `fleet build`: `radios.ft3185.power: 'LOW2' is the power of every channel, but channel 'Hill 2m' from hills sets the power Low; make power a level or watts and map the levels in power_levels`.

### `naming`

```yaml
naming:
  upstream: "{callsign} {band}"
  replace: {" TS1 ": " 1 ", " TS2 ": " 2 "}
```

| Key | Meaning |
|---|---|
| `upstream` | The name of an upstream channel. `{callsign}` is the callsign, `{band}` the name of the capability band of its RX frequency, and `{site}` the snapshot's `name` column. Default: `{callsign}`. With `{band}`, the 2 m and the 70 cm channel of one callsign get different names. Repeated spaces become one; a name that comes out empty is the callsign. An override can set another `name`, and a DMR template appends to the name. |
| `replace` | Maps a text to its replacement. The replacements run in order on every channel name, own lists included. Then the name is cut to `capability.name_length`, and trailing spaces are removed. |

## Renderers

| Renderer | Carries | Needs | Uses zones | Uses scan lists | Receive-only channels |
|---|---|---|---|---|---|
| `qdmr` | FM, DMR | `base`, `dmrconf_radio`, dmrconf | yes, as qdmr zones | yes, as qdmr scan lists; each generated channel refers to the first one that takes it | `rxOnly: true` |
| `chirp` | FM | `power` in watts, or `power` and `power_levels` in watts | no | no | `Duplex` `off` |
| `ft5d` | FM, C4FM | memory-channels-processor (installed with radio-fleet) | yes, as banks 1 to 24 | no | dropped |
| `jayt` | FM, FT-3185 only | `base`, `tools.jayt` | no | no | dropped |
| `hytera` | FM, DMR | `base`, `factory`, `tools.hytera` | yes | no | dropped |

A channel of a mode that the renderer does not carry fails the build. Keep `capability.modes` within the renderer's modes, so that selection drops such channels instead.
