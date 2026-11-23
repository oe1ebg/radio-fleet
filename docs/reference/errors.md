# Exit codes and error messages

## Exit codes

| Code | Meaning |
|---|---|
| 0 | The command did its work. |
| 1 | The command failed. The message is on standard error. |
| 2 | The command line is wrong, such as a missing `--radio` or an unknown command. argparse prints the usage. |

`fleet build` and `fleet applied` also exit with 1 when their work is done but `build/CHANGES.md` could not be written:

```text
fleet: CHANGES.md not written: <reason>
```

## Message form

Messages start with `fleet <command>:`. A build error also names the radio: `fleet build: <radio>: <message>`. A message about a YAML file names the file and the key path, such as `fleet.yaml: radios.uv5r-mini.capability: unknown key 'name_len'`. Paths are shown as you gave them, so with the current directory as the data root they are relative.

## Messages you will meet

### Data root and configuration

| Message | Cause and fix |
|---|---|
| `no file fleet.yaml` | The data root has no `fleet.yaml`. Give `--data`, set `FLEET_DATA`, or change to the data root. |
| `fleet.yaml: no radio 'X'; radios: a, b, ...` | The radio id is not in `radios`. Use one of the listed ids. |
| `fleet.yaml: radios.R: unknown key 'K'` | A key that the profile does not have. See [fleet-yaml.md](fleet-yaml.md). |
| `fleet.yaml: radios.R: 'K' is required` | A required key is missing. |
| `fleet.yaml: radios.R.base: no file P` | A base or factory file is missing. This fails every `select` and `build`, for every radio. |
| `fleet.yaml: radios.R.own_lists: no own list 'L': no file sources/own/L.yaml` | Make the list, or remove it from `own_lists`. |
| `fleet.yaml: radios.R.dmr_template: no template 'T' in sources/dmr_templates.yaml` | Define the template, or remove it from the profile. `radios.R.dmr_templates.K` says the same of a template named for a callsign or prefix. |
| `fleet.yaml: radios.R.power: the qdmr renderer takes the power as Max, High, Mid, Low or Min, not 'Turbo'` | A value that the renderer does not take, in `power` or `power_levels.<level>`. Each renderer names its own values. A radio's own name, such as Turbo, is not a power: map the level `Max` to the radio's value instead. |
| `fleet.yaml: radios.R.power: no level with watts for the power 5W in power_levels` | The profile's `power` is watts, and `power_levels` gives no level watts. Map the levels to watts. `no value for the power L in power_levels` is the same for a level that the profile does not map. |
| `fleet.yaml: radios.R.power_range: the R renderer writes no stepped power range yet` | No renderer writes a `power_range` yet. Use `power_levels`. |
| `fleet.yaml: radios.R.power_range.max: 10W is not 1W plus whole steps of 2W` | `max` must be `min` plus whole steps. `power_range: expected min below max and a step above 0W` and `expected watts, such as 5W` are the other checks of the range. |
| `fleet.yaml: radios.R.power_levels.High: 5.5W is not a step of power_range` | With a `power_range`, every watts of `power_levels` must be one of its steps. |
| `fleet.yaml: radios.R.power_levels.Top: power levels are Max, High, Mid, Low, Min` | A key of `power_levels` must be a level. |
| `fleet.yaml: radios.R.power: power is a level (Max, High, Mid, Low, Min) or watts, such as 5W` | With `power_levels` or `power_range`, `power` is a level or watts, not a radio value. |
| `fleet.yaml: radios.R.power_levels: the ft5d renderer writes no power; power takes only a level or watts` | Remove `power_levels` and `power_range`, or give `power` a level or watts. |
| `fleet.yaml: radios.R.region.modes.M: modes are FM, DMR, C4FM, D-STAR` | A key of `region.modes` must be a mode. |
| `fleet.yaml: radios.R.naming.upstream: a name takes only the fields {callsign}, {band}, {site}, not {F}` | Use only those fields, without a format spec. |
| `fleet.yaml: radios.R.dmrconf_radio: only the qdmr renderer takes a dmrconf radio` | Remove `dmrconf_radio`, or change the renderer. |
| `fleet.yaml: radios.R.factory: only the hytera renderer takes a factory image` | Remove `factory`, or change the renderer. |
| `fleet.yaml: radios.R.scan_lists: only the qdmr and chirp renderers take scan lists` | Remove `scan_lists`, or change the renderer. |
| `fleet.yaml: radios.R.step: only the chirp renderer takes a tuning step` | Remove `step`, or change the renderer. |
| `...: step: a tuning step is one of 1, 2.5, 5, 6.25, 9, 10, 12.5, 15, 20, 25, 30, 50, 100, 125, 200 kHz` | A profile's or a channel's `step` must be one of CHIRP's tuning steps, in kHz. |
| `fleet.yaml: radios.R.equipment_dir: expected a directory inside the equipment directory, such as anytone/d878` | `equipment_dir` is a relative path without `..`. |
| `fleet.yaml: radios.R.zones[N].base_channel: only the qdmr renderer takes base channels` | Remove `base_channel`, or change the renderer. |
| `fleet.yaml: tools.jayt.commit: expected a git commit: 7 to 40 hex digits` | Give the commit as a quoted string of lowercase hex digits. |
| `fleet.yaml: tools.hytera.export: expected a list of arguments with exactly the placeholders {base}, {document}` | Each command line must name exactly its files. |

### Sources

