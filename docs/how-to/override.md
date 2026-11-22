# Correct an upstream channel with an override

An override changes the upstream channels of one callsign. Use it when the upstream list is wrong or when you want other settings for a repeater. Every override needs a reason, and the change report lists every override that a build applied.

1. Add the override to `sources/overrides.yaml`:

   ```yaml
   overrides:
     - callsign: XX3DD
       mode: FM
       reason: the repeater also uses the tone for squelch
       set: {tone_rx: {ctcss: 123.0}}
   ```

   - `callsign` is the callsign in the snapshot.
   - `mode` is optional. Without it, the override changes the channels of every mode of that callsign.
   - `set` takes one or more of `name`, `rx`, `tx`, `tone_tx`, `tone_rx`, `bandwidth`, `color_code`, `power` and `tags`, with the values of an own list channel.

2. Check that the override applies:

   ```sh
   fleet select --radio uv5r-mini
   ```

   ```text
   ...
   overrides: 1
     XX3DD FM: tone_rx=CTCSS 123 (the repeater also uses the tone for squelch)
   ```

3. Build the radio. The section of the radio in `build/CHANGES.md` lists the override under `Overrides`.

## Rules

- An override applies after the region: the region reads the callsign before the override changes the name. A repeater outside the region stays dropped.
- An override applies before the DMR template. If you change the `name` of a DMR repeater, the template channels take the new name.
- Overrides apply in file order. Two overrides of one callsign both apply; the later one wins for a field that both set.
- An override that matches no channel of a radio does nothing and gives no message. If `overrides` in `fleet select` does not show it, check the callsign and the mode.

These overrides are refused:

```text
fleet select: sources/overrides.yaml: overrides[0]: 'reason' is required
fleet select: sources/overrides.yaml: overrides[0].set: an override changes at least one field
```
