# Correct an upstream channel with an override

An override changes the upstream channels of one callsign. Use it when the upstream list is wrong or when you want other settings for a repeater. Every override needs a reason, and the change report lists every override that a build applied and every override that matched nothing.

1. Add the override to `sources/overrides.yaml`:

   ```yaml
   overrides:
     - callsign: XX3DD
       mode: FM
       band: 2m
       reason: the repeater also uses the tone for squelch
       set: {tone_rx: {ctcss: 123.0}}
   ```

   - `callsign` is the callsign in the snapshot.
   - `mode`, `band` and `radios` are optional. They narrow the override:
     - `mode`: only the channels of this mode, such as `FM`.
     - `band`: only the channels whose RX frequency is in the band of this name in the radio's `capability.bands`, such as `70cm`. Use it for a callsign with a repeater on two bands.
     - `radios`: only on these radios of `fleet.yaml`, such as `[uv5r-mini, rt95]`.
   - `set` takes any channel key of an own list, with the values of an own list channel: `name`, `rx`, `tx`, `mode`, `tone_tx`, `tone_rx`, `bandwidth`, `color_code`, `time_slot`, `tx_talkgroup`, `rx_group_list`, `power` (a level or watts), `tags`, `rx_only`, and the CHIRP keys `step`, `skip` and `note`.
   - `clear` removes keys from the channel: any of `tone_tx`, `tone_rx`, `bandwidth`, `color_code`, `time_slot`, `tx_talkgroup`, `rx_group_list`, `power`, `tags`, `step`, `skip` and `note`. For example, `clear: [tone_rx]` makes the radio squelch on the carrier.

2. Check that the override applies:

   ```sh
   fleet select --radio uv5r-mini
   ```

   ```text
   ...
   overrides: 1
     XX3DD FM 2m: tone_rx=CTCSS 123 (the repeater also uses the tone for squelch)
   overrides that match nothing: 0
   power set to the nearest value: 0
   ```

   The line names the callsign, the mode and the band of the channel that the override changed. A cleared key shows as `key=-`.

3. Build the radio. The section of the radio in `build/CHANGES.md` lists the override under `Overrides`.

## Give one DMR repeater its own talkgroup

A radio with a DMR template turns each upstream DMR repeater into the template's channels. To give one repeater other channels, name another template for its callsign in the profile (see [Expand DMR repeaters with a template](dmr-template.md)). To make it one channel with its own talkgroup, set the talkgroup in an override:

```yaml
overrides:
  - callsign: XX1BB
    mode: DMR
    reason: the repeater carries only the local talkgroup
    set: {time_slot: 2, tx_talkgroup: TG91}
```

The template leaves a DMR channel that has a talkgroup as it is. Talkgroups and RX group lists must be defined in [talkgroups.yaml](talkgroups.md).

## Rules

- An override applies after the region: the region reads the callsign before the override changes the name. A repeater outside the region stays dropped.
- An override matches the upstream channel as it was: its callsign, mode and RX frequency, before any override changes them.
- An override applies before the DMR template. If you change the `name` of a DMR repeater, the template channels take the new name.
- Overrides apply in file order. Two overrides of one callsign both apply; the later one wins for a field that both set.
- An override that matches no upstream channel, in the radio's region or not, is listed under `overrides that match nothing` in `fleet select` and under `Overrides that match nothing` in `build/CHANGES.md`. Check its callsign, mode and band. An override for other `radios` is not listed for this radio.

These overrides are refused:

```text
fleet select: sources/overrides.yaml: overrides[0]: 'reason' is required
fleet select: sources/overrides.yaml: overrides[0]: an override sets or clears at least one field
fleet select: sources/overrides.yaml: overrides[0].clear: 'tone_rx' is both set and cleared
fleet select: sources/overrides.yaml: overrides[0].clear: cannot clear 'name'; clear takes tone_tx, tone_rx, bandwidth, color_code, time_slot, tx_talkgroup, rx_group_list, power, tags
fleet select: sources/overrides.yaml: overrides[0].radios: no radio 'uv5r' in fleet.yaml
```
