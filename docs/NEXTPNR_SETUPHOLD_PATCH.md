# nextpnr-himbaechel GateMate: the "setuphold corners" patch (pu-cc abd0731) — evaluation

TASK-5064, 26.09.2026. Applies to both projects in this repo (`ulx5m-gs-linux-sbc` and `ulx5m-gs-m2-serdes`),
because both are placed and routed with the same `nextpnr-himbaechel` from oss-cad-suite 20260923
(`nextpnr-0.11.1-31-g3edea68e`).

## 1. Verdict

**Do not use the patch. Upstream is correct, and the patch is wrong.**

- The patch assumes the `fast_*` / `slow_*` fields of a GateMate timing entry are PVT corners. They are not.
  The chipdb generator stores **rise in `fast_*` and fall in `slow_*`**. For a combined BRAM `SETUPHOLD`
  entry, rise = **setup** and fall = **hold**. The PVT corner is chosen once for the whole run
  (`--vopt time_mode`, default WORST) and selects a different speed grade in the chipdb.
- The vendor's own SDF (Cologne Chip `p_r`) confirms this ordering value for value (§3.3).
- Effect of abd0731:
  - **CPE flip-flops: none.** Setup and hold are stored with rise == fall (100 ps / 100 ps at worst_spd).
  - **BRAM inputs: setup and hold are swapped.** At worst_spd the BRAM setup check becomes
    **53–942 ps more optimistic** and the hold check the same amount more pessimistic (§4).
- The expectation that "the new nextpnr shows WORSE numbers" does not hold. Two board designs have a critical
  path that ends at a BRAM input. On `usb5_pll60_s1` (grx_clk) the patch would turn a real setup FAIL
  (121.4 MHz at 125 MHz) into a PASS (≈132 MHz). On `grec_3` (rxc) it would report ≈159 instead of 143 MHz (§6.1).
- The patch does **not** make nextpnr report the K22 hold violation (BRAM → FF, CPU does not start).
  The unpatched nextpnr **already** reports it (1 violation, −0.14 ns on `dvistdy_1` / `dvilr0_1`),
  and that check ends at a CPE FF, which the patch does not touch (§7).
- SerDes/BER designs contain no BRAM. The patched binary produces a **byte-identical** routed bitstream
  text for them. It cannot change anything about higher link speeds (§6).

Default in all build scripts stays the oss-cad-suite nextpnr. The `NEXTPNR=` hook exists (§8) and is useful
for testing other nextpnr builds, but it is **not** recommended with the `patched` binary.

## 2. What the patch changes

`himbaechel/uarch/gatemate/delay.cc`, 6 lines:

```diff
 void GateMateImpl::get_setuphold_from_tmg_db(IdString id_setup, IdString id_hold, DelayPair &setup, DelayPair &hold)
-        setup.min_delay = fnd->second->delay.fast_min;   // used for CPE FF: timing_del_Setup_D_L
-        setup.max_delay = fnd->second->delay.fast_max;
+        setup.min_delay = fnd->second->delay.slow_min;
+        setup.max_delay = fnd->second->delay.slow_max;
 void GateMateImpl::get_setuphold_from_tmg_db(IdString id_setuphold, DelayPair &setup, DelayPair &hold)
-        setup = fast_{min,max};  hold = slow_{min,max}     // used for BRAM: timing_RAM_{NOECC,ECC,REG}_SETUPHOLD_n
+        setup = slow_{min,max};  hold = fast_{min,max}
```

Upstream YosysHQ/nextpnr `main` (checked 26.09.2026) still has the original code. abd0731 exists only on
the branch `pu-cc/nextpnr:gatemate-setuphold-fix` (1 commit ahead, 82 behind `YosysHQ:main`). No PR or
issue for it exists upstream.

## 3. Why the premise is wrong

### 3.1 What `fast`/`slow` mean in the GateMate chipdb

`himbaechel/uarch/gatemate/gen/arch_gen.py` (the generator that built the chipdb shipped in oss-cad-suite):

```python
def convert_timing(tim):
    return TimingValue(tim.rise.min, tim.rise.max, tim.fall.min, tim.fall.max)
#   TimingValue(fast_min,     fast_max,     slow_min,     slow_max)   <- himbaechel_dbgen/chip.py
```

