# Add a radio profile

Each radio has a profile under `radios` in `fleet.yaml`. The profile says which file to build, what the radio can carry, which channels it gets and how to sort them into zones and scan lists. Every key is in the [fleet.yaml reference](../reference/fleet-yaml.md).

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
       power: High
       power_levels: {Max: 25W, High: 25W, Mid: 10W, Low: 5W, Min: 5W}
       naming: {replace: {"Call": "C"}}
   ```

2. Check the selection:

   ```sh
   fleet select --radio rt95-car
   ```

   ```text
   rt95-car (Retevis RT95): 5 channels, 0 zones, 0 scan lists
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
   overrides that match nothing: 0
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
| Baofeng, Retevis (CHIRP) | `chirp` | `power` and `power_levels` in watts |
| Yaesu FT5D (ADMS-14) | `ft5d` | nothing |
| Yaesu FT-3185 (jayt) | `jayt` | `base`, `tools.jayt` |
| Hytera | `hytera` | `base`, `factory`, `tools.hytera` |

Put only modes in `capability.modes` that the renderer carries. A channel of a mode that is not in `modes` is dropped; a channel that the renderer cannot carry fails the build. See [Build and import per radio family](build-and-import.md).

## Capability

- `bands`: each band has an RX range and, for transmit, a TX range, in MHz. A channel is dropped when its RX frequency is in no RX range, or when its TX frequency is in no TX range. Set the TX ranges to the amateur bands you may transmit on. A receive-only channel (`rx_only: true` in an own list) is checked against the RX ranges only; the qdmr and CHIRP renderers write it so that the radio cannot transmit, and the other renderers drop it.
- `channels`: the memory count. Channels beyond it are dropped with `channel limit of N reached`.
- `name_length`: names are cut to this length.
- `zones` and `zone_channels`: the number of zones and the channels per zone. `scan_lists` and `scan_list_channels`: the number of scan lists and the channels per scan list. A limit that you leave out is no limit. Set the radio's limits when the profile has zone or scan-list rules, so that selection drops what the radio cannot hold.

## Region

The region selects upstream channels. It does not apply to own lists. Use one of:

- `{locator: JJ00mm, max_km: 60}`: the repeaters within 60 km of the centre of the Maidenhead locator. A repeater without a position in the snapshot is dropped.
- `{prefixes: [XX1, XX3]}`: the repeaters whose callsign starts with one of the prefixes.

Two optional keys go next to the area:

```yaml
region:
  locator: JJ00mm
  max_km: 60
  modes: {DMR: {locator: JJ00mm, max_km: 150}}
  exclude: {XX1CC: "DCS, which the FT5D output cannot carry"}
```

- `modes` gives some modes another area, here the DMR repeaters within 150 km. A mode that is not named takes the region's area.
- `exclude` names callsigns that the radio never gets, each with the reason. `fleet select` shows the drop: `XX1CC: excluded: DCS, which the FT5D output cannot carry`.

## Zones and scan lists

A zone rule selects channels by `mode`, `band`, `source`, `tag` and `channel` (a name pattern such as `"XX1*"`). Each key takes one value or a list. A channel joins a zone when it meets every key of the rule. One channel can be in several zones.

```yaml
zones:
  - {name: Simplex, source: simplex}
  - {name: FM 2m, mode: FM, band: 2m}
  - {name: Local, channel: ["XX1*", "XX3*"]}
```

The `channel` pattern matches the name after `naming` and after the cut to `name_length`. A rule that matches no channel is dropped with `matches no channel`. The renderers use zones as follows: qdmr and Hytera write zones, the FT5D writes banks 1 to 24, and the CHIRP and jayt renderers do not use them.

Scan-list rules under `scan_lists` take the same keys. Only the qdmr renderer takes scan-list rules; another renderer refuses them when `fleet.yaml` is read. Each generated channel refers to the first scan list that takes it, so the radio scans that list when you start a scan on the channel.

```yaml
scan_lists:
  - {name: FM, mode: FM}
  - {name: DMR, mode: DMR, base_channel: Hotspot}
```

With the qdmr renderer, `base_channel` adds hand-made channels of the base to a zone or scan list by their exact name, before the generated channels. A rule with only a `name` and `base_channel` takes only those channels. The name must belong to exactly one hand-made channel of the base, or the build fails.

Selection keeps at most `capability.zones` zones and `capability.scan_lists` scan lists, and at most `zone_channels` or `scan_list_channels` channels in each; every zone, scan list or member beyond a limit is a drop with its reason.

## Power

Channels carry a power level: `Max`, `High`, `Mid`, `Low` or `Min`. `power` is the level of every channel that does not set its own, and `power_levels` maps each level to the radio's value:

```yaml
power: High
power_levels: {Max: 25W, High: 25W, Mid: 10W, Low: 5W, Min: 5W}
```

| Renderer | Values | Without `power_levels` |
|---|---|---|
| `qdmr` | `Max`, `High`, `Mid`, `Low`, `Min` | each level is its own value |
| `chirp` | watts, such as `5W` or `0.5W`; every channel needs one | no value |
| `jayt` | `LOW`, `LOW2`, `LOW3`, `HIGH` | no value |
| `hytera` | `High`, `Middle`, `Low` | `Max`, `High`: `High`; `Mid`: `Middle`; `Low`, `Min`: `Low` |
| `ft5d` | none: the FT5D writes no power | |

A value the renderer does not take is refused when `fleet.yaml` is read, with the profile and the key. A level that a channel has and the profile does not map fails the selection, with the channel and its list. A `power` that is not a level, such as `power: 25W`, gives every level that value.

## Naming

`naming.upstream` names the upstream channels. `{callsign}` is the callsign, `{band}` the name of the capability band of the RX frequency and `{site}` the snapshot's `name` column. The default is `{callsign}`. A callsign with a repeater on 2 m and one on 70 cm gives two channels of one name; with `{band}`, they differ:

```yaml
naming: {upstream: "{callsign} {band}"}
```

```text
  XX1AA 2m         RX 145.60000 TX 145.00000 FM ...
  XX1AA 70cm       RX 438.65000 TX 431.05000 FM ...
```

`naming.replace` rewrites parts of every channel name, in order, before the cut to `name_length`. Trailing spaces are removed after the cut.

```yaml
naming: {replace: {" TS1 ": " 1 ", " TS2 ": " 2 "}}
```
