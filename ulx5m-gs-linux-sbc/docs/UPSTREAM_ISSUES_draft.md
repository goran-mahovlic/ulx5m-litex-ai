# gatemate: negedge CC_DFF merged into IOSEL (FF_OBF / FF_IBF) loses clock inversion

**nextpnr:** `nextpnr-0.11.1-31-g3edea68e` (oss-cad-suite 2026-09-23); the code path is unchanged in master `24781ef` (2026-09-24)
**yosys:** 0.69+136
**Device:** CCGM1A1 (GateMate A1)

## Summary
When a flip-flop clocked on the **falling edge** drives an output pad with `FF_OBF=true`, nextpnr merges the FF into the IOSEL but **drops the clock inversion**. The IO FF then silently runs on the **rising** edge. No warning is printed and timing reports PASS.

## Minimal reproduction
`neg.v`
```verilog
module top(input clk25, input d, output q_neg, output q_pos);
  reg a = 0, b = 0;
  always @(negedge clk25) a <= d;
  always @(posedge clk25) b <= d;
  assign q_neg = a; assign q_pos = b;
endmodule
```
`neg.ccf`
```
Net "clk25" Loc = "IO_SB_A8";
Net "d"     Loc = "IO_EB_A8";
Net "q_neg" Loc = "IO_EB_B2" | FF_OBF=true;
Net "q_pos" Loc = "IO_EB_A2" | FF_OBF=true;
```
```sh
yosys -q -p "read_verilog neg.v; synth_gatemate -top top; write_json neg.json"
nextpnr-himbaechel --device CCGM1A1 --json neg.json --vopt ccf=neg.ccf --vopt out=neg.txt --write neg.r.json
```
**Expected:** the IOSEL cell for `q_neg` has `INV_OUT1_CLOCK=1`.
**Actual:**
```
q_neg IOSEL: {'OUT_CLOCK': '00', 'OUT1_FF': '1', 'OUT_SIGNAL': '1', 'DELAY_OBF': '0000000000000001', 'SLEW': '1', 'OE_ENABLE': '1'}
```
`INV_OUT1_CLOCK` is missing, so `q_neg` behaves exactly like `q_pos`. Without `FF_OBF` (FF stays in a CPE) the negedge behaviour is correct.

## Root cause (reading the source)
- `GateMatePacker::cleanup()` (pack.cc) calls `dff_update_params()`, which calls `dff_to_cpe()` (pack_cpe.cc) on **every** `CC_DFF`.
- `dff_to_cpe()` converts `CLK_INV` into `C_CPE_CLK` and then does `dff->unsetParam(id_CLK_INV)`.
- `pack_io_sel()` runs **later** (pack.cc, after `pack_bufg()`). When it merges the DFF into the IOSEL (pack_io.cc ~l. 528 for outputs, ~l. 453 for inputs), it reads `bool_or_default(dff->params, id_CLK_INV, 0)`. That parameter has already been removed, so it gets 0, and `INV_OUT1_CLOCK` / `INV_IN1_CLOCK` are never set.
- The input path (`FF_IBF`) should be affected the same way. The ODDR/IDDR paths read `CLK_INV` from the DDR cell, so they are not affected.

## Possible fix
In `pack_io_sel()`, derive the inversion from `C_CPE_CLK` (`0b01` = inverted clock) when `CLK_INV` is absent. Alternatively, skip `dff_to_cpe()` for DFFs that will be merged into an IOSEL, or run the conversion after `pack_io_sel()`.

## Impact
We hit this in an RGMII design, where TXC was generated with a negedge IO FF to get a 90° phase shift relative to TXD. The PHY received TXC edge-aligned with the data and dropped the frames, while timing reported PASS. Our workaround is a posedge IO FF on a PLL CLK180 output.

---

# (2) LiteEth `last_be = 0` → FCS 00000000 for frames > 60 B — NOT an upstream bug (version mismatch)
**Do not report upstream.** Kept here so nobody reports it by mistake.

- LiteEth `40dfb7a` (2026-09-18, PR #226) switched to LiteX's `Packetizer`/`Depacketizer`.
- LiteX added `last_be` support to `Packetizer`/`Depacketizer` the **same day**, in `7fca6dba` (2026-09-18).
- Our build used LiteEth `9654767` (after #226) with an **old LiteX `52f183ef6` (2026-03-17)**, whose `Packetizer` does not drive `last_be`.
- With `core_dw == phy_dw == 8`, `LiteEthMAC` inserts no `TXLastBE` stage (`add_last_be()` only runs when `core_dw > phy_dw`, `mac/core.py`). As a result, the CRC inserter (`mac/crc.py`, `If(sink.last_be[e], …)`) never sees the end of the frame, and frames > 60 B go out with FCS = 0. Frames ≤ 60 B are rescued by the padding inserter.
- Check: `grep -n last_be litex/soc/interconnect/packet.py` finds nothing in LiteX 52f183ef6 and does find `last_be` in LiteX ≥ 7fca6dba.
- Fix on our side: update LiteX to ≥ 7fca6dba. The local workaround `TXLastBE8` (`gateware/eth_stack.py`) can then be removed.
- Optional (low priority): suggest that LiteEth state the minimum LiteX version it needs.

---

# (TASK-5032, draft, NOT yet isolated) gatemate: TimingAnalyser `dict::at` when a PLL clock reaches an output pad through a LUT

**nextpnr:** `nextpnr-0.11.1-31-g3edea68e`. **Backtrace** (LD_PRELOAD `__cxa_throw` hook): `dict<int,ArrivReqTime>::at` <- `TimingAnalyser::set_required_time` <- `walk_backward` <- `TimingAnalyser::run` <- `placer_heap` <- `Arch::place`.
Seen in the full GbE design (LiteEth + 125 MHz RGMII) for TXC = `~CLK0`, `CLK0` (LUT buffer), `~CLK90`, a runtime 4:1 clock mux, and TXC = PLL `CLK270`; every seed tried. TXC = `CLK90` directly builds.
A minimal PLL -> inverter -> pad design does **not** crash, so the trigger is not isolated yet. Do not file until a small repro exists.