`fast_*` holds **rise** and `slow_*` holds **fall**. The PVT corner is a separate chipdb speed grade
(`best_/typ_/worst_` × `lpr/eco/spd`), selected in `gatemate.cc` from `--vopt time_mode` (default 3 = WORST)
and `--vopt fpga_mode` (the LiteX builds use 3 = SPEED → `worst_spd`). Within one run every check uses the
same corner. There is no fast/slow pair inside an entry to choose from.

### 3.2 How prjpeppercorn fills rise/fall for setup/hold

`prjpeppercorn/gatemate/chip.py` (YosysHQ/prjpeppercorn b1eb52f):

```python
def convert_delay_val(d):   # del_Setup_D_L, del_Hold_D_L  (CPE flip-flop)
    return Timing(TimingDelay(d.min, d.typ, d.max), TimingDelay(d.min, d.typ, d.max))   # rise == fall
def convert_ram_delay(d):   # RAM_*_SETUPHOLD_n  (BRAM)
    return Timing(TimingDelay(d.time1...), TimingDelay(d.time2...))                    # rise = time1, fall = time2
```

- CPE FF: the separate setup and hold entries have identical rise and fall. Reading `fast` or `slow` gives the
  same number, so the first hunk of the patch is a no-op.
- BRAM: `time1` / `time2` of the vendor delay record (`Tdel_entry`) end up in rise / fall.

### 3.3 The vendor SDF names time1 = setup, time2 = hold

The Cologne Chip SDF writer (`p_r`, openCologne corescore build, `TIMING MODE: BEST SPEED`) emits
`(SETUPHOLD port clk (setup) (hold))`. Compared with our timing DB at `best_spd`:

| check | vendor SDF setup | vendor SDF hold | our DB time1 (→ rise/`fast`) | our DB time2 (→ fall/`slow`) |
|---|---|---|---|---|
| FPGA_RAM `ADDRA0[*]` → CLOCK1, merged_entry 4 (`RAM_NOECC_SETUPHOLD_1`) | 45:392:740 | −342:3:348 | 45 … 740 | −342 … 348 |
| FPGA_RAM `GLWEA[*]` → CLOCK1, merged_entry 10 (`RAM_NOECC_SETUPHOLD_7`) | 382:468:555 | −77:67:212 | 382 … 555 | −77 … 212 |
| CPE FF `D_IN` → CLK (`del_Setup_D_L` / `del_Hold_D_L`) | 59:59:59 | 59:59:59 | 59 | 59 |

So `fast` = setup and `slow` = hold, which is exactly what upstream reads. The negative minimum values are
typical of hold limits and appear only in `time2`.

Source: `~/app/regoc_system/openCologne/8.StressTest/1.corescore_cc/build/corescore_0/cc_gatemate-gatemate/corescore_0_00.sdf`.

Pin → entry mapping (nextpnr `delay.cc`, NOECC): ADDRA/ADDRB `_1`, CLOCK `_2`, DIA `_3`, DIB `_4`, ENA `_5`,
ENB `_6`, GLWEA `_7`, GLWEB `_8`, WEA `_9`, WEB `_10`. This matches the SDF `merged_entry` numbers
(4 → `_1`, 10 → `_7`, 12 → `_9`; NOECC entry n ↔ `_n-3`).

### 3.4 How nextpnr uses the numbers

`common/kernel/timing.cc`: the endpoint required time uses `setup.maxDelay()` for the setup check and
`hold.maxDelay()` for the hold check. So the effective values are `setup.max_delay` and `hold.max_delay`.

## 4. Effect of abd0731 per timing entry (worst_spd, what the LiteX builds use), ps

| entry | setup (upstream = time1.max) | hold (upstream = time2.max) | setup (abd0731) | hold (abd0731) | setup shift | hold shift |
|---|---|---|---|---|---|---|
| RAM_NOECC_SETUPHOLD_1 | 1350 | 508 | 508 | 1350 | -842 | +842 |
| RAM_NOECC_SETUPHOLD_2 | 269 | 216 | 216 | 269 | -53 | +53 |
| RAM_NOECC_SETUPHOLD_3 | 1174 | 524 | 524 | 1174 | -650 | +650 |
| RAM_NOECC_SETUPHOLD_4 | 1309 | 367 | 367 | 1309 | -942 | +942 |
| RAM_NOECC_SETUPHOLD_5 | 966 | 312 | 312 | 966 | -654 | +654 |
| RAM_NOECC_SETUPHOLD_6 | 996 | 354 | 354 | 996 | -642 | +642 |
| RAM_NOECC_SETUPHOLD_7 | 973 | 310 | 310 | 973 | -663 | +663 |
| RAM_NOECC_SETUPHOLD_8 | 1001 | 294 | 294 | 1001 | -707 | +707 |
| RAM_NOECC_SETUPHOLD_9 | 1356 | 654 | 654 | 1356 | -702 | +702 |
| RAM_NOECC_SETUPHOLD_10 | 1313 | 549 | 549 | 1313 | -764 | +764 |
| CPE FF del_Setup_D_L/del_Hold_D_L | 100 | 100 | 100 | 100 | 0 | 0 |

