# Review changes and mark a build applied

`applied.yaml` in the data root records which build is in each radio. `build/CHANGES.md` compares each new build with that applied build. Follow these steps every time you update a radio.

1. Build the radio:

   ```sh
   fleet build --radio uv5r-mini
   ```

2. Read the radio's section in `build/CHANGES.md`. Check the added, removed and changed channels, the drops, the overrides, the overrides that match nothing and the powers set to the nearest value. The format is in [reference/changes.md](../reference/changes.md).

   ```markdown
   ## uv5r-mini: Baofeng UV-5R mini (chirp)

   Against the build applied on 2026-11-22: 8 channels, 6 unchanged.

   ### Added (1)

   - 2m FM 2: rx 145.52500, tx 145.52500, mode FM, bandwidth 12.5 kHz, power 5W
   ...
   ### Changed (1)

   - XX3DD: tone_rx - -> CTCSS 123
   ```

3. If the report shows something you do not want, change the sources or the profile and build again.

4. Publish the build. It is copied to `<equipment>/<equipment_dir>/generated/<date>/`, where `equipment_dir` in the radio's profile defaults to the radio id:

   ```sh
   fleet publish uv5r-mini
   ```

   ```text
   uv5r-mini: equipment/uv5r-mini/generated/2026-11-22
   ```

   `equipment` in `fleet.yaml` names the directory, relative to the data root, and the directory must exist. Give a radio `equipment_dir`, such as `equipment_dir: baofeng/uv5r-mini`, to publish into a directory of your own layout inside it. `fleet publish` never overwrites a file: if that date's directory exists, it refuses. Remove or rename the old directory yourself if you want to publish again on the same day.

5. Write the published file to the radio with the radio's software (qdmr, CHIRP, ADMS, jayt or the Hytera tool). See [Build and import per radio family](build-and-import.md).

6. Record the build as applied:

   ```sh
   fleet applied uv5r-mini
   ```

   ```text
   uv5r-mini: sha256:e8f516c8a8abb6fb1de61820636b4d5cfc5afef604087a511144f4199889b6c1 in applied.yaml
   git tag applied/uv5r-mini/2026-11-22
   ```

   `fleet applied` writes the date, the digest and the channels of `build/uv5r-mini/` to `applied.yaml`, and rewrites `build/CHANGES.md`. It replaces the earlier entry of that radio and keeps the other radios.

7. Commit `applied.yaml` in your data root, and run the printed tag command:

   ```sh
   git add applied.yaml
   git commit -m "applied: uv5r-mini"
   git tag applied/uv5r-mini/2026-11-22
   ```

   `fleet applied` never runs git.

Run `fleet applied` only after the file is in the radio, and before the next `fleet build` of that radio: it records whatever is in `build/<radio>/` at that time.