| Message | Cause and fix |
|---|---|
| `sources/own/F.yaml: name: the list in F.yaml must be named 'F'` | Rename the file or the list. |
| `sources/overrides.yaml: overrides[0]: 'reason' is required` | Every override needs a reason. |
| `sources/overrides.yaml: overrides[0]: an override sets or clears at least one field` | Give `set` or `clear` a key. |
| `sources/overrides.yaml: overrides[0].clear: 'K' is both set and cleared` | Set the key or clear it, not both. |
| `sources/overrides.yaml: overrides[0].clear: cannot clear 'K'; clear takes ...` | Only optional keys can be cleared. Use `set` for the others. |
| `sources/overrides.yaml: overrides[0].radios: no radio 'R' in fleet.yaml` | Name radios of `fleet.yaml`. |
| `...: channels[0].power: power is a level (Max, High, Mid, Low, Min) or watts, such as 5W, not 'Turbo'` | A channel's, override's or DMR template entry's `power` is a level or watts. The profile resolves it to the radio's value. |
| `...: channels[0].tx: a receive-only channel has no TX frequency` | Remove `tx`, or `rx_only`. |
| `...: talkgroup 'X' is not defined in talkgroups.yaml` | Define the talkgroup in `sources/talkgroups.yaml`. |
| `...: RX group list 'X' is not defined in talkgroups.yaml` | Define the RX group list. |

### Snapshots and fetch

| Message | Cause and fix |
|---|---|
| ``no snapshot for 'S' at snapshots/S.csv; run `fleet fetch` `` | `select` or `build` found no snapshot. Run `fleet fetch`. |
| `fleet fetch: no snapshot for 'S' at snapshots/S.csv` | `fetch --offline` found no snapshot. Run `fleet fetch` with network. |
| `memory-channels-processor failed for source 'S': ...` | The fetch failed. The old snapshot stays. The message is memory-channels-processor's own; an unknown source lists the valid ones. |
| `snapshot P lacks columns: ...` | The snapshot is not from memory-channels-processor 0.2.5. Fetch it again. |

### Build

| Message | Cause and fix |
|---|---|
| `fleet.yaml: radios.R.power_levels: no value for the power L of channel 'C' from S` | The channel has the level `L` from `S`: `the own list sources/own/N.yaml` for an own channel, the upstream source id for an upstream channel, even when an override or the DMR template sets its power,, and the profile maps no value for it. Add `L` to `power_levels`. With a `power_range` the message says `no watts for the power L`. `fleet select` fails the same way. |
| `fleet.yaml: radios.R.power_levels: no level with watts for the power W of channel 'C' from S` | The channel asks for the watts `W` from `S`, as above, and the profile has no level with watts and no `power_range`. Map the levels to watts in `power_levels`. `fleet select` fails the same way. |
| `fleet.yaml: radios.R.power: 'V' is the power of every channel, but channel 'C' from S sets the power P; make power a level or watts and map the levels in power_levels` | The profile's `power` is a radio value `V`, as before the levels, and the channel has its own power `P` from `S`, as above. Give the profile a level or watts as `power` and map the levels in `power_levels`. `fleet select` fails the same way. |
| `the qdmr renderer needs a base and a dmrconf_radio in the profile` | Set both. |
| `dmrconf is not installed: dmrconf not found` | Install qdmr 0.15, so `dmrconf` is on the `PATH`. |
| `dmrconf verify failed:` and dmrconf's output | The codeplug does not fit the radio. Read dmrconf's message. |
| `channel C: CHIRP needs a power: give the profile a power level and its watts, such as power: High and power_levels: {High: 5W}` | The channel has no power level. Give the profile `power` and `power_levels`. |
| `channel C: the CHIRP renderer carries FM, not DMR` | Remove the mode from `capability.modes`. The other renderers say the same in their own words. |
| `channel C: RX F MHz is on no CHIRP tuning step` | Correct the frequency. |
| `channel C: RX F MHz or its offset is not on its step S kHz` | The channel's own `step` does not fit its frequency or offset. Correct the `step`, or remove it. |
| `channel C: memory-channels-processor's FT5D output carries no DCS` | Use CTCSS, or override the channel. |
| `the CSV check failed: ...` | The CSV does not fit the radio. |
| `the jayt renderer needs tools.jayt (path and commit) in the fleet file` | Add `tools.jayt`. |
| `the jayt renderer needs a base (the radio file) in the profile` | Set `base`. |
| `jayt C is not installed: no file P` | `tools.jayt.path` names no file. |
| ``jayt C lacks `jayt import` as called:`` and jayt's output | This jayt has no such command. The build writes only the document, `build/R/R.jayt.yaml`. |
| `the jayt renderer writes FT-3185 channels, not those of radio 'X'` | The base is not an FT-3185 file. |
| `the hytera renderer needs a base and a factory in the profile` | Set both. |
| `the hytera renderer needs tools.hytera (export and import commands) in the fleet file` | Add `tools.hytera`. |
| `the Hytera tool cannot run: P not found` | The first argument of a command line names no program. |
| `the Hytera tool's import failed:` and the tool's output | The rebuild or its check failed. The tool names the field. |

### Publish and applied

| Message | Cause and fix |
|---|---|
| ``no build of R in build/R; run `fleet build --radio R` `` | Build the radio first. |
| ``fleet.yaml: `fleet publish` needs the equipment directory: equipment: DIR`` | Add `equipment` to `fleet.yaml`. |
| `no equipment directory P` | Make the directory. |
| `P exists; publish never overwrites a file` | That date is published already. |