Negative setup shift = the patched setup check is more optimistic; positive hold shift = the patched hold check is more pessimistic.

ECC and REG variants behave the same (e.g. `RAM_ECC_SETUPHOLD_4`: 1736 / 485 → shift ∓1251 ps).

## 5. Build

Build scripts: `~/app/regoc_system/tools/nextpnr-patched/` (`build.sh`, `compare.sh`, `summarize.py`,
`abd0731.patch`, `README.md`). Install: `~/app/raid/tools/nextpnr-gatemate-setuphold/{vanilla,patched}/bin/`.
oss-cad-suite is not modified.

- Source: YosysHQ/nextpnr `3edea68e` (the commit in oss-cad-suite 20260923), gatemate uarch only, Release, LTO.
  Built twice: `vanilla` (control) and `patched` (+ abd0731).
- Chipdb: the one shipped in oss-cad-suite 20260923 (symlinked). It matches the nextpnr commit, and the local
  `vanilla` build reproduces oss-cad-suite **byte for byte** on every design that finished (routed `.txt`
  sha256 identical; table §6). The comparison therefore isolates the patch from compiler or chipdb differences.
- Built in the container (13 jobs = MemAvailable/2 GB), about 5 min for both flavours.

## 6. Measurements: same input, same seed, three binaries

`compare.sh` runs each design with the exact arguments of its original build script (LiteX:
`--vopt fpga_mode=3 --freq 125 --router router2 --seed N --timing-allow-fail`; BER: `--freq 40` or none).
Fmax values are post-route unless marked. "sha" is sha256 (first 12 hex digits) of the routed `.txt`.

Designs: `ber_gs_od4_s1`, `ber_m2_od2p0e_s1` (SerDes BER, `ulx5m-gs-m2-serdes/gateware/ber/build`);
`soc_grec_3` (Linux+1G+DVI, on the board, works) and `soc_dvistdy_1` / `soc_dvilr0_1` / `soc_dvis16_1`
(2-clock builds, CPU does not start, K22) from `litex-eth-ulx5m-gs-1g-sbc/build`; `soc_usb5_pll60_s1` (the
USB-PNRU build loaded on the board, sha256 `9aeda4dc…`) from `ulx5m-gs-linux-sbc/build`. The task mentions
`s_usb2_pll60`; no build of that name exists, and `s_usb5_pll60_s1` is the pll60 build that was on the board.
`--freq 125` is the global target of the LiteX build scripts, so every clock is reported against 125 MHz except
the ones with their own constraint (sys = `debugCd_external_clk` 20/16 MHz, usb_clk 60 MHz).
`secs` is the P&R wall time. `rc=143` = killed by me.

**Summary of the table**
- `oss` == `vanilla` everywhere (same sha, same numbers): the local build is a faithful control.
- BER (no BRAM): `patched` == `oss` byte for byte.
- SoC: `patched` produces a different placement and routing (different sha), so its numbers are a different
  design, not a re-analysis. It is not better: grec_3 rxc 143.0 PASS → 102.8 FAIL, dvis16 ref_clk 112.7 → 80.7,
  hdmi5x 160.9 PASS → 116.7 FAIL. On `usb5_pll60_s1` the router did not converge (stuck at `overuse=1` for
  1910 iterations, 32 min, killed). On `grec_3` it needed 1562 s against 766 s.
- Hold: the oss/vanilla violations on the K22 builds disappear in `patched` only because the placement differs (§7).

#### ber_gs_od4_s1

