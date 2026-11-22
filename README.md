# radio-fleet

Builds the CPS files for all of my radios from one channel source: the ÖVSV repeater database (through [memory-channels-processor](https://gitlab.com/oe3lrt/memory-channels-processor)) plus my own channel lists.

The radios are AnyTone (qdmr), Baofeng/Retevis (CHIRP), Yaesu (ADMS, jayt) and Hytera (hytera_reverse). Each radio has a profile in `fleet.yaml` of the data root.

- What it does and must do: [`SPEC.md`](SPEC.md)
- Order of work: [`docs/PLAN.md`](docs/PLAN.md)
- Rules: [`AGENTS.md`](AGENTS.md)

Status: `fleet fetch` snapshots the upstream sources named in `fleet.yaml` (or by `--source`) to `snapshots/` (`--offline` reads the existing snapshots). `fleet select --radio R` prints the channels, zones, drops with their reasons, and applied overrides of one radio from the snapshots and `sources/`. `fleet build --radio R` builds a qdmr radio (AnyTone): it merges the selection into the radio's base qdmr YAML, writes `build/<radio>/<radio>.yaml` and checks it with `dmrconf verify` (qdmr 0.15); a file that fails the check is removed and the build exits non-zero. Generated objects have ids that start with `gen_`; every build replaces them and keeps the base's settings and hand-made objects. The other renderers come with later plan steps.

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
```

Upstream repeater data: ÖVSV, CC BY 4.0.
