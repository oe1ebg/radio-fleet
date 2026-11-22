# Add a radio profile

Each radio has a profile under `radios` in `fleet.yaml`. The profile says which file to build, what the radio can carry, which channels it gets and how to sort them into zones. Every key is in the [fleet.yaml reference](../reference/fleet-yaml.md).

This guide adds a second Retevis RT95 that carries the repeaters within 60 km of a locator.

1. Add the profile under `radios`. The key (`rt95-car`) is the radio id that the commands use:

   ```yaml
   radios:
     rt95-car:
       model: Retevis RT95
       renderer: chirp
       capability:
         bands:
           - {name: 2m, rx: [136, 174], tx: [144, 146]}
           - {name: 70cm, rx: [400, 480], tx: [430, 440]}
         modes: [FM]
         channels: 200
         name_length: 6
       region: {locator: JJ00mm, max_km: 60}
       own_lists: [simplex]
       power: 25W
       naming: {replace: {"Call": "C"}}
   ```

2. Check the selection:

   ```sh
   fleet select --radio rt95-car
   ```

   ```text
   rt95-car (Retevis RT95): 5 channels, 0 zones
     2m C             RX 145.50000 TX 145.50000 FM power 25W [simplex]
     70cm C           RX 433.50000 TX 433.50000 FM power 25W [simplex]
     XX1AA            RX 145.60000 TX 145.00000 FM tone TX CTCSS 88.5 tone RX CTCSS 88.5 power 25W [oevsv-repeater-db]
     XX1CC            RX 438.62500 TX 431.02500 FM tone TX DCS 023 power 25W [oevsv-repeater-db]
     XX3DD            RX 145.66250 TX 145.06250 FM tone TX CTCSS 123 power 25W [oevsv-repeater-db]
   drops: 6
     XX5FF: 310 km from JJ00mm, beyond 60 km
     DMR Simplex: mode DMR not supported
     C4FM Call: mode C4FM not supported
     XX1BB: mode DMR not supported
     XX1CC: mode C4FM not supported
     XX3EE: TX 445.00000 MHz outside the TX bands
   overrides: 0
   ```

3. Read every drop. If a channel is dropped that the radio should carry, change the profile and run `fleet select` again.

4. Build it:

   ```sh
   fleet build --radio rt95-car
   ```

   ```text
   rt95-car: build/rt95-car/rt95-car.csv
   ```

## Choose the renderer

| Radio family | `renderer` | Also needs |
|---|---|---|
| AnyTone (qdmr) | `qdmr` | `base`, `dmrconf_radio` |
| Baofeng, Retevis (CHIRP) | `chirp` | `power` in watts |
| Yaesu FT5D (ADMS-14) | `ft5d` | nothing |
| Yaesu FT-3185 (jayt) | `jayt` | `base`, `tools.jayt` |
| Hytera | `hytera` | `base`, `factory`, `tools.hytera` |

Put only modes in `capability.modes` that the renderer carries. A channel of a mode that is not in `modes` is dropped; a channel that the renderer cannot carry fails the build. See [Build and import per radio family](build-and-import.md).

## Capability

- `bands`: each band has an RX range and, for transmit, a TX range, in MHz. A channel is dropped when its RX frequency is in no RX range, or when its TX frequency is in no TX range. Set the TX ranges to the amateur bands you may transmit on.
- `channels`: the memory count. Channels beyond it are dropped with `channel limit of N reached`.
- `name_length`: names are cut to this length.
- `zones` and `zone_channels`: the number of zones and the channels per zone. Both are 0 when you leave them out. Set both when the profile has zone rules.

## Region

The region selects upstream channels. It does not apply to own lists. Use one of:

- `{locator: JJ00mm, max_km: 60}`: the repeaters within 60 km of the centre of the Maidenhead locator. A repeater without a position in the snapshot is dropped.
- `{prefixes: [XX1, XX3]}`: the repeaters whose callsign starts with one of the prefixes.

## Zones

A zone rule selects channels by `mode`, `band`, `source`, `tag` and `channel` (a name pattern such as `"XX1*"`). Each key takes one value or a list. A channel joins a zone when it meets every key of the rule. One channel can be in several zones.

```yaml
zones:
  - {name: Simplex, source: simplex}
  - {name: FM 2m, mode: FM, band: 2m}
  - {name: Local, channel: ["XX1*", "XX3*"]}
```

The `channel` pattern matches the name after `naming` and after the cut to `name_length`. A rule that matches no channel is dropped with `matches no channel`. The renderers use zones as follows: qdmr and Hytera write zones, the FT5D writes banks 1 to 24, and the CHIRP and jayt renderers do not use them.

## Power

`power` is the power of every channel that does not set its own. Each renderer takes other values:

| Renderer | Values |
|---|---|
| `qdmr` | `Max`, `High`, `Mid`, `Low`, `Min` |
| `chirp` | watts, such as `5W` or `0.5W`; required |
| `jayt` | `LOW`, `LOW2`, `LOW3`, `HIGH` |
| `hytera` | `High`, `Middle`, `Low` |
| `ft5d` | not used |

## Naming

`naming.replace` rewrites parts of the channel names, in order, before the cut to `name_length`. Trailing spaces are removed after the cut.

```yaml
naming: {replace: {" TS1 ": " 1 ", " TS2 ": " 2 "}}
```