| metric | oss | vanilla | patched |
|---|---|---|---|
| rc | rc=0 secs=159 | rc=0 secs=157 | rc=0 secs=163 |
| routed .txt sha256 | d3157c3452cc | d3157c3452cc | d3157c3452cc |
| hold violations | 0 | 0 | 0 |
| worst hold slack (ns) | - | - | - |
| post-route Fmax u.clk_i (MHz) | 35.22 PASS @12 | 35.22 PASS @12 | 35.22 PASS @12 |
| post-route Fmax u.rclk (MHz) | 32.81 PASS @12 | 32.81 PASS @12 | 32.81 PASS @12 |
| post-route Fmax u.tclk (MHz) | 89.22 PASS @12 | 89.22 PASS @12 | 89.22 PASS @12 |
| post-place Fmax u.clk_i (MHz) | 46.97 PASS @12 | 46.97 PASS @12 | 46.97 PASS @12 |
| post-place Fmax u.rclk (MHz) | 42.00 PASS @12 | 42.00 PASS @12 | 42.00 PASS @12 |
| post-place Fmax u.tclk (MHz) | 156.18 PASS @12 | 156.18 PASS @12 | 156.18 PASS @12 |

#### ber_m2_od2p0e_s1

| metric | oss | vanilla | patched |
|---|---|---|---|
| rc | rc=0 secs=45 | rc=0 secs=44 | rc=0 secs=43 |
| routed .txt sha256 | b90f6c520a74 | b90f6c520a74 | b90f6c520a74 |
| hold violations | 0 | 0 | 0 |
| worst hold slack (ns) | - | - | - |
| post-route Fmax u.clk_i (MHz) | 121.71 PASS @40 | 121.71 PASS @40 | 121.71 PASS @40 |
| post-route Fmax u.rclk (MHz) | 66.41 PASS @40 | 66.41 PASS @40 | 66.41 PASS @40 |
| post-route Fmax u.tclk (MHz) | 84.17 PASS @40 | 84.17 PASS @40 | 84.17 PASS @40 |
| post-place Fmax u.clk_i (MHz) | 313.77 PASS @40 | 313.77 PASS @40 | 313.77 PASS @40 |
| post-place Fmax u.rclk (MHz) | 106.88 PASS @40 | 106.88 PASS @40 | 106.88 PASS @40 |
| post-place Fmax u.tclk (MHz) | 167.59 PASS @40 | 167.59 PASS @40 | 167.59 PASS @40 |

#### soc_dvilr0_1

| metric | oss | vanilla | patched |
|---|---|---|---|
| rc | rc=0 secs=610 | rc=0 secs=609 | rc=0 secs=966 |
| routed .txt sha256 | 017eab8f8aba | 017eab8f8aba | f8c2c7a5203a |
| hold violations | 1 | 1 | 0 |
| worst hold slack (ns) | -0.14 | -0.14 | - |
| post-route Fmax debugCd_external_clk (MHz) | 22.20 PASS @20 | 22.20 PASS @20 | 22.46 PASS @20 |
| post-route Fmax hdmi5x_clk (MHz) | 131.98 PASS @125 | 131.98 PASS @125 | 117.47 FAIL @125 |
| post-route Fmax hdmi_clk (MHz) | 43.36 FAIL @125 | 43.36 FAIL @125 | 48.16 FAIL @125 |
| post-route Fmax ref_clk (MHz) | 97.54 FAIL @125 | 97.54 FAIL @125 | 94.98 FAIL @125 |
| post-place Fmax debugCd_external_clk (MHz) | 31.48 PASS @20 | 31.48 PASS @20 | 32.46 PASS @20 |
| post-place Fmax hdmi5x_clk (MHz) | 290.53 PASS @125 | 290.53 PASS @125 | 235.68 PASS @125 |
| post-place Fmax hdmi_clk (MHz) | 51.27 FAIL @125 | 51.27 FAIL @125 | 73.24 FAIL @125 |
| post-place Fmax ref_clk (MHz) | 127.94 PASS @125 | 127.94 PASS @125 | 181.75 PASS @125 |

#### soc_dvis16_1

