# Build and import per radio family

`fleet build --radio R` writes the file of one radio to `build/R/`, but only when the file passes its check. You then open or import the file in the radio's own software and write it to the radio yourself. radio-fleet never talks to a radio.

Every build that passes also writes `build/R/selection.yaml` and rewrites `build/CHANGES.md`. A build that fails exits with 1, names the radio and the reason, and removes the earlier output of that radio.

## AnyTone: qdmr codeplug

Needs: `dmrconf` from qdmr 0.15 on the `PATH`.

1. Make a base codeplug. In qdmr, read the radio or start a new codeplug, set the radio IDs, settings, APRS and every object you want to keep by hand. Save it as YAML, for example `bases/qdmr/d878uv2plus.yaml` in the data root.
2. Find the radio key for dmrconf:

   ```sh
   dmrconf --list-radios
   ```

3. Set `base` and `dmrconf_radio` in the profile:

   ```yaml
   d878uv2plus:
     renderer: qdmr
     base: bases/qdmr/d878uv2plus.yaml
     dmrconf_radio: d878uv2
   ```

4. Build:

   ```sh
   fleet build --radio d878uv2plus
   ```

   ```text
   d878uv2plus: build/d878uv2plus/d878uv2plus.yaml
   ```

5. Open `build/d878uv2plus/d878uv2plus.yaml` in qdmr, review it, and write it to the radio.

The build keeps everything of the base and adds contacts, group lists, channels and zones whose ids start with `gen_`. A rebuild first removes every `gen_` object, so do not give a hand-made object an id that starts with `gen_`. The build writes no scan lists. Zones get their channels in list A.

The check is `dmrconf verify --radio <dmrconf_radio>`. If it fails, the build shows dmrconf's message:

```text
fleet build: d168uv: dmrconf verify failed:
Warning in cli/verify.cc@128: Warn: : The support for this radio is still under development. Some features may sill be missing or are not well tested.
ERROR in cli/verify.cc@131: Crit: In list 'channels', In element 4 ('23cm Call'), In object '23cm Call': Frequency 1297.5MHz is outside of allowed frequency ranges.
```

## Baofeng and Retevis: CHIRP CSV

Needs: nothing besides radio-fleet.

1. Set `renderer: chirp` and `power` in watts, such as `5W`.
2. Build:

   ```sh
   fleet build --radio uv5r-mini
   ```

   ```text
   uv5r-mini: build/uv5r-mini/uv5r-mini.csv
   ```

3. In CHIRP, download the image from the radio, import `build/uv5r-mini/uv5r-mini.csv` into it, review the memories, and upload the image to the radio.

The CSV has CHIRP's generic columns. Memories are numbered from 1 in the order of the selection. A bandwidth of 12.5 kHz or less gives `NFM`. The check counts the columns, the memory numbers, the memories against `channels` and each name against `name_length`.

The CHIRP renderer carries FM only. These fail the build:

- a channel without `power` in watts: `CHIRP needs the power in watts, such as 5W, not 'High'`
- a frequency or offset that is on none of the tuning steps 12.5, 6.25, 5 or 2.5 kHz

## Yaesu FT5D: ADMS-14 CSV

Needs: nothing besides radio-fleet. memory-channels-processor writes the file with its `yaesu-ft5d` output.

1. Set `renderer: ft5d`. Give zone rules for the banks.
2. Build:

   ```sh
   fleet build --radio ft5d
   ```

   ```text
   ft5d: build/ft5d/ft5d.csv
   ```

3. Import `build/ft5d/ft5d.csv` in ADMS-14, review it, and write it to the radio with ADMS.

The FT5D renderer carries FM and C4FM. An FM and a C4FM channel with the same name and frequencies become one memory. The zones become banks 1 to 24, in order; ADMS banks have no names. These fail the build:

- a DCS tone: memory-channels-processor's FT5D output carries no DCS
- an RX tone that differs from the TX tone
- more than 24 zones

## Yaesu FT-3185: jayt

Needs: a jayt executable.

1. Name jayt in `fleet.yaml`, with the commit it was built from (7 to 40 hex digits):

   ```yaml
   tools:
     jayt: {path: tools/jayt, commit: 'abc1234'}
   ```

   `path` is relative to the data root, or absolute.

2. Set `renderer: jayt` and `base` to the radio file of the FT-3185. The radio file is a radio image: give an absolute or git-ignored path, never a committed file.
3. Build:

   ```sh
   fleet build --radio ft3185
   ```

4. Write `build/ft3185/ft3185<suffix of the base>` to the radio yourself.

The build runs, in a temporary directory:

1. `jayt export BASE --format yaml -o DOCUMENT`
2. the edit: it replaces the `channels` list of the document and keeps every other key
3. `jayt import DOCUMENT -o OUTPUT --template BASE`
4. `jayt check OUTPUT`

It writes the radio file and the edited document `build/ft3185/ft3185.jayt.yaml`. If this jayt has no `import` or `check` command, or lacks an option, the build writes only the document, names the gap and exits with 1.

The jayt renderer writes FT-3185 documents only, and it carries FM only. The FT-3185 sends one CTCSS tone, squelches on the tone it sends, or uses one DCS code both ways; other tone pairs fail the build.

## Hytera: the Hytera tool

Needs: the Hytera tool, a private command-line tool for `.rcdx` files. radio-fleet calls it only through the command lines in `tools.hytera`.

1. Give the export and import command lines as argument lists. They run in the data root. The placeholders stand for the files, and each command must name exactly its own:

   ```yaml
   tools:
     hytera:
       export: [tools/hytera-export, '{base}', '{document}']
       import: [tools/hytera-import, '{document}', '{output}', '{base}', '{factory}']
   ```

   | Placeholder | File |
   |---|---|
   | `{base}` | the radio's `.rcdx` base file, with its secrets |
   | `{factory}` | an unmodified CPS factory image; added records take its defaults |
   | `{document}` | the YAML document that the export writes and the import reads |
   | `{output}` | the `.rcdx` file that the import writes |

2. Set `renderer: hytera`, `base` and `factory` in the profile. Both files stay outside every repository, so give absolute paths or paths outside the data root's repository:

   ```yaml
   hp785:
     renderer: hytera
     base: ../hytera/hp785.rcdx
     factory: ../hytera/hp785-factory.rcdx
   ```

3. Build:

   ```sh
   fleet build --radio hp785
   ```

4. Write `build/hp785/hp785.rcdx` to the radio yourself, as the Hytera tool describes.

The build exports the base, edits the digital and analog channels, contacts, RX group lists and zones of the export, and runs the import. A record is found by its name: a base record with the name of a generated one is changed in place and keeps its other settings. The import decodes its result again and fails, naming the field, when a value differs. That is the check. The export and the edited document stay in a temporary directory; only the checked `.rcdx` goes to `build/hp785/`.

The Hytera renderer carries FM and DMR. A channel name longer than 16 characters, or a table beyond its capacity, fails the import.

CAUTION: the `.rcdx` file in `build/` holds the secrets of the base. `fleet publish` copies it to the `equipment` directory. Keep `build/` and that directory out of every repository.
