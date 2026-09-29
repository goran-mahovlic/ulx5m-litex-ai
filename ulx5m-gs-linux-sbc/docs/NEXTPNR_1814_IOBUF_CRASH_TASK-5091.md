# nextpnr #1814 crash on GateMate `CC_IOBUF` with `FF_IBF=1`, and the upstream fix #1817 (TASK-5090 / TASK-5091)

**28.–29.09.2026.** Problem, cause, minimal repro, fix, and the board test of the Linux SoC built with the fixed nextpnr.

## Problem

nextpnr-himbaechel `3c42800d` (YosysHQ main, #1814 "gatemate: add missing timing check from and to IOSEL") aborts on
the ULX5M-GS Linux SoC right after packing, in the first timing analysis of the placer:

```
terminate called after throwing an instance of 'std::out_of_range'
  what():  dict::at()
```

Backtrace (debug build): `placer_heap → TimingAnalyser::run → walk_backward → set_required_time → dict<domain, ArrivReqTime>::at()`.
The missing domain is on `<iobuf>$iosel.GPIO_EN`, reached backwards from `<iobuf>.T` (`CPE_IOBUF`).
The commit before it (`073bb87e`), built the same way with the same chipdb, does not crash.

It hits every LiteX SoC with SDRAM: LiteX's GateMate SDR tristate for the SDRAM DQ lines is a `CC_IOBUF` with registered
input (`FF_IBF=1`).

## Cause

A mismatch in `himbaechel/uarch/gatemate/delay.cc` that was already there; #1814 only exposes it.

1. `getCellDelay()` for `CPE_IBUF/OBUF/TOBUF/IOBUF` (and the LVDS variants) ended with `return true;`, so every port
   pair not listed (e.g. `T→Y`, `A→Y`) was reported as a combinational arc with zero delay.
2. `getPortTimingClass()` returns `TMG_IGNORE` for `A` and `T`. `TimingAnalyser::get_cell_delays()` skips ignored
   inputs, so the false arc is added only on the output side (`Y` gets fan-in from `T` and `A`), not on the input side.
3. `topo_sort()` builds its edges from the input side only, so there is no `T→Y` edge and `T` can come after `Y`
   in the order.
4. `setup_port_domains()` visits `T` before `Y` has given it its required-time domain, so `T` passes nothing to its
   driver `IOSEL.GPIO_EN`. Later `Y` copies the domain into `T`; in `walk_backward()` `T` pushes it to `GPIO_EN`,
   which has no entry → `dict::at()`.
5. Before #1814 the IOSEL was fully combinational, so `GPIO_EN` got the domain by another path and the problem stayed
   hidden. #1814 makes `GPIO_IN` a registered endpoint (`IN1_FF/IN2_FF`), and now the domain reaches `GPIO_EN` only
   through `Y → T`.

## Minimal repro

`docs/nextpnr_1814_repro/` (`top.v`, `top.ccf`, `run.sh`):

```verilog
module top(input clk, input d, input oe, inout io, output q);
  reg a_q, t_q, r; wire y;
  always @(posedge clk) begin a_q <= d; t_q <= ~oe; r <= y; end
  CC_IOBUF #(.FF_IBF(1'b1), .FF_OBF(1'b1)) u_io (.A(a_q), .T(t_q), .Y(y), .IO(io));
  assign q = r;
endmodule
```

```
NEXTPNR=/path/to/nextpnr-himbaechel docs/nextpnr_1814_repro/run.sh
```

| nextpnr | result |
|---|---|
| `073bb87e` (before #1814) | OK |
| `3c42800d` (#1814) | abort `dict::at()`, rc 134 |
| `ad8527f8` (#1817) | OK, rc 0 |

`FF_IBF=1` crashes with or without `FF_OBF`, with `T` from a FF, from logic or constant; `FF_IBF=0` does not crash.

## Fix

Report only the arcs that really exist through an IO buffer. Our proposed patch (`docs/nextpnr_1814_repro/fix_iobuf_arcs.patch`)
changed the final `return true;` to `return false;` in both IO buffer branches.

Upstream fixed it the same way in **PR #1817** "gatemate: only set IOBUF delays where connection exists" (merged
29.09.2026, main `ad8527f8`): `return false` for unlisted pairs, and the arcs to and from the pad port are recognised as well
(`A/T→IO`, `IO→Y`, LVDS `IO_P/IO_N`).

Possible extra hardening (not upstream): in `common/kernel/timing.cc` `get_cell_delays()`, do not add a combinational
fan-in arc on an output when the input's class is `TMG_IGNORE`, so no uarch can break the topological order this way.

## Board test with the fixed nextpnr (TASK-5091)

nextpnr `ad8527f8` built locally (gatemate uarch only, chipdb from oss-cad-suite 2026-09-28; script
`docs/nextpnr_1814_repro/build_nextpnr_ad8527f.sh`, local paths), Yosys 0.69+154 from oss-cad-suite 2026-09-28. Same design
and `target_soc.py` options as `s_usb5_pll60`. The CSR map is identical, so `rv32_k612.dtb` and the Linux 6.12 images stay valid.

- seed 2: builds, bitstream `ETH_GateMateA1_2909_1015_Linux_GbE_DVI_USBPNRU_pll60s2_np1817.bit` (CFGRST);
- seed 1: stuck in routing (`overused=1` after 1460 iterations), stopped.

| post-route Fmax [MHz] | 28.09. s2 (oss 0928, nextpnr c4fbb55a) | **29.09. s2 (nextpnr ad8527f8)** |
|---|---|---|
| usb_clk (60) | 64.2 | **61.2** |
| grx_clk (125) | 127.8 | **118.3** (fail) |
| gtx0_clk | 43.6 | **46.6** |
| ref_clk | 83.2 | **83.0** |

The numbers are not fully comparable: #1814 adds timing checks to and from the IOSEL, which the older nextpnr did not
analyse at all.

Board (ULX5M-GS, `lxrun.sh`, Image612 + rv32_k612.dtb + rootfs612.cpio), 29.09.2026:

- Linux 6.12 login after 266 s (oss0928 s2: 261 s); USB PNRU keyboard/mouse found (`input0`);
- DVI console with login prompt on the grabber at the start and after 36 min;
- 36 min uptime under constant SDRAM load (`cat` + `md5sum` of an 8 MB file in a loop, load average ~3.5), no reboot;
- ping from the Pi: 300/300 × 1400 B under load, then 1800/1800 × 1400 B over 30 min, 0 % loss, avg 17.6 ms;
- video recoveries (`vrec`) 0, `dmesg` without error/fail/oops.