| metric | oss | vanilla | patched |
|---|---|---|---|
| rc | rc=0 secs=777 | rc=0 secs=762 | rc=0 secs=879 |
| routed .txt sha256 | e4e7ceab3368 | e4e7ceab3368 | 096d38fa572f |
| hold violations | 2 | 2 | 0 |
| worst hold slack (ns) | -0.24 | -0.24 | - |
| post-route Fmax debugCd_external_clk (MHz) | 22.44 PASS @16 | 22.44 PASS @16 | 24.52 PASS @16 |
| post-route Fmax hdmi5x_clk (MHz) | 160.85 PASS @125 | 160.85 PASS @125 | 116.66 FAIL @125 |
| post-route Fmax hdmi_clk (MHz) | 49.68 FAIL @125 | 49.68 FAIL @125 | 49.17 FAIL @125 |
| post-route Fmax ref_clk (MHz) | 112.70 FAIL @125 | 112.70 FAIL @125 | 80.72 FAIL @125 |
| post-place Fmax debugCd_external_clk (MHz) | 28.96 PASS @16 | 28.96 PASS @16 | 25.84 PASS @16 |
| post-place Fmax hdmi5x_clk (MHz) | 324.25 PASS @125 | 324.25 PASS @125 | 188.57 PASS @125 |
| post-place Fmax hdmi_clk (MHz) | 48.27 FAIL @125 | 48.27 FAIL @125 | 65.98 FAIL @125 |
| post-place Fmax ref_clk (MHz) | 156.05 PASS @125 | 156.05 PASS @125 | 107.79 FAIL @125 |

#### soc_dvistdy_1

| metric | oss | vanilla | patched |
|---|---|---|---|
| rc | rc=0 secs=527 | rc=0 secs=515 | rc=0 secs=880 |
| routed .txt sha256 | 8e341e2ea762 | 8e341e2ea762 | 7e3f1181f17e |
| hold violations | 1 | 1 | 0 |
| worst hold slack (ns) | -0.14 | -0.14 | - |
| post-route Fmax debugCd_external_clk (MHz) | 22.20 PASS @20 | 22.20 PASS @20 | 22.46 PASS @20 |
| post-route Fmax hdmi5x_clk (MHz) | 131.98 PASS @125 | 131.98 PASS @125 | 117.47 FAIL @125 |
| post-route Fmax hdmi_clk (MHz) | 43.36 FAIL @125 | 43.36 FAIL @125 | 48.16 FAIL @125 |
| post-route Fmax ref_clk (MHz) | 97.54 FAIL @125 | 97.54 FAIL @125 | 94.98 FAIL @125 |
| post-place Fmax debugCd_external_clk (MHz) | 31.48 PASS @20 | 31.48 PASS @20 | 32.46 PASS @20 |
| post-place Fmax hdmi5x_clk (MHz) | 290.53 PASS @125 | 290.53 PASS @125 | 235.68 PASS @125 |
| post-place Fmax hdmi_clk (MHz) | 51.27 FAIL @125 | 51.27 FAIL @125 | 73.24 FAIL @125 |
| post-place Fmax ref_clk (MHz) | 127.94 PASS @125 | 127.94 PASS @125 | 181.75 PASS @125 |

#### soc_grec_3

| metric | oss | vanilla | patched |
|---|---|---|---|
| rc | rc=0 secs=856 | rc=0 secs=766 | rc=0 secs=1562 |
| routed .txt sha256 | 42df499508f1 | 42df499508f1 | bce8eeafed53 |
| hold violations | 0 | 0 | 0 |
| worst hold slack (ns) | - | - | - |
| post-route Fmax debugCd_external_clk (MHz) | 22.39 PASS @20 | 22.39 PASS @20 | 23.15 PASS @20 |
| post-route Fmax gtx0_clk (MHz) | 44.36 FAIL @125 | 44.36 FAIL @125 | 38.59 FAIL @125 |
| post-route Fmax mdio_core.rxc (MHz) | 143.04 PASS @125 | 143.04 PASS @125 | 102.84 FAIL @125 |
| post-route Fmax ref_clk (MHz) | 97.35 FAIL @125 | 97.35 FAIL @125 | 100.52 FAIL @125 |
| post-place Fmax debugCd_external_clk (MHz) | 25.04 PASS @20 | 25.04 PASS @20 | 26.19 PASS @20 |
| post-place Fmax gtx0_clk (MHz) | 65.69 FAIL @125 | 65.69 FAIL @125 | 59.86 FAIL @125 |
| post-place Fmax mdio_core.rxc (MHz) | 213.17 PASS @125 | 213.17 PASS @125 | 205.47 PASS @125 |
| post-place Fmax ref_clk (MHz) | 200.88 PASS @125 | 200.88 PASS @125 | 219.01 PASS @125 |

#### soc_usb5_pll60_s1

