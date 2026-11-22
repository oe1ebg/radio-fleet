# AGENTS.md

Rules for agents and people working in this repository.

## What this is

radio-fleet builds a checked CPS file for every radio of the owner from upstream repeater lists (through memory-channels-processor) and the owner's own lists. Scope and requirements: [`SPEC.md`](SPEC.md). Order of work: [`docs/PLAN.md`](docs/PLAN.md).

## Commands

```sh
uv sync            # once
just ci            # the checks CI and the Archon workflow run (uv sync --locked, ruff, mypy strict, pytest)
just test-dmrconf  # tests marked `dmrconf`; fails instead of skipping when dmrconf is missing
just workflow-test # replays the fleet-step fixtures (needs archon)
uv run fleet --help
```

Python 3.12, uv. Runtime dependencies: memory-channels-processor (git, pinned tag) and PyYAML. Add a dependency only when the step needs it, with `uv add`, and commit `uv.lock`.

## Rules

- **Trace work to the spec.** Every change serves a requirement (`R1`..`R13`, `G1`, `G2`) of `SPEC.md`. Name it in the commit body and the PR. Work that serves none is out of scope: stop and say so.
- **G1: never talk to a radio.** No code opens a serial port, a USB device or a radio tool's write command. External tools are called only to export, import, convert or check files.
- **G2: data policy.**
  - This repository is public. The owner's real data (own lists, overrides, `fleet.yaml`, qdmr bases, home locator, DMR ID) lives in their private data repository (R13), never here. Example data in `examples/` is synthetic.
  - Never commit:
    - Hytera `.rcdx` files or anything decoded from them;
    - radio images (`.img`, `.rdt`, `.FT3185`, `.FTX-1`, `.ft5d`);
    - build output;
    - secrets;
    - real codeplug exports.
  - Tests use synthetic data only. Never print keys, passwords, serial numbers or MAC addresses.
- **External tools behind adapters.** qdmr/dmrconf, jayt and hytera_reverse are external CLIs. Each one is called through one adapter class with a fake for tests. Do not copy code from those repositories. A missing feature in a tool is reported, not patched here.
- **Tests are data-free and offline.** No test needs network, a real radio file or an installed radio tool. A test that needs `dmrconf` skips when it is missing.
- **Commits:** Conventional Commits (`feat(render): ...`). Small PRs, one plan step each. Never merge, never force-push. Merging is the owner's step.

## Layout

A data root (R13) has `fleet.yaml`, `sources/`, `snapshots/`, `bases/`, `applied.yaml` and `build/`. Until step 2b moves them, the example data is at the top level.

```
examples/                synthetic data root (step 2b): fleet.yaml, sources/, snapshots/, bases/
src/radio_fleet/         package; render/ holds one module per output
tests/                   data-free tests
.archon/workflows/       the repo's Archon workflow (fleet-step)
```
