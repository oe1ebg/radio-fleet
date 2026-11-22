# `CHANGES.md` reference

`build/CHANGES.md` compares each radio's build in `build/` with its last applied build in `applied.yaml`. `fleet build` and `fleet applied` rewrite the whole file every time. It is made from the build records and `applied.yaml` only, so it holds no secret and no base path.

## Structure

```markdown
# Changes

Each radio's build in `build/` against its last applied build in `applied.yaml`.

## <radio>: <model> (<renderer>)

<summary line>

### Added (<n>)
### Removed (<n>)
### Changed (<n>)
### Drops (<n>)
### Overrides (<n>)
```

There is one `##` section per radio of `fleet.yaml`, in the order of the file. A list with no items says `None.`.

## Summary line

| Line | When |
|---|---|
| `Not built.` | `build/<radio>/` has no build record: the radio was never built, or its last build failed. The section has no lists. |
| ``The build record selection.yaml is unreadable; run `fleet build --radio <radio>`.`` | The build record is not valid. The section has no lists. |
| `First build, nothing applied: <n> channels.` | `applied.yaml` has no entry for the radio. Every channel is under `Added`. |
| `Against the build applied on <date>: <n> channels, <m> unchanged.` | `applied.yaml` has an entry. `<n>` counts the channels of the build. |

## Lists

| List | Item |
|---|---|
| Added | `<label>: <field> <value>, ...`: a channel of the build that the applied build does not have |
| Removed | `<label>: <field> <value>, ...`: a channel of the applied build that the build does not have |
| Changed | `<label>: <field> <before> -> <after>; ...`: only the fields that differ; `-` stands for a field the channel does not have |
| Drops | `<name>: <reason>`: each channel, zone and scan list that the selection dropped |
| Overrides | `<callsign> <mode>: <field>=<value>, ... (<reason>)`: each override that the build applied |

Example:

```markdown
### Changed (1)

- XX3DD: tone_rx - -> CTCSS 123

### Overrides (1)

- XX3DD FM: tone_rx=CTCSS 123 (the repeater also uses the tone for squelch)
```

## How channels are matched

- The compared fields are `rx`, `tx`, `mode`, `tone_tx`, `tone_rx`, `bandwidth`, `color_code`, `time_slot`, `tx_talkgroup`, `rx_group_list` and `power`. Tags and sources are not compared.
- A channel is matched by its name. Then a change of mode is a change, such as `mode FM -> C4FM`.
- A name that occurs more than once, in the build or in the applied build, is matched by name and mode. Its label is `<name> [<mode>]`, such as `XX1CC [FM]`. If the name and mode also repeat, the label counts them: `<name> [<mode> #2]`.
- A renamed channel shows as one removed and one added channel.
