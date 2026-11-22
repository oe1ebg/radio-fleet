# radio-fleet specification

## Goal

One build turns the upstream repeater lists and the owner's own channel lists into a checked CPS file for every radio the owner has. A readable report says what changed since the file that is in the radio now.

## Radios

| Radio | Output | Tool that checks or builds it |
|---|---|---|
| AnyTone D878UV II Plus, D168UV | qdmr YAML | `dmrconf verify` (qdmr 0.15) |
| Baofeng UV-5R mini, UV-9R Pro, Retevis RT95 | CHIRP CSV | CHIRP (manual import) |
| Yaesu FT5D | ADMS-14 CSV | ADMS (manual import) |
| Yaesu FT-3185, FTX-1 | radio file | `jayt` (owner's project, in development) |
| Hytera HP785, HM785 | `.rcdx` | the owner's Hytera tool (private) for now; later a jayt-like Hytera product |

## Requirements

Each requirement has an acceptance criterion. Tests are data-free: synthetic channels and fake tool adapters, no network and no real radio data.

- **R1 Fetch and snapshot.**
  - Use memory-channels-processor (MCP), pinned in `pyproject.toml`, to read the upstream sources. The first one is `oevsv-repeater-db`; others come through `fleet.yaml`.
  - Write one snapshot per source to `snapshots/<source>.csv` in the data root (R13), sorted by callsign and frequency, with a fixed column order.
  - Use MCP's CSV output: in MCP 0.2.5 the JSON output fails with the installed pandas.
  - *Accept:* two fetches of the same data give byte-identical snapshots, and `--offline` builds from the snapshot without network.
- **R2 Channel model.**
  - One canonical model, `radio_fleet.model.Channel`. It has name, RX/TX frequency in Hz, mode (FM, DMR, C4FM, D-STAR), FM tones (CTCSS/DCS, TX and RX), bandwidth, DMR color code, time slot, TX talkgroup and RX group list, power, tags and source.
  - A reader turns MCP snapshot rows into channels. MCP's `freq_tx` and `ctcss_tx` are what the radio transmits.
  - A channel can be receive-only (for example PMR446 or Freenet). Selection checks only its RX frequency against the radio's bands, and every renderer writes it so that the radio cannot transmit on it, or drops it with a reason when the radio cannot do that.
  - *Accept:*
    - a snapshot row for an FM repeater and one for a DMR repeater convert into the expected channels;
    - a receive-only channel outside the TX bands is kept, and its output cannot transmit.
- **R3 Own lists.**
  - The owner's lists are YAML files in `sources/own/` of the data root (R13), one list per file, with name, tags and channels in the R2 model. Talkgroups and RX group lists are named in the list and defined once in `sources/talkgroups.yaml`.
  - `sources/overrides.yaml` changes upstream channels by callsign, optionally narrowed to one band and mode, and optionally to named radios. An override can set or clear any R2 field, tones, time slot, talkgroup and RX group list included. Each entry needs a `reason`. An override that matches no channel is reported.
  - `sources/dmr_templates.yaml` expands one upstream DMR repeater into the owner's standard channels (time slot + talkgroup + RX group, for example `TS1 TG232`, `TS2 TG9`). A radio profile names a default template and may name other templates for callsigns or callsign prefixes.
  - *Accept:*
    - an override without a reason is refused;
    - an override is applied and reported;
    - an override narrowed to a band changes only that band's channel;
    - an override that matches nothing is reported;
    - a DMR repeater expands to the template's channels, and to another template where the profile names one for its callsign.
- **R4 Radio profiles.**
  - `fleet.yaml` in the data root (R13) names every radio, with:
    - its renderer and base file;
    - its capability: bands with RX and TX limits, modes, channel/zone/scan-list limits, name length; a limit that is not given means no limit;
    - the region: a locator and maximum km, or callsign prefixes; optionally a different region per mode, and callsigns to exclude;
    - the own lists it includes;
    - zone/bank rules and scan-list rules, as filter expressions;
    - power: channels carry a power level (Max, High, Mid, Low, Min), and the profile maps the levels to the radio's values (for example watts for CHIRP);
    - naming: upstream channel names can include the band, so that two bands of one callsign get different names.
  - Selection drops every channel the radio cannot carry and records the reason. An example is a TX frequency outside the radio's TX range.
  - *Accept:*
    - the selection of a synthetic fleet gives the expected channels per radio, per zone and per scan list, and the expected list of drops with reasons;
    - a profile without zone or scan-list limits keeps all its zones and scan lists;
    - a channel with power `High` gets the radio's mapped value in every renderer;
    - an excluded callsign is dropped with a reason.
- **R5 qdmr renderer.**
  - Merge the selection into the radio's base qdmr YAML. Keep its settings, radio IDs, APRS/positioning and every hand-made object.
  - Generated contacts, group lists, channels, zones and scan lists carry an id prefix (`gen_`), so a rebuild replaces exactly the generated objects.
  - Reuse an existing contact with the same number instead of adding a second one.
  - Generate scan lists from the profile's scan-list rules (R4); generated channels refer to their scan list. Hand-made channels of the base can be members of generated zones and scan lists by name.
  - Read bases that use qdmr's own YAML tags (`!default`, `!selected`) and keep them.
  - *Accept:* rendering twice gives the same file; hand-made objects are unchanged; `dmrconf verify -R <radio>` passes on a synthetic base (skipped when `dmrconf` is not installed).
- **R6 CHIRP renderer.**
  - Write the CHIRP CSV with the columns of CHIRP's generic CSV: `Location,Name,Frequency,Duplex,Offset,Tone,rToneFreq,cToneFreq,DtcsCode,DtcsPolarity,RxDtcsCode,CrossMode,Mode,TStep,Skip,Power,Comment,...`.
  - Respect the radio's memory count and name length.
  - `TStep` comes from the profile (default 12.5 kHz) or the channel; `Skip` comes from the profile's scan rules or the channel; `Comment` is the channel's location or note, not its source id.
  - *Accept:*
    - repeater, simplex, CTCSS and DCS channels give the expected rows;
    - the memory limit drops channels with a reason;
    - a profile step of 5 kHz and a skipped channel give the expected `TStep` and `Skip`.
- **R7 Yaesu FT5D renderer.**
  - Write the ADMS-14 import CSV through MCP's `yaesu-ft5d` output, with banks from the profile.
  - *Accept:* a synthetic selection gives a CSV that MCP's own format accepts, with the expected banks.
- **R8 Yaesu FT-3185 / FTX-1 through jayt.**
  - An adapter with `export`, `import` and `check` calls the jayt CLI: `jayt export --format yaml`, `jayt import --format ... --template BASE`, `jayt check`.
  - The renderer edits only the channel part of the radio document.
  - The path and commit of jayt are set in `fleet.yaml`.
  - If jayt lacks a needed command, the renderer stops after writing the radio document and reports the gap.
  - *Accept:* with a fake jayt, the renderer edits the channels, calls import and check with the right arguments, and leaves all other keys of the document unchanged.
- **R9 Hytera through the Hytera tool.**
  - The Hytera tool is the owner's private CLI for `.rcdx` files. The repository does not name it or its scripts: `tools.hytera` in the data-root `fleet.yaml` (R13) holds its export and import command lines, with placeholders for the base, factory, document and output files.
  - The same adapter interface calls:
    - the export command, which writes a lossless YAML document of the base file;
    - the import command after the edit, which rebuilds the `.rcdx` file with the secrets of the base file and the defaults of a factory file;
    - its post-check: the import decodes its result again and fails, naming the field, when a value differs.
  - The renderer edits digital and analog channels, contacts, RX group lists and zones.
  - Base files stay outside the repo, and no secret is ever written to the repo, to `build/` logs or to the terminal.
  - A later Hytera tool replaces the adapter's command lines without a change to the model or the profiles.
  - *Accept:* with a fake tool, the renderer produces the expected YAML edit and the expected tool calls, and the base path never appears in a committed file.
- **R10 Verify gate.**
  - `fleet build` runs each output's check:
    - `dmrconf verify`;
    - `jayt check`;
    - the post-check of the Hytera tool's import;
    - the CSV row and column checks.
  - A failed check fails the build for that radio, with the tool's message.
  - *Accept:* a failing fake check gives a non-zero exit and names the radio.
- **R11 Change report.**
  - `build/CHANGES.md` lists per radio:
    - the channels added, removed and changed, compared by name and field;
    - the drops with their reasons;
    - the overrides applied.
  - It compares against the last applied build (R12), or against nothing on the first build.
  - *Accept:* a synthetic before/after pair gives the expected report.
- **R12 Publish and applied.**
  - `fleet publish` copies `build/<radio>/` to `<equipment>/<folder>/generated/<date>/`, where `<folder>` is the radio's `equipment_dir` from its profile or else its id. It never overwrites another file.
  - `fleet applied <radio>` records the build's digest in `applied.yaml` and prints the git tag command `applied/<radio>/<date>` for the owner.
  - *Accept:* publish refuses an existing target, and applied records the digest.
- **R13 Data root.**
  - The owner's data is in one directory, the data root: `fleet.yaml`, `sources/`, `snapshots/`, `bases/`, `applied.yaml` and `build/`.
  - The data root is `--data DIR`, else the environment variable `FLEET_DATA`, else the current directory. The options that name one path (`--fleet`, `--sources`, `--snapshots`) still win over the data root for that path.
  - Paths in `fleet.yaml` (bases, tool paths) are relative to the data root.
  - The owner's data root is a separate, private repository. This repository has only synthetic example data, in `examples/`, which is a valid data root.
  - A file that `fleet.yaml` names but that does not exist (an own list, a base, a template) is an error that names the file. It is never skipped.
  - *Accept:*
    - `fleet select --data examples --radio R` run from another directory gives the same output as `fleet select --radio R` run in `examples/`;
    - `FLEET_DATA` gives the same result, and `--data` wins over `FLEET_DATA`;
    - an own list that is named but missing fails with its file name.

## Rules

- **G1 No radio access.** radio-fleet never talks to a radio, and nothing in it opens a serial or USB port. Writing a file to a radio is the owner's manual step in qdmr, CHIRP, ADMS, jayt or the Hytera tool.
- **G2 Data policy.**
  - This repository is public. It has code, tests and synthetic example data (`examples/`), and nothing of the owner's real data: no real own lists, overrides, home locator, DMR ID or base file.
  - The owner's private data repository (R13) may commit:
    - own lists, talkgroups, overrides, DMR templates;
    - upstream snapshots (ÖVSV data is CC BY 4.0: keep the source columns);
    - qdmr base files;
    - `fleet.yaml` and `applied.yaml`.
  - No repository ever commits:
    - Hytera base files or anything derived from them;
    - radio images;
    - build output;
    - secrets.
  - Tests use synthetic data only.

## Plan

The order of the work is in [`docs/PLAN.md`](docs/PLAN.md).
