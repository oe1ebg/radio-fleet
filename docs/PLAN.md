# Plan

Each step is delivered as one pull request through the repo workflow `fleet-step`:

```sh
archon --cwd ~/projects/oe1ebg/radio-fleet workflow run fleet-step --input step=1 "Plan step 1"
```

The run implements the step on a branch, opens a draft PR, reviews and simplifies it, and waits for green CI. Merging is the owner's step. Run the next step after the previous PR is merged. Exception: after step 3 is merged, steps 4, 5 and 6 can run at the same time, because each one adds its own renderer under `render/`. Merge them one at a time; the delivery merges `main` into the other branches when they conflict.

Facts that are true for one run only go in the `note` input, for example where jayt or the Hytera tool is installed:

```sh
archon --cwd ~/projects/oe1ebg/radio-fleet workflow run fleet-step --input step=5 --input note="jayt is at ~/projects/jayt, commit abc1234" "Plan step 5"
```

Change `fleet-step` only together with its fixtures; `just workflow-test` replays them.

| Step | Requirements | Content |
|---|---|---|
| 1 | R1, R2 | `radio_fleet.model`, MCP fetch to `snapshots/`, snapshot reader; `fleet fetch`. |
| 2 | R3, R4 | Own lists, talkgroups, overrides, DMR templates; `fleet.yaml` schema and selection; `fleet select --radio R` prints the selection and the drops. Example `fleet.yaml` with every radio of SPEC.md. |
| 2b | R13, G2 | Data root: `--data` and `FLEET_DATA`; a named file that is missing is an error. Move `fleet.yaml`, `sources/` and `snapshots/` to `examples/` with synthetic data only. Tests that read example data use `examples/`. Update the layout in README.md and AGENTS.md. |
| 3 | R5, R10 | qdmr renderer and `dmrconf verify` gate; `fleet build --radio R`. |
| 4 | R6, R7 | CHIRP and FT5D renderers. |
| 5 | R8 | jayt adapter and Yaesu renderer (FT-3185 first). |
| 6 | R9 | Hytera tool adapter and Hytera renderer. |
| 7 | R11, R12 | `CHANGES.md`, `fleet publish`, `fleet applied`. |
| 8a | R4, R5 | Zones and scan lists: a limit that is not given means no limit (today it means 0); scan-list rules and generated qdmr scan lists with limits and drops (#21); generated channels refer to their scan list; hand-made base channels join generated zones and scan lists by name; the qdmr base reader keeps `!default` and `!selected`. |
| 8b | R2, R3, R4 | Channel data: receive-only channels; power levels mapped per radio; overrides narrowed by band, mode and radio that set or clear any field, and a report of overrides that match nothing; several DMR templates per radio; region per mode and excluded callsigns; upstream names that tell the bands of one callsign apart. |
| 8c | R6, R12 | CHIRP `TStep`, `Skip` and `Comment`; `equipment_dir` per radio for `fleet publish`; CLI fixes: `--data` also before the command, `publish` and `applied` without `--snapshots`, a qdmr power error names the profile or own list instead of the base. |

Steps 8a to 8c close the gaps that the first real builds of the CHIRP and qdmr radios showed. Run them one after the other: all three change selection or the renderers. The FTX-1 and C4FM in the jayt renderer wait for jayt.

After step 2b, the owner creates the private data repository (R13) and seeds the own lists from the current configs there (local, with real data, not in a workflow run). Real qdmr bases go to that repository, not to `bases/` here; step 3 tests use synthetic bases. After each renderer step, the owner builds the real radio once with `--data` and checks `CHANGES.md` against today's hand-made config.
