# How a build works

radio-fleet keeps one channel source for every radio. You correct a repeater once, in the sources, and every radio that carries it gets the correction in its next build.

## The flow

```text
upstream lists --fleet fetch--> snapshots/ --+
                                             +--> selection --> renderer --> check --> build/<radio>/
sources/ (own lists, overrides, templates) --+         |                                  |
                                                       +--> drops with reasons            +--> build/CHANGES.md
```

1. **Snapshot.** `fleet fetch` reads the upstream lists through memory-channels-processor and writes them to `snapshots/`, sorted and in fixed columns. The snapshots are committed in the data root, so `git diff` shows what changed upstream. Every later step reads only the snapshots, never the network.
2. **Selection.** For one radio, the selection takes the upstream channels of the radio's region, applies the overrides, and expands DMR repeaters with the DMR template. The own lists come first. Then it drops every channel that the radio cannot carry: a mode it does not have, a frequency outside its bands (only the RX frequency of a receive-only channel counts), a receive-only channel the renderer cannot write, a channel beyond its memory. Each drop has a reason, so nothing disappears without a trace. Last, the zone and scan-list rules sort the channels into zones and scan lists.
3. **Render.** The radio's renderer writes the file that the radio's software reads. Where the radio has a base file, the renderer changes only the channel part and keeps every other setting.
4. **Check.** The radio's own tool, or a CSV check, checks the file: `dmrconf verify`, `jayt check`, the Hytera tool's import check, or the row and column checks of the CSV files.
5. **Output.** Only a file that passed its check goes to `build/<radio>/`, with the build record `selection.yaml`. `build/CHANGES.md` compares each build with the build that is in the radio.

## Why the check gates the output

A file in `build/` is a file you may write to a radio. If a build could leave a file that failed its check, you could import it by mistake. So the build checks the candidate first, in memory or in a temporary directory, and writes it to `build/` only when the check passes. A failed build also removes the radio's earlier output. The change report then shows the radio as `Not built.`, and `fleet publish` and `fleet applied` refuse it.

## Applied builds

The change report is only useful if it compares against what is really in the radio. radio-fleet cannot read a radio, so you tell it: `fleet applied` records the build's digest and channels in `applied.yaml` after you wrote the file to the radio. The next report compares against that record. The printed git tag marks the same state in the data root's history.

## G1: radio-fleet never talks to a radio

radio-fleet only reads and writes files. No part of it opens a serial port or a USB device, and it calls external tools only to export, import, convert or check files. Writing a file to a radio is always your step, in qdmr, CHIRP, ADMS, jayt or the Hytera tool.

This has consequences for you:

- You review `CHANGES.md` and the file before it goes to the radio.
- You decide when a build is in the radio, and you run `fleet applied` after that.
- radio-fleet never reads a radio, so a change you make on the radio itself is not in any report. Make changes in the sources or the base file instead, and build again.

## Data policy

The data root is a private repository; this repository holds only code and synthetic examples. Hytera base files, radio images, build output and secrets are never committed anywhere. See [Set up your own data root](how-to/data-root.md).