| metric | oss | vanilla | patched |
|---|---|---|---|
| rc | rc=0 secs=792 | rc=0 secs=773 | rc=143 secs=1901 |
| routed .txt sha256 | 9f3c4acff181 | 9f3c4acff181 | None |
| hold violations | 0 | 0 | 0 |
| worst hold slack (ns) | - | - | - |
| post-route Fmax debugCd_external_clk (MHz) | 24.89 PASS @20 | 24.89 PASS @20 | - |
| post-route Fmax grx_clk (MHz) | 121.36 FAIL @125 | 121.36 FAIL @125 | - |
| post-route Fmax gtx0_clk (MHz) | 45.59 FAIL @125 | 45.59 FAIL @125 | - |
| post-route Fmax ref_clk (MHz) | 104.91 FAIL @125 | 104.91 FAIL @125 | - |
| post-route Fmax usb_clk (MHz) | 64.61 PASS @60 | 64.61 PASS @60 | - |
| post-place Fmax debugCd_external_clk (MHz) | 25.09 PASS @20 | 25.09 PASS @20 | 26.05 PASS @20 |
| post-place Fmax grx_clk (MHz) | 159.57 PASS @125 | 159.57 PASS @125 | 171.17 PASS @125 |
| post-place Fmax gtx0_clk (MHz) | 65.74 FAIL @125 | 65.74 FAIL @125 | 55.63 FAIL @125 |
| post-place Fmax ref_clk (MHz) | 184.64 PASS @125 | 184.64 PASS @125 | 151.15 PASS @125 |
| post-place Fmax usb_clk (MHz) | 98.94 PASS @60 | 98.94 PASS @60 | 103.93 PASS @60 |

### 6.1 Why the patched column is not a like-for-like STA comparison

The placer and router are timing driven. As soon as the BRAM setup/hold values change, the patched binary
places differently. The patched runs are therefore different designs. I also tried `--no-tmdriv` on vanilla and
patched to force identical placement. The logs still diverge at the first initial-placer iteration
(`wirelen = 38985` vs `39015` on grec_3), because the gatemate uarch uses timing outside that flag, so that
experiment was dropped.

A pure STA re-analysis of the vanilla-routed netlist with the patched timing model is not possible either:
re-loading the routed JSON (`--no-pack --no-place`) segfaults in the gatemate uarch.

The effect on identical routing is therefore **projected from the vanilla critical paths**. Only a path that
ends at a BRAM input can move:

| design / clock (vanilla = oss) | path | endpoint setup used by upstream | abd0731 would use | reported → projected |
|---|---|---|---|---|
| `usb5_pll60_s1` / grx_clk (125 MHz) | 8.24 ns, ends at `mem_3.GLWEA[0]` | 0.97 ns (`_7` setup) | 0.31 ns (`_7` hold) | 121.4 MHz **FAIL** → ≈132 MHz **PASS** (false) |
| `grec_3` / mdio_core.rxc (125 MHz) | 6.99 ns, ends at `mem_3.WEA[2]` | 1.36 ns (`_9` setup) | 0.65 ns (`_9` hold) | 143.0 MHz → ≈159 MHz |
| all other clocks of all designs | end at a CPE FF (setup 0.10 ns) | 0.10 | 0.10 | unchanged |

All BER designs end at CPE FFs and contain no BRAM at all (RAM_HALF 0/64), which is why their routed output is
byte-identical in all three binaries.

## 7. The K22 hold violation (2-clock builds where the CPU does not start)

| build | oss | vanilla | patched (different placement) |
|---|---|---|---|
| `dvistdy_1` | 1 violation, −0.14 ns (clk-skew −3.74 ns) | identical to oss (same sha) | 0 |
| `dvilr0_1` | 1 violation, −0.14 ns (clk-skew −3.74 ns) | identical to oss (same sha) | 0 |
| `dvis16_1` | 2 violations, −0.24 / −0.17 ns (clk-skew −3.89 / −3.55 ns) | identical to oss (same sha) | 0 |

All four violating paths end at a CPE FF `DIN` with `hold -0.10`. The `dvistdy_1` path in detail (vanilla/oss): `debugCd_external_clk` clk-skew −3.74 ns, source
`IBusCachedPlugin_cache.banks_0 DOB[31]` (BRAM clk-to-out 2.34 ns), sink a CPE FF `DIN` with
`hold -0.10` (= `del_Hold_D_L` 100 ps). The check ends at a **CPE FF**, whose hold value the patch does not
change. On the same routing the patched binary would report exactly the same −0.14 ns. The patched run
shows 0 violations only because it placed the design differently, not because it detects anything better.
The tool we already use detects K22. What remains valid is the gate from LESSONS K22 (`grep -c 'Hold/min time
violation for' log` must be 0).

