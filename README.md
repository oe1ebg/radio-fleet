# radio-fleet

Builds the CPS files for all of my radios from one channel source: the ÖVSV repeater database (through [memory-channels-processor](https://gitlab.com/oe3lrt/memory-channels-processor)) plus my own channel lists.

The radios are AnyTone (qdmr), Baofeng/Retevis (CHIRP), Yaesu (ADMS, jayt) and Hytera (hytera_reverse). Each radio has a profile in `fleet.yaml`.

- What it does and must do: [`SPEC.md`](SPEC.md)
- Order of work: [`docs/PLAN.md`](docs/PLAN.md)
- Rules: [`AGENTS.md`](AGENTS.md)

Status: `fleet fetch` snapshots the upstream sources named in `fleet.yaml` (or by `--source`) to `snapshots/` (`--offline` reads the existing snapshots). `fleet select --radio R` prints the channels, zones, drops with their reasons, and applied overrides of one radio from the snapshots and `sources/`. No radio is built yet.

Your own radios and lists live in a separate data directory, usually a private repository (`SPEC.md` R13). This repository has only synthetic example data.

Upstream repeater data: ÖVSV, CC BY 4.0.
