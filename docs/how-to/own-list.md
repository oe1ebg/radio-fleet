# Add an own channel list

An own list is a YAML file in `sources/own/` of the data root. A radio carries the list when its profile names it in `own_lists`. The keys of a list and its channels are in [reference/data-root.md](../reference/data-root.md#own-lists).

1. Make the file `sources/own/hills.yaml`. The file name without `.yaml` must be the `name` of the list:

   ```yaml
   name: hills
   tags: [portable]
   channels:
     - {name: Hill 2m, rx: 145.550, mode: FM}
     - {name: Hill 70, rx: 433.525, mode: FM, bandwidth: 12.5}
     - name: Hill rpt
       rx: 438.900
       tx: 431.300
       mode: FM
       tone_tx: {ctcss: 77.0}
       tone_rx: {ctcss: 77.0}
   ```

   Frequencies are in MHz and bandwidth in kHz. If you leave out `tx`, it is the same as `rx`.

2. Add the list to each radio that carries it, in `fleet.yaml`:

   ```yaml
   radios:
     uv5r-mini:
       own_lists: [simplex, hills]
   ```

3. Check the result:

   ```sh
   fleet select --radio uv5r-mini
   ```

   ```text
   uv5r-mini (Baofeng UV-5R mini): 8 channels, 0 zones
     2m Call          RX 145.50000 TX 145.50000 FM power 5W [simplex]
     70cm Call        RX 433.50000 TX 433.50000 FM power 5W [simplex]
     Hill 2m          RX 145.55000 TX 145.55000 FM power 5W [hills]
     Hill 70          RX 433.52500 TX 433.52500 FM power 5W [hills]
     Hill rpt         RX 438.90000 TX 431.30000 FM tone TX CTCSS 77 tone RX CTCSS 77 power 5W [hills]
     XX1AA            RX 145.60000 TX 145.00000 FM tone TX CTCSS 88.5 tone RX CTCSS 88.5 power 5W [oevsv-repeater-db]
   ...
   ```

   The channels of the list show its name as the source: `[hills]`. Own lists come first, in the order of `own_lists`, before the upstream channels.

## What to check

- A channel whose mode, RX or TX frequency the radio cannot carry is dropped, with the reason. The region does not apply to own lists.
- A `power` on a channel wins over the `power` of the profile. Use a value that the radio's renderer takes (see the [fleet.yaml reference](../reference/fleet-yaml.md#power)). If one list feeds radios of different renderers, leave `power` out of the list. Otherwise the build of one of them fails, for example:

  ```text
  fleet build: uv5r-mini: channel Hill 2m: CHIRP needs the power in watts, such as 5W, not 'Low'
  ```
- A DMR channel names its talkgroup and RX group list by name. Define them first: see [Talkgroups and RX group lists](talkgroups.md).
- The list's `tags` and the channel's `tags` both go to the channel. A zone rule can select channels by tag or by `source: hills`.

If a radio names a list that has no file, every command that reads the sources fails:

```text
fleet select: fleet.yaml: radios.uv5r-mini.own_lists: no own list 'hills': no file sources/own/hills.yaml
```

If the `name` differs from the file name, the list is refused:

```text
fleet select: sources/own/simple.yaml: name: the list in simple.yaml must be named 'simple'
```
