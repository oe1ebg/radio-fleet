# Expand DMR repeaters with a template

The upstream list has one entry per DMR repeater, without a time slot or talkgroup. A DMR template turns each upstream DMR repeater into your standard channels.

1. Define the template in `sources/dmr_templates.yaml`:

   ```yaml
   templates:
     standard:
       - {name: TS1 TG232, time_slot: 1, tx_talkgroup: TG232, rx_group_list: Austria}
       - {name: TS2 TG9, time_slot: 2, tx_talkgroup: TG9}
   ```

   Each entry gives one channel. `name` is appended to the callsign, `time_slot` is 1 or 2, and `tx_talkgroup` and the optional `rx_group_list` must be defined in [talkgroups.yaml](talkgroups.md).

2. Name the template in the radio's profile in `fleet.yaml`:

   ```yaml
   radios:
     d878uv2plus:
       dmr_template: standard
   ```

3. Check the result:

   ```sh
   fleet select --radio d878uv2plus
   ```

   ```text
     XX1BB 1 TG232    RX 438.96250 TX 431.46250 DMR CC1 TS1 talkgroup TG232 RX group Austria power High [oevsv-repeater-db]
     XX1BB 2 TG9      RX 438.96250 TX 431.46250 DMR CC1 TS2 talkgroup TG9 power High [oevsv-repeater-db]
   ```

   The template made `XX1BB TS1 TG232` and `XX1BB TS2 TG9`. The profile's `naming` then replaced ` TS1 ` with ` 1 ` and ` TS2 ` with ` 2 `.

## Rules

- A template applies to upstream DMR channels only. DMR channels of own lists stay as they are.
- The color code comes from the snapshot.
- Without `dmr_template`, an upstream DMR repeater stays one channel without a time slot or talkgroup.
- Names grow by the template entry's name. Keep `name_length` of the radio in mind, or shorten the names with `naming`.

If the profile names a template that is not in the file:

```text
fleet select: fleet.yaml: radios.d878uv2plus.dmr_template: no template 'local' in sources/dmr_templates.yaml
```
