# Set up your own data root

Your real radios and lists go in a data root of your own, not in this repository. This repository is public and holds only the synthetic data root `examples/`. The layout of a data root is in [reference/data-root.md](../reference/data-root.md).

1. Make a new, private git repository, and copy the example into it:

   ```sh
   mkdir my-fleet-data
   cp -R radio-fleet/examples/. my-fleet-data/
   cd my-fleet-data
   git init
   ```

2. Add a `.gitignore` that keeps build output and radio files out of the repository:

   ```gitignore
   build/
   *.rcdx
   *.img
   *.rdt
   *.FT3185
   *.FTX-1
   *.ft5d
   secrets*.yaml
   ```

3. Replace the synthetic data with your own:
   - `fleet.yaml`: your radios, your locator and your regions. See [Add a radio profile](radio-profile.md).
   - `sources/own/`: your own channel lists. See [Add an own channel list](own-list.md).
   - `sources/talkgroups.yaml`, `sources/overrides.yaml`, `sources/dmr_templates.yaml`.
   - `bases/qdmr/`: a qdmr base codeplug per AnyTone radio. See [Build and import per radio family](build-and-import.md).

4. Fetch the real upstream snapshots (this needs network):

   ```sh
   fleet fetch
   ```

   ```text
   oevsv-repeater-db: 251 channels in snapshots/oevsv-repeater-db.csv
   ```

5. Commit `fleet.yaml`, `sources/`, `snapshots/` and `bases/`. The snapshots are committed so that `git diff` shows what changed upstream. ÖVSV data is CC BY 4.0: keep the `source_*` columns.

## Point `fleet` at the data root

`fleet` finds the data root in this order:

1. `--data DIR`
2. the environment variable `FLEET_DATA`
3. the current directory

`--data` goes before or after the command name:

```sh
fleet --data ~/my-fleet-data select --radio uv5r-mini
fleet select --data ~/my-fleet-data --radio uv5r-mini
```

Or set it once for the shell:

```sh
export FLEET_DATA=~/my-fleet-data
fleet select --radio uv5r-mini
```

## Keep these files out of every repository

- Hytera `.rcdx` files (bases and factory images) and anything decoded from them. They hold secrets.
- Radio images, such as the jayt base file of an FT-3185.
- `build/`.

Give the paths of such files in `fleet.yaml` as absolute paths, or as git-ignored paths in the data root. If a radio uses the Hytera renderer, `fleet publish` copies its `.rcdx` file to the `equipment` directory: keep that directory outside every repository too, or ignore `*.rcdx` in it.
