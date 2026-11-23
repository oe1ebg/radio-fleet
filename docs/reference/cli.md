# `fleet` command reference

```text
fleet [-h] [--version] {fetch,select,build,publish,applied} ...
```

Without a command, `fleet` prints its help and exits with 0. `fleet --version` prints `fleet 0.1.0`. Exit codes and messages are in [errors.md](errors.md).

## Options of every command

Each command takes these options. Give them after the command name: `fleet select --data DIR --radio R`, not `fleet --data DIR select`.

| Option | Default | Meaning |
|---|---|---|
| `--data DIR` | `$FLEET_DATA`, else the current directory | The data root. See [data-root.md](data-root.md). |
| `--fleet FILE` | `DATA/fleet.yaml` | The fleet file. Paths in it stay relative to the data root, not to this file. |
| `--snapshots DIR` | `DATA/snapshots` | The snapshot directory. `publish` and `applied` do not use it. |
| `-h`, `--help` | | Print the command's help. |

## `fleet fetch`

```text
fleet fetch [--data DATA] [--fleet FLEET] [--snapshots SNAPSHOTS] [--source SOURCE] [--offline]
```

Snapshots each upstream source to `SNAPSHOTS/<source>.csv` through memory-channels-processor, then reads the snapshot back and prints its channel count.

| Option | Meaning |
|---|---|
| `--source SOURCE` | A memory-channels-processor source to fetch. Repeat it for more sources. Default: the `sources` of the fleet file. |
| `--offline` | Do not use the network. Read the existing snapshots only. |

```text
$ fleet fetch
oevsv-repeater-db: 251 channels in snapshots/oevsv-repeater-db.csv
```

- Without `--source`, `fleet fetch` reads the sources from the fleet file, so the fleet file must load.
- A snapshot is written only when every row converts, so a failed fetch keeps the old snapshot.
- Two fetches of the same data give byte-identical snapshots: fixed columns, rows sorted by callsign and TX frequency.
- `fleet fetch` goes on after a failed source and reports each failure. It exits with 1 if one source failed.

## `fleet select`

```text
fleet select [--data DATA] [--fleet FLEET] [--snapshots SNAPSHOTS] --radio RADIO [--sources SOURCES]
```

Prints the selection of one radio: its channels, zones, scan lists, drops with reasons, the overrides it applies and the overrides for the radio that match no upstream channel. It writes no file.

| Option | Meaning |
|---|---|
| `--radio RADIO` | Required. The radio id, a key under `radios` in the fleet file. |
| `--sources DIR` | The sources directory. Default: `DATA/sources`. |

```text
$ fleet select --radio uv5r-mini
uv5r-mini (Baofeng UV-5R mini): 7 channels, 0 zones, 0 scan lists
  2m Call          RX 145.50000 TX 145.50000 FM power 5W [simplex]
  ...
  PMR 1            RX 446.00625 TX 446.00625 FM power 5W RX only [listen]
  ...
drops: 6
  XX5FF: 310 km from JJ00mm, beyond 40 km
  ...
overrides: 0
overrides that match nothing: 0
power set to the nearest value: 0
```

Each channel line shows the name, the RX and TX frequency in MHz, the mode, then each value the channel has: tones, color code (`CC1`), time slot (`TS1`), talkgroup, RX group list, power (the radio's value of the channel's level or watts) and `RX only` for a receive-only channel. The source is in brackets: the own list or the upstream source. Each zone and scan list line lists the names of its channels; a hand-made channel of the base that the rule names with `base_channel` is marked `(base)`.

Each override line shows the callsign, the mode and band of the channel it changed, the fields it sets (`field=value`) or clears (`field=-`) and its reason. An override that matches nothing shows the callsign and the mode and band it names. It matches nothing when no upstream channel has its callsign, mode and band, whether in the radio's region or not.

Each `power set to the nearest value` line names a channel whose watts the radio sets to another value, with the requested watts and the result, such as `XX1AA: 25W -> Max (5W)` or `XX1AA: 2.4W -> 2W`. See [`power`](fleet-yaml.md#power).

`fleet select` checks every profile of the fleet file, not only the selected one. A missing own list, template, base or factory file of any radio fails it, and so does an override that names a radio the fleet file does not have.

## `fleet build`

```text
fleet build [--data DATA] [--fleet FLEET] [--snapshots SNAPSHOTS] --radio RADIO [--sources SOURCES]
```

Makes the selection like `fleet select`, renders the radio's file, runs its check and writes the file to `DATA/build/<radio>/` only when the check passes. The options are those of `fleet select`.

```text
$ fleet build --radio uv5r-mini
uv5r-mini: build/uv5r-mini/uv5r-mini.csv
```

A build that passes writes:

| File | Renderer |
|---|---|
| `build/<radio>/<radio>.yaml` | `qdmr` |
| `build/<radio>/<radio>.csv` | `chirp`, `ft5d` |
| `build/<radio>/<radio><suffix of base>` and `build/<radio>/<radio>.jayt.yaml` | `jayt` |
| `build/<radio>/<radio>.rcdx` | `hytera` |
| `build/<radio>/selection.yaml` | every renderer: the build record |

A build that fails removes the radio's output file and its `selection.yaml`, so the change report shows the radio as `Not built.`. Exception: when jayt lacks a command, the build keeps the edited document.

Every build that gets to the render step rewrites `build/CHANGES.md`, also when the render or the check fails. An error in the fleet file, the sources or the snapshots stops the command before that. The checks per renderer are in [Build and import per radio family](../how-to/build-and-import.md).

## `fleet publish`

```text
fleet publish [--data DATA] [--fleet FLEET] [--snapshots SNAPSHOTS] radio
```

Copies every file of `DATA/build/<radio>/` to `<equipment>/<radio>/generated/<date>/`, with today's date as `YYYY-MM-DD`. `equipment` is a key of the fleet file.

```text
$ fleet publish uv5r-mini
uv5r-mini: equipment/uv5r-mini/generated/2026-11-22
```

- The radio needs a complete build: a `selection.yaml` in `build/<radio>/`.
- The `equipment` directory must exist.
- If the target directory exists, `fleet publish` refuses and changes nothing.
- If the copy fails, it removes the target directory again.

## `fleet applied`

```text
fleet applied [--data DATA] [--fleet FLEET] [--snapshots SNAPSHOTS] radio
```

Records the build in `DATA/build/<radio>/` as the build that is in the radio: it writes the date, the digest and the channels to `DATA/applied.yaml`, rewrites `build/CHANGES.md` and prints the git tag command.

```text
$ fleet applied uv5r-mini
uv5r-mini: sha256:2d90061895bed8d3e7885334d39bba4b49964123e67aa1c14fda8d8afdc4c0d7 in applied.yaml
git tag applied/uv5r-mini/2026-11-22
```

- The radio needs a complete build.
- The digest is the SHA-256 over the path and content of every file in `build/<radio>/`.
- An earlier entry of the same radio is replaced. Entries of other radios stay.
- `fleet applied` never runs git.
