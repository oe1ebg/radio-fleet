# Tutorial: your first checked build

In this tutorial you build the files for two radios from the synthetic example data: a CHIRP CSV for a Baofeng UV-5R mini and a qdmr codeplug for an AnyTone D878UV II Plus. Then you read the change report, publish one build and mark it as applied.

You work on a copy of `examples/`, so the repository stays clean. No step touches a radio.

You need:

- git, and [uv](https://docs.astral.sh/uv/)
- dmrconf from qdmr 0.15, for the qdmr radio only

## 1. Install radio-fleet

1. Clone the repository and install its dependencies:

   ```sh
   git clone https://github.com/oe1ebg/radio-fleet.git
   cd radio-fleet
   uv sync
   ```

2. Put the `fleet` command on your `PATH` for this shell:

   ```sh
   source .venv/bin/activate
   fleet --version
   ```

   ```text
   fleet 0.1.0
   ```

## 2. Make a data root

A data root is the directory with your radios (`fleet.yaml`), your lists (`sources/`) and the upstream snapshots (`snapshots/`). `examples/` is a complete data root with synthetic data.

1. Copy it to a temporary directory and go there:

   ```sh
   mkdir -p /tmp/fleet-tutorial
   cp -R examples/. /tmp/fleet-tutorial/
   cd /tmp/fleet-tutorial
   ```

`fleet` uses the current directory as the data root. You can also give it with `--data DIR` or the environment variable `FLEET_DATA`.

## 3. Read the snapshot

`fleet fetch` reads the upstream repeater lists through memory-channels-processor and writes one snapshot per source. With `--offline` it reads the snapshot that is already there, so this step needs no network.

```sh
fleet fetch --offline
```

```text
oevsv-repeater-db: 7 channels in snapshots/oevsv-repeater-db.csv
```

The snapshot has 6 synthetic repeaters. One of them carries FM and C4FM, so it gives 2 channels.

## 4. See what a radio gets

`fleet select` prints the channels that one radio carries, its zones and scan lists, the channels it drops with the reason, and the overrides it applies.

```sh
fleet select --radio uv5r-mini
```

```text
uv5r-mini (Baofeng UV-5R mini): 5 channels, 0 zones, 0 scan lists
  2m Call          RX 145.50000 TX 145.50000 FM power 5W [simplex]
  70cm Call        RX 433.50000 TX 433.50000 FM power 5W [simplex]
  XX1AA            RX 145.60000 TX 145.00000 FM tone TX CTCSS 88.5 tone RX CTCSS 88.5 power 5W [oevsv-repeater-db]
  XX1CC            RX 438.62500 TX 431.02500 FM tone TX DCS 023 power 5W [oevsv-repeater-db]
  XX3DD            RX 145.66250 TX 145.06250 FM tone TX CTCSS 123 power 5W [oevsv-repeater-db]
drops: 6
  XX5FF: 310 km from JJ00mm, beyond 40 km
  DMR Simplex: mode DMR not supported
  C4FM Call: mode C4FM not supported
  XX1BB: mode DMR not supported
  XX1CC: mode C4FM not supported
  XX3EE: TX 445.00000 MHz outside the TX bands
overrides: 0
```

The own list `simplex` comes first, then the upstream repeaters of the region. The text in brackets is the source of each channel. Every channel that the radio cannot carry is in `drops`, with the reason.

## 5. Build the CHIRP radio

```sh
fleet build --radio uv5r-mini
```

```text
uv5r-mini: build/uv5r-mini/uv5r-mini.csv
```

`fleet build` wrote the file only because its check passed. Look at the result:

```sh
cat build/uv5r-mini/uv5r-mini.csv
```

```text
Location,Name,Frequency,Duplex,Offset,Tone,rToneFreq,cToneFreq,DtcsCode,DtcsPolarity,RxDtcsCode,CrossMode,Mode,TStep,Skip,Power,Comment,URCALL,RPT1CALL,RPT2CALL,DVCODE
1,2m Call,145.500000,,0.000000,,88.5,88.5,023,NN,023,Tone->Tone,FM,12.50,,5.0W,simplex,,,,
2,70cm Call,433.500000,,0.000000,,88.5,88.5,023,NN,023,Tone->Tone,FM,12.50,,5.0W,simplex,,,,
3,XX1AA,145.600000,-,0.600000,TSQL,88.5,88.5,023,NN,023,Tone->Tone,NFM,12.50,,5.0W,oevsv-repeater-db,,,,
4,XX1CC,438.625000,-,7.600000,Cross,88.5,88.5,023,NN,023,DTCS->,FM,12.50,,5.0W,oevsv-repeater-db,,,,
5,XX3DD,145.662500,-,0.600000,Tone,123.0,88.5,023,NN,023,Tone->Tone,FM,12.50,,5.0W,oevsv-repeater-db,,,,
```

`build/uv5r-mini/` also has `selection.yaml`, the record of this build. The change report and `fleet applied` read it.

## 6. Build the qdmr radio

This step needs `dmrconf`. If it is not installed, the build fails with `dmrconf is not installed: dmrconf not found`; go on with step 7.

1. Look at the selection. The DMR template `standard` turns the DMR repeater XX1BB into two channels, and the profile's `naming` shortens `TS1` to `1`:

   ```sh
   fleet select --radio d878uv2plus
   ```

   ```text
   d878uv2plus (AnyTone D878UV II Plus): 8 channels, 4 zones, 2 scan lists
     2m Call          RX 145.50000 TX 145.50000 FM power High [simplex]
     70cm Call        RX 433.50000 TX 433.50000 FM power High [simplex]
     DMR Simplex      RX 433.45000 TX 433.45000 DMR CC1 TS1 talkgroup TG99 power High [simplex]
     XX1AA            RX 145.60000 TX 145.00000 FM tone TX CTCSS 88.5 tone RX CTCSS 88.5 power High [oevsv-repeater-db]
     XX1BB 1 TG232    RX 438.96250 TX 431.46250 DMR CC1 TS1 talkgroup TG232 RX group Austria power High [oevsv-repeater-db]
     XX1BB 2 TG9      RX 438.96250 TX 431.46250 DMR CC1 TS2 talkgroup TG9 power High [oevsv-repeater-db]
     XX1CC            RX 438.62500 TX 431.02500 FM tone TX DCS 023 power High [oevsv-repeater-db]
     XX3DD            RX 145.66250 TX 145.06250 FM tone TX CTCSS 123 power High [oevsv-repeater-db]
   zone Simplex: 2m Call, 70cm Call, DMR Simplex
   zone FM 2m: 2m Call, XX1AA, XX3DD
   zone FM 70cm: 70cm Call, XX1CC
   zone DMR: Hotspot (base), DMR Simplex, XX1BB 1 TG232, XX1BB 2 TG9
   scan list FM: 2m Call, 70cm Call, XX1AA, XX1CC, XX3DD
   scan list DMR: Hotspot (base), DMR Simplex, XX1BB 1 TG232, XX1BB 2 TG9
   drops: 4
     XX5FF: 310 km from JJ00mm, beyond 80 km
     C4FM Call: mode C4FM not supported
     XX1CC: mode C4FM not supported
     XX3EE: TX 445.00000 MHz outside the TX bands
   overrides: 0
   ```

2. Build it:

   ```sh
   fleet build --radio d878uv2plus
   ```

   ```text
   d878uv2plus: build/d878uv2plus/d878uv2plus.yaml
   ```

`Hotspot (base)` is the hand-made channel `Hotspot` of the base: the profile's DMR zone and scan list name it with `base_channel`.

The build merged the selection into the base `bases/qdmr/d878uv2plus.yaml` and ran `dmrconf verify --radio d878uv2` on the result. Every object it added has an id that starts with `gen_`. Each generated channel refers to its scan list. The hand-made objects of the base are unchanged, and the base contact for talkgroup 9 is reused.

## 7. Read the change report

Every build rewrites `build/CHANGES.md`. It has one section per radio of `fleet.yaml`. Nothing is applied yet, so every channel is new:

```sh
cat build/CHANGES.md
```

```markdown
# Changes

Each radio's build in `build/` against its last applied build in `applied.yaml`.

## d878uv2plus: AnyTone D878UV II Plus (qdmr)

First build, nothing applied: 8 channels.

### Added (8)

- 2m Call: rx 145.50000, tx 145.50000, mode FM, power High
...

## d168uv: AnyTone D168UV (qdmr)

Not built.

## uv5r-mini: Baofeng UV-5R mini (chirp)

First build, nothing applied: 5 channels.

### Added (5)

- 2m Call: rx 145.50000, tx 145.50000, mode FM, power 5W
- 70cm Call: rx 433.50000, tx 433.50000, mode FM, power 5W
- XX1AA: rx 145.60000, tx 145.00000, mode FM, tone_tx CTCSS 88.5, tone_rx CTCSS 88.5, bandwidth 12.5 kHz, power 5W
- XX1CC: rx 438.62500, tx 431.02500, mode FM, tone_tx DCS 023, power 5W
- XX3DD: rx 145.66250, tx 145.06250, mode FM, tone_tx CTCSS 123, power 5W

### Removed (0)

None.

### Changed (0)

None.

### Drops (6)

- XX5FF: 310 km from JJ00mm, beyond 40 km
...
```

## 8. Publish the build

`fleet publish` copies a build to the `equipment` directory of `fleet.yaml`, under the radio and the date. The example names `equipment`, which does not exist yet.

1. Make the directory and publish:

   ```sh
   mkdir equipment
   fleet publish uv5r-mini
   ```

   ```text
   uv5r-mini: equipment/uv5r-mini/generated/2026-11-22
   ```

2. Publish again. `fleet publish` never overwrites a file, so it refuses:

   ```sh
   fleet publish uv5r-mini
   ```

   ```text
   fleet publish: equipment/uv5r-mini/generated/2026-11-22 exists; publish never overwrites a file
   ```

With a real radio, you now import the CSV in CHIRP and write it to the radio yourself. radio-fleet never does that step.

## 9. Mark the build as applied

After you wrote the file to the radio, record it:

```sh
fleet applied uv5r-mini
```

```text
uv5r-mini: sha256:2d90061895bed8d3e7885334d39bba4b49964123e67aa1c14fda8d8afdc4c0d7 in applied.yaml
git tag applied/uv5r-mini/2026-11-22
```

`applied.yaml` now holds the digest and the channels of this build. `fleet applied` prints the git tag command but does not run it. In your own data root, which is a git repository, you commit `applied.yaml` and run that command.

## 10. Change a list and see the difference

1. Add a channel to the own list. Append this line to `sources/own/simplex.yaml`:

   ```yaml
     - {name: 2m FM 2, rx: 145.525, mode: FM, bandwidth: 12.5}
   ```

2. Replace `sources/overrides.yaml` with an override for the repeater XX3DD:

   ```yaml
   overrides:
     - callsign: XX3DD
       mode: FM
       reason: the repeater also uses the tone for squelch
       set: {tone_rx: {ctcss: 123.0}}
   ```

3. Build again and read the section of the radio:

   ```sh
   fleet build --radio uv5r-mini
   sed -n '/## uv5r-mini/,/## uv9r-pro/p' build/CHANGES.md
   ```

   ```markdown
   ## uv5r-mini: Baofeng UV-5R mini (chirp)

   Against the build applied on 2026-11-22: 6 channels, 4 unchanged.

   ### Added (1)

   - 2m FM 2: rx 145.52500, tx 145.52500, mode FM, bandwidth 12.5 kHz, power 5W

   ### Removed (0)

   None.

   ### Changed (1)

   - XX3DD: tone_rx - -> CTCSS 123

   ### Drops (6)

   ...

   ### Overrides (1)

   - XX3DD FM: tone_rx=CTCSS 123 (the repeater also uses the tone for squelch)
   ```

The report compares the new build with the applied one. It shows the new channel, the changed tone and the override with its reason.

## Next steps

- [Set up your own data root](how-to/data-root.md)
- [Add a radio profile](how-to/radio-profile.md)
- [How a build works](explanation.md)
