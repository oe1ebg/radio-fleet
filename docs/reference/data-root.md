# Data root reference

The data root is one directory with all of the owner's data. `fleet` takes it from `--data DIR`, else from the environment variable `FLEET_DATA`, else the current directory. `--fleet`, `--snapshots` and `--sources` override one path each.

```text
fleet.yaml          radios, sources, tools, equipment              written by you
sources/
  own/<name>.yaml   own channel lists, one list per file           written by you
  talkgroups.yaml   talkgroups and RX group lists                  written by you
  overrides.yaml    changes to upstream channels                   written by you
  dmr_templates.yaml  DMR templates                                written by you
snapshots/<source>.csv  upstream snapshots                         written by fleet fetch
bases/              base files of the renderers, such as bases/qdmr/
applied.yaml        the build that is in each radio                written by fleet applied
build/              build output and CHANGES.md                    written by fleet build
```

| Path | Commit it? |
|---|---|
| `fleet.yaml`, `sources/`, `snapshots/`, `applied.yaml` | yes |
| qdmr bases | yes |
| jayt base files (radio images), Hytera `.rcdx` files | never |
| `build/` | never |

A file in `sources/` that does not exist reads as empty. A file that `fleet.yaml` names must exist. All YAML files are read strictly: an unknown key or a wrong value is an error with the file and the key path.

## Own lists

`sources/own/<name>.yaml`, one list per file. The file name without `.yaml` must equal `name`.

| Key | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | yes | The list name. Profiles name it in `own_lists`; channels show it as their source. |
| `tags` | list of strings | no | Tags for every channel of the list. |
| `channels` | list | yes | The channels. |

A channel has these keys:

| Key | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | yes | The channel name. |
| `rx` | number | yes | The RX frequency in MHz. |
| `tx` | number | no | The TX frequency in MHz. Default: `rx`. A receive-only channel has none. |
| `mode` | string | yes | `FM`, `DMR`, `C4FM` or `D-STAR`. |
| `tone_tx`, `tone_rx` | `{ctcss: Hz}` or `{dcs: code}` | no | The tone the radio sends, and the tone it squelches on. A DCS code is 1 to 777. |
| `bandwidth` | number | no | In kHz. 12.5 or less is narrow. |
| `color_code` | integer, 0 to 15 | no | DMR color code. |
| `time_slot` | 1 or 2 | no | DMR time slot. |
| `tx_talkgroup` | string | no | A talkgroup of `talkgroups.yaml`. |
| `rx_group_list` | string | no | An RX group list of `talkgroups.yaml`. |
| `power` | string | no | The power level: `Max`, `High`, `Mid`, `Low` or `Min`. Wins over the profile's `power`; each profile maps the level to the radio's value. |
| `tags` | list of strings | no | Added to the list's tags. |
| `rx_only` | `true` or `false` | no | A receive-only channel, such as PMR446 or Freenet: the radio never transmits on it. Selection checks only its RX frequency. Default: `false`. |

## `talkgroups.yaml`

| Key | Type | Meaning |
|---|---|---|
| `talkgroups` | mapping name: number | Each talkgroup, with a number from 1 to 16777215. |
| `rx_group_lists` | mapping name: list of names | Each RX group list, with talkgroups of `talkgroups`. |

## `overrides.yaml`

| Key | Type | Required | Meaning |
|---|---|---|---|
| `overrides` | list | no | The overrides, applied in order. |
| `overrides[].callsign` | string | yes | The upstream callsign. |
| `overrides[].mode` | string | no | Only the channels of this mode. Default: every mode. |
| `overrides[].band` | string | no | Only the channels whose RX frequency is in the capability band of this name, such as `70cm`. Default: every band. |
| `overrides[].radios` | string or list | no | Only on these radios of `fleet.yaml`. Default: every radio. |
| `overrides[].reason` | string | yes | Why. The change report shows it. |
| `overrides[].set` | mapping | no | Any channel key of an own list, with its value. |
| `overrides[].clear` | string or list | no | Keys to remove from the channel: `tone_tx`, `tone_rx`, `bandwidth`, `color_code`, `time_slot`, `tx_talkgroup`, `rx_group_list`, `power`, `tags`. |

An override sets or clears at least one key, and never both for one key. `tags` in `set` replaces the channel's tags.

## `dmr_templates.yaml`

| Key | Type | Required | Meaning |
|---|---|---|---|
| `templates` | mapping name: list | no | The templates. |
| `templates.<name>[].name` | string | yes | Appended to the channel name, after a space. |
| `templates.<name>[].time_slot` | 1 or 2 | yes | The time slot. |
| `templates.<name>[].tx_talkgroup` | string | yes | A talkgroup of `talkgroups.yaml`. |
| `templates.<name>[].rx_group_list` | string | no | An RX group list of `talkgroups.yaml`. |

## Snapshots

`snapshots/<source>.csv` is the CSV output of memory-channels-processor 0.2.5 with a fixed column order, sorted by callsign and TX frequency. `fleet fetch` writes it. Do not edit it: correct upstream data with an override.

Each row gives one channel per mode column that is `True` (`fm`, `dmr`, `c4fm`, `dstar`), named after the callsign; a profile's `naming.upstream` can name it otherwise. The `name` column is the channel's site. `freq_tx` and `ctcss_tx` are what the radio transmits. Tones go to FM channels only; DCS wins over CTCSS. The color code goes to DMR channels. `lat` and `long` place the channel for a locator region. `source_id` is the channel's source.

## `applied.yaml`

Written by `fleet applied`. One entry per radio id:

```yaml
uv5r-mini:
  date: '2026-11-22'
  digest: sha256:93ecc57271df88a604de9204267f089abbdc6ca00c86ce4431e6d6e3fc7451d5
  channels:
  - name: 2m Call
    rx: '145.50000'
    tx: '145.50000'
    mode: FM
    power: 5W
  ...
```

The channels have the fields of the build record below.

## `build/`

| Path | Content |
|---|---|
| `build/CHANGES.md` | The change report. See [changes.md](changes.md). |
| `build/<radio>/<radio>.<ext>` | The checked file. See [cli.md](cli.md#fleet-build). |
| `build/<radio>/selection.yaml` | The build record: `channels`, `drops` (name and reason), `overrides` and `unmatched_overrides` (text). |

A channel in the build record has its `name` and each of these fields that it has, as text: `rx`, `tx` (MHz with 5 decimals), `mode`, `tone_tx`, `tone_rx` (`CTCSS 88.5` or `DCS 023`), `bandwidth` (`12.5 kHz`), `color_code`, `time_slot`, `tx_talkgroup`, `rx_group_list`, `power` (the radio's value, such as `5W`), `rx_only` (`yes`).
