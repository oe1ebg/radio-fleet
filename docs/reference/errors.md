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
| `fleet.yaml: radios.R.dmr_template: no template 'T' in sources/dmr_templates.yaml` | Define the template, or remove it from the profile. |
| `fleet.yaml: radios.R.dmrconf_radio: only the qdmr renderer takes a dmrconf radio` | Remove `dmrconf_radio`, or change the renderer. |
| `fleet.yaml: radios.R.factory: only the hytera renderer takes a factory image` | Remove `factory`, or change the renderer. |
| `fleet.yaml: radios.R.scan_lists: only the qdmr renderer takes scan lists` | Remove `scan_lists`, or change the renderer. |
| `fleet.yaml: radios.R.zones[N].base_channel: only the qdmr renderer takes base channels` | Remove `base_channel`, or change the renderer. |
| `fleet.yaml: tools.jayt.commit: expected a git commit: 7 to 40 hex digits` | Give the commit as a quoted string of lowercase hex digits. |
| `fleet.yaml: tools.hytera.export: expected a list of arguments with exactly the placeholders {base}, {document}` | Each command line must name exactly its files. |

### Sources

| Message | Cause and fix |
|---|---|
| `sources/own/F.yaml: name: the list in F.yaml must be named 'F'` | Rename the file or the list. |
| `sources/overrides.yaml: overrides[0]: 'reason' is required` | Every override needs a reason. |
| `sources/overrides.yaml: overrides[0].set: an override changes at least one field` | `set` is empty. |
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
| `the qdmr renderer needs a base and a dmrconf_radio in the profile` | Set both. |
| `dmrconf is not installed: dmrconf not found` | Install qdmr 0.15, so `dmrconf` is on the `PATH`. |
| `dmrconf verify failed:` and dmrconf's output | The codeplug does not fit the radio. Read dmrconf's message. |
| `channel C: CHIRP needs the power in watts, such as 5W, not 'High'` | Give `power` in watts. |
| `channel C: power 'P' is not one of ...` | Give a power value that the renderer takes. The qdmr message starts with the base path. |
| `channel C: the CHIRP renderer carries FM, not DMR` | Remove the mode from `capability.modes`. The other renderers say the same in their own words. |
| `channel C: RX F MHz is on no CHIRP tuning step` | Correct the frequency. |
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
