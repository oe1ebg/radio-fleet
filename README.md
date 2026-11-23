# radio-fleet

Builds the CPS files for all of my radios from one channel source: the ÖVSV repeater database (through [memory-channels-processor](https://gitlab.com/oe3lrt/memory-channels-processor)) plus my own channel lists.

The radios are AnyTone (qdmr), Baofeng/Retevis (CHIRP), Yaesu (ADMS, jayt) and Hytera (a private tool). Each radio has a profile in `fleet.yaml` of the data root.

- How to use it: [`docs/`](docs/README.md), starting with the [tutorial](docs/tutorial.md)
- What it does and must do: [`SPEC.md`](SPEC.md)
- Order of work: [`docs/PLAN.md`](docs/PLAN.md)
- Rules: [`AGENTS.md`](AGENTS.md)

Status: `fleet fetch` snapshots the upstream sources named in `fleet.yaml` (or by `--source`) to `snapshots/` (`--offline` reads the existing snapshots). `fleet select --radio R` prints the channels, zones, scan lists, drops with their reasons, applied overrides, overrides that match nothing and powers set to the nearest value of one radio from the snapshots and `sources/`. Channels, overrides, DMR templates and profiles give a power as a level (Max, High, Mid, Low, Min) or as watts; each profile maps the levels to watts or the radio's values, and watts go to the nearest level (or the nearest step of a `power_range`, which no renderer writes yet), with a report line when they change; a receive-only channel is checked against the RX bands only and written so that the radio cannot transmit, or dropped by a renderer that cannot; overrides can be narrowed by band, mode and radio; a profile can name DMR templates per callsign, another region per mode and excluded callsigns, and band-aware upstream names. `fleet build --radio R` merges that selection into the radio's qdmr base (AnyTone) and writes `build/R/R.yaml` only when `dmrconf verify` passes for the profile's `dmrconf_radio`; a failed check exits 1 with the radio and dmrconf's message. Generated objects, scan lists included, have ids that start with `gen_`; everything else of the base is kept, qdmr's `!default` and `!selected` tags too. For a chirp radio it writes CHIRP's generic CSV to `build/R/R.csv` (levels mapped to watts; `TStep` from the channel's or the profile's `step`, `Skip` from the channel's `skip` or the profile's scan-list rules, `Comment` from the channel's `note` or its upstream site), and for the FT5D the ADMS-14 import CSV through MCP's `yaesu-ft5d` output, with the profile's zones as banks 1 to 24; both are written only when the CSV row and column checks pass. MCP's FT5D output carries no DCS, so a DCS channel fails that build. For a Yaesu FT-3185 (renderer `jayt`) it exports the base radio file with `jayt export`, replaces the document's channels, builds the file with `jayt import --template BASE` and writes `build/R/R<base suffix>` and its document `build/R/R.jayt.yaml` only when `jayt check` passes; `tools.jayt` in `fleet.yaml` names the jayt executable and its commit. If jayt lacks the import or check, the build writes only the document and names the gap. For a Hytera radio it runs the export command of `tools.hytera` in `fleet.yaml` on the profile's `base` `.rcdx`, edits the export's channels, contacts, RX group lists and zones, and runs the import command, which rebuilds `build/R/R.rcdx` with the base's secrets and the `factory` image's defaults; the import's own post-check is the check. The base and factory files stay outside every repository. A build that passes also writes `build/R/selection.yaml` (its channels, drops and overrides), and every build rewrites `build/CHANGES.md`: per radio of `fleet.yaml`, the channels added, removed and changed by name and field against the last applied build, the drops with their reasons and the overrides applied. `fleet publish R` copies `build/R/` to `<equipment>/<equipment_dir>/generated/<date>/`, where `equipment` in `fleet.yaml` names an existing directory and the profile's `equipment_dir` defaults to R, and refuses a target that exists. `fleet applied R` records the digest and channels of `build/R/` in `applied.yaml` and prints the `git tag applied/R/<date>` command; it never runs git.

## Data root

Your own radios and lists live in a data root, usually a private repository (`SPEC.md` R13):

```
fleet.yaml      the radios (R4); paths in it, such as bases, are relative to the data root
sources/        own/<list>.yaml, talkgroups.yaml, overrides.yaml, dmr_templates.yaml (R3)
snapshots/      <source>.csv, written by `fleet fetch` (R1)
bases/          base files of the renderers
applied.yaml    the builds that are in the radios, written by `fleet applied` (R12)
build/          build output and CHANGES.md (R11); never committed
```

The data root is `--data DIR` (before or after the command name), else the environment variable `FLEET_DATA`, else the current directory. `--fleet`, `--sources` and `--snapshots` still name one path each. A file that `fleet.yaml` names but that is missing is an error. An own list is in `sources/own/<name>.yaml`, named after its `name:`; a list whose file name differs is refused.

This repository has only synthetic example data, in [`examples/`](examples), which is a valid data root:

```sh
uv run fleet select --data examples --radio d878uv2plus
uv run fleet build --data examples --radio d878uv2plus   # needs dmrconf (qdmr 0.15)
uv run fleet build --data examples --radio uv5r-mini     # CHIRP CSV
uv run fleet build --data examples --radio ft5d          # FT5D ADMS CSV
```

Upstream repeater data: ÖVSV, CC BY 4.0.
