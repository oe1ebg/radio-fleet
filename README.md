# radio-fleet

Builds the CPS files for all of my radios from one channel source: the ÖVSV repeater database (through [memory-channels-processor](https://gitlab.com/oe3lrt/memory-channels-processor)) plus my own channel lists.

The radios are AnyTone (qdmr), Baofeng/Retevis (CHIRP), Yaesu (ADMS, jayt) and Hytera (a private tool). Each radio has a profile in `fleet.yaml` of the data root.

- What it does and must do: [`SPEC.md`](SPEC.md)
- Order of work: [`docs/PLAN.md`](docs/PLAN.md)
- Rules: [`AGENTS.md`](AGENTS.md)

Status: `fleet fetch` snapshots the upstream sources named in `fleet.yaml` (or by `--source`) to `snapshots/` (`--offline` reads the existing snapshots). `fleet select --radio R` prints the channels, zones, drops with their reasons, and applied overrides of one radio from the snapshots and `sources/`. `fleet build --radio R` merges that selection into the radio's qdmr base (AnyTone) and writes `build/R/R.yaml` only when `dmrconf verify` passes for the profile's `dmrconf_radio`; a failed check exits 1 with the radio and dmrconf's message. Generated objects have ids that start with `gen_`; everything else of the base is kept. For a chirp radio it writes CHIRP's generic CSV to `build/R/R.csv` (power in watts, such as `5W`), and for the FT5D the ADMS-14 import CSV through MCP's `yaesu-ft5d` output, with the profile's zones as banks 1 to 24; both are written only when the CSV row and column checks pass. MCP's FT5D output carries no DCS, so a DCS channel fails that build. For a Yaesu FT-3185 (renderer `jayt`) it exports the base radio file with `jayt export`, replaces the document's channels, builds the file with `jayt import --template BASE` and writes `build/R/R<base suffix>` and its document `build/R/R.jayt.yaml` only when `jayt check` passes; `tools.jayt` in `fleet.yaml` names the jayt executable and its commit. If jayt lacks the import or check, the build writes only the document and names the gap. The Hytera renderer comes with the next plan step.

## Data root

Your own radios and lists live in a data root, usually a private repository (`SPEC.md` R13):

```
fleet.yaml      the radios (R4); paths in it, such as bases, are relative to the data root
sources/        own/<list>.yaml, talkgroups.yaml, overrides.yaml, dmr_templates.yaml (R3)
snapshots/      <source>.csv, written by `fleet fetch` (R1)
bases/          base files of the renderers
applied.yaml    the builds that are in the radios (R12)
build/          build output; never committed
```

The data root is `--data DIR`, else the environment variable `FLEET_DATA`, else the current directory. `--fleet`, `--sources` and `--snapshots` still name one path each. A file that `fleet.yaml` names but that is missing is an error. An own list is in `sources/own/<name>.yaml`, named after its `name:`; a list whose file name differs is refused.

This repository has only synthetic example data, in [`examples/`](examples), which is a valid data root:

```sh
uv run fleet select --data examples --radio d878uv2plus
uv run fleet build --data examples --radio d878uv2plus   # needs dmrconf (qdmr 0.15)
uv run fleet build --data examples --radio uv5r-mini     # CHIRP CSV
uv run fleet build --data examples --radio ft5d          # FT5D ADMS CSV
```

Upstream repeater data: ÖVSV, CC BY 4.0.