**(c) Designs that work on the board** (`grec_3`, `usb5_pll60_s1`): the oss/vanilla report for them is unchanged
(0 hold violations, the Fmax values above). The patched binary does not re-judge these bitstreams, because it
builds different ones. Its grec_3 comes out worse (rxc 102.8 MHz FAIL, gtx0 38.6 MHz), and its pll60 s1 does
not route. The only change the patch would make to their *existing* routing is the projection in §6.1:
the BRAM-ended grx/rxc paths look 0.66–0.70 ns better than they are.

## 8. Build-script integration (optional; default unchanged)

- `ulx5m-gs-linux-sbc/env.sh` and `litex-eth-ulx5m-gs-1g-sbc/env.sh`: if `NEXTPNR=<path to nextpnr-himbaechel>`
  is set, its directory goes first on PATH (LiteX calls the tool by name). An invalid path prints a warning and
  falls back to oss-cad-suite.
- `tools/soc_build.sh` (both repos): the first line of `~/.tmp/t5032/soc_<name>.log` is now
  `[soc_build] nextpnr=<path actually used>`.
- `build_ber.sh` (`ulx5m-gs-m2-serdes/gateware/ber/` and `regoc_system/docs/ulx5m-serdes/gw/`):
  `"${NEXTPNR:-nextpnr-himbaechel}"`.

```bash
NEXTPNR=$HOME/app/raid/tools/nextpnr-gatemate-setuphold/vanilla/bin/nextpnr-himbaechel tools/soc_build.sh x ...
```

Recommendation after measuring: **leave `NEXTPNR` unset** (oss-cad-suite). The patched binary makes BRAM
setup optimistic and hides real failures (grx_clk on `usb5_pll60_s1`).

## 9. Upstream: proposed text (NOT sent; waiting for Goran's approval)

The patch was never proposed upstream. Opening a PR would be wrong. The useful action is a short note to the
author on the fork branch, so it does not get submitted:

> **Re: `gatemate: fix setuphold corners` (abd0731, branch gatemate-setuphold-fix)**
>
> We built nextpnr 3edea68e with and without this commit and compared it on several GateMate designs.
> We believe the original code is correct and this commit should not be merged:
>
> - In `gen/arch_gen.py`, `convert_timing()` stores `rise` in `fast_*` and `fall` in `slow_*`. These are not
>   PVT corners. The corner is the chipdb speed grade chosen by `time_mode`/`fpga_mode`.
> - prjpeppercorn fills `del_Setup_D_L`/`del_Hold_D_L` with rise == fall (`convert_delay_val`), so the first
>   hunk is a no-op.
> - For BRAM, `convert_ram_delay()` maps `time1` → rise and `time2` → fall. Cologne Chip's own SDF writer emits
>   `(SETUPHOLD ADDRA0[15] CLOCK1 (45:392:740) (-342:3:348))` at BEST SPEED. That matches
>   `RAM_NOECC_SETUPHOLD_1` time1 = 45..740 and time2 = −342..348, so time1 is setup and time2 is hold, which
>   is what the current code reads.
> - With the commit, the BRAM setup check at worst_spd becomes 53–942 ps (NOECC) / up to 1251 ps (ECC) too
>   optimistic. On one of our designs a real 125 MHz setup failure at `GLWEA` (8.24 ns path, 0.97 ns setup)
>   would be reported as a pass.
>
> Happy to share logs and the comparison script.

## 10. Reproduce

```bash
T=~/app/regoc_system/tools/nextpnr-patched
$T/build.sh all                                    # ~5 min
S=~/app/litex-eth-ulx5m-gs-1g-sbc/build/s_grec_3/gateware
$T/compare.sh soc_grec_3 $S/intergalaktik_ulx5m_gs.json $S/intergalaktik_ulx5m_gs.ccf 3 --vopt fpga_mode=3 --freq 125
python3 $T/summarize.py ~/app/raid/tools/nextpnr-gatemate-setuphold/cmp --md
# timing DB values (rise/fall = time1/time2):
cd ~/app/regoc_system/prjpeppercorn/gatemate && python3 -c "import chip; t=chip.get_timings('worst_spd'); print(t['RAM_NOECC_SETUPHOLD_1'])"
```
