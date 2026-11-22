# Review changes and mark a build applied

`applied.yaml` in the data root records which build is in each radio. `build/CHANGES.md` compares each new build with that applied build. Follow these steps every time you update a radio.

1. Build the radio:

   ```sh
   fleet build --radio uv5r-mini
   ```

2. Read the radio's section in `build/CHANGES.md`. Check the added, removed and changed channels, the drops and the overrides. The format is in [reference/changes.md](../reference/changes.md).

   ```markdown
   ## uv5r-mini: Baofeng UV-5R mini (chirp)

   Against the build applied on 2026-11-22: 6 channels, 4 unchanged.

   ### Added (1)

   - 2m FM 2: rx 145.52500, tx 145.52500, mode FM, bandwidth 12.5 kHz, power 5W
   ...
   ### Changed (1)

   - XX3DD: tone_rx - -> CTCSS 123
   ```

3. If the report shows something you do not want, change the sources or the profile and build again.

4. Publish the build. It is copied to `<equipment>/<radio>/generated/<date>/`:

   ```sh
   fleet publish uv5r-mini
   ```

   ```text
   uv5r-mini: equipment/uv5r-mini/generated/2026-11-22
   ```

   `equipment` in `fleet.yaml` names the directory, relative to the data root, and the directory must exist. `fleet publish` never overwrites a file: if that date's directory exists, it refuses. Remove or rename the old directory yourself if you want to publish again on the same day.

5. Write the published file to the radio with the radio's software (qdmr, CHIRP, ADMS, jayt or the Hytera tool). See [Build and import per radio family](build-and-import.md).

6. Record the build as applied:

   ```sh
   fleet applied uv5r-mini
   ```

   ```text
   uv5r-mini: sha256:2d90061895bed8d3e7885334d39bba4b49964123e67aa1c14fda8d8afdc4c0d7 in applied.yaml
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
