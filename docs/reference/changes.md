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
### Overrides that match nothing (<n>)
### Power set to the nearest value (<n>)
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
| Overrides | `<callsign> <mode> <band>: <field>=<value>, ... (<reason>)`: each override that the build applied, once per channel it changed; a cleared field shows as `<field>=-` |
| Overrides that match nothing | `<callsign> [<mode>] [<band>]: <field>=<value>, ... (<reason>)`: each override for the radio that matches no upstream channel, with the mode and band it names |
| Power set to the nearest value | `<name>: <watts> -> <level> (<watts>)` or `<name>: <watts> -> <watts>`: each channel whose watts the radio sets to another value, such as `XX1AA: 25W -> Max (5W)`; the profile's own `power` is reported once as `power of the profile: ...` |

Example:

```markdown
### Changed (1)

- XX3DD: tone_rx - -> CTCSS 123

### Overrides (1)

- XX3DD FM 2m: tone_rx=CTCSS 123 (the repeater also uses the tone for squelch)

### Overrides that match nothing (1)

- XX9ZZ FM: tone_tx=- (the repeater stopped sending a tone)
```

## How channels are matched

- The compared fields are `rx`, `tx`, `mode`, `tone_tx`, `tone_rx`, `bandwidth`, `color_code`, `time_slot`, `tx_talkgroup`, `rx_group_list`, `power` (the radio's value, such as `5W`), `rx_only`, and the channel's own `step`, `skip` and `note`. Tags and sources are not compared.
- A channel is matched by its name. Then a change of mode is a change, such as `mode FM -> C4FM`.
- A name that occurs more than once, in the build or in the applied build, is matched by name and mode. Its label is `<name> [<mode>]`, such as `XX1CC [FM]`. If the name and mode also repeat, the label counts them: `<name> [<mode> #2]`.
- A renamed channel shows as one removed and one added channel.
