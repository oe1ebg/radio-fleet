# Plan

Each step is delivered as one pull request through the repo workflow `fleet-step`:

```sh
archon --cwd ~/projects/oe1ebg/radio-fleet workflow run fleet-step --input step=1 "Plan step 1"
```

The run implements the step on a branch, opens a draft PR, reviews and simplifies it, and waits for green CI. Merging is the owner's step. Run the next step after the previous PR is merged.

| Step | Requirements | Content |
|---|---|---|
| 1 | R1, R2 | `radio_fleet.model`, MCP fetch to `snapshots/`, snapshot reader; `fleet fetch`. |
| 2 | R3, R4 | Own lists, talkgroups, overrides, DMR templates; `fleet.yaml` schema and selection; `fleet select --radio R` prints the selection and the drops. Example `fleet.yaml` with every radio of SPEC.md. |
| 3 | R5, R10 | qdmr renderer and `dmrconf verify` gate; `fleet build --radio R`. |
| 4 | R6, R7 | CHIRP and FT5D renderers. |
| 5 | R8 | jayt adapter and Yaesu renderer (FT-3185 first). |
| 6 | R9 | hytera_reverse adapter and Hytera renderer. |
| 7 | R11, R12 | `CHANGES.md`, `fleet publish`, `fleet applied`. |

After step 2, the owner seeds the own lists from the current configs (local, with real data, not in a workflow run). After each renderer step, the owner builds the real radio once and checks `CHANGES.md` against today's hand-made config.
