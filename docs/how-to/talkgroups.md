# Define talkgroups and RX group lists

Talkgroups and RX group lists are defined once, in `sources/talkgroups.yaml`. Own lists and DMR templates name them; the qdmr and Hytera renderers turn them into contacts and group lists.

1. Add the talkgroup with its number, and the RX group lists with their talkgroups:

   ```yaml
   talkgroups:
     TG9: 9
     TG99: 99
     TG232: 232
     TG2321: 2321
   rx_group_lists:
     Austria: [TG232, TG9]
     Vienna: [TG2321, TG232, TG9]
   ```

   A talkgroup number is a whole number from 1 to 16777215. An RX group list may only name talkgroups of this file.

2. Use them in a DMR channel of an own list:

   ```yaml
   - name: DMR Vienna
     rx: 438.250
     tx: 430.650
     mode: DMR
     color_code: 1
     time_slot: 2
     tx_talkgroup: TG2321
     rx_group_list: Vienna
   ```

   Or use them in a [DMR template](dmr-template.md).

3. Check the channel:

   ```sh
   fleet select --radio d878uv2plus
   ```

   The channel shows `talkgroup TG2321 RX group Vienna`.

## How the renderers use them

- qdmr: each talkgroup becomes a group call contact with the id `gen_tg<number>`. If the base already has a group call contact with that number, the build uses that contact instead. Each RX group list becomes a group list with the id `gen_grp<n>`.
- Hytera: the build reuses a group call contact of the base with the same number, or adds one with the talkgroup's name. RX group lists are matched by name.

A name that is not defined is refused with its place, for example:

```text
fleet select: sources/own/simplex.yaml: channels[2].tx_talkgroup: talkgroup 'TG98' is not defined in talkgroups.yaml
```
