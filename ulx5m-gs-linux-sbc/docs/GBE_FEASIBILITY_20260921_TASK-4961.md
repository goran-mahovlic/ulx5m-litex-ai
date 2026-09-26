# ULX5M-GS: feasibility of 1 Gbps Ethernet (TASK-4961, 2026-09-21)

Author: Grga (REGOČ Designer) · Project: PRJ-033 (belongs to the FPGA/ULX5M-GS work — not to the inbox)
Repo: `/home/klaudio/app/litex-eth-ulx5m-gs/litex-eth-ulx5m-gs`
Tools: oss-cad-suite (`nextpnr-0.10-45-g98c18d7`), LiteX `52f183ef6`, LiteEth `9654767`

---

## 0. Summary in three sentences

1. **GbE does not close timing today**: it needs 125 MHz, and after routing we measured **60.45 MHz (RX)** and
   **61.93 MHz (TX)** — a shortfall of **≈ 2.0×**. The bottleneck is NOT the RGMII outputs nor the
   RXC pin, but the **gray counters of the LiteEth async FIFOs**, and mostly **routing**
   (12.96 ns of 16.54 ns = 78%).
2. **There is an older, more serious fault that also blocks 100 Mbps**: **nobody gives the KSZ9031 a
   reference clock**. Oscillator X1 and its series resistor R104 are **both
   `dnp`** on the ULX5M-GS, and pin XI hangs on net `ETH_CLK`, which goes **only to FPGA pin IO_EB_A3** —
   which the gateware so far has never driven. This also explains "the board is silent" (TASK-4959)
   and MDIO returning 0x0000.
3. Delivered: the `--gbe` flag (29 changed lines in total) and **driving the 25 MHz reference
   clock on IO_EB_A3** (`--no-phy-refclk` turns it off). The default 100 Mbps build with refclk passes
   timing and produces a bitstream (453 676 B, md5 `fdc72cb175520564f72b82edb49215f0`) — this is
   what should go on the board first. The GbE build passes on seed 7 **without** refclk;
   with refclk the router fails, so gigabit stays a measurement result, not a deliverable.

---

## 1. What was measured (nextpnr, post-route, worst corner)

| Build | eth_tx (PLL#1) | eth_rx (RXC) | sys (PLL#2) | result |
|---|---|---|---|---|
| 100M baseline (before the patch), seed 7 | 57.61 MHz @ 25 | 79.80 MHz @ 25 | 30.92 MHz @ 16 | PASS |
| 100M after the patch (regression), seed 7 | 52.80 MHz @ 25 | 68.67 MHz @ 25 | 27.85 MHz @ 16 | PASS |
| **GbE `--gbe`, seed 7** | **61.93 MHz @ 125** | **60.45 MHz @ 125** | 29.13 MHz @ 16 | **FAIL** |

GbE needs 125 MHz in both PHY domains. Shortfall: **125 / 61.93 = 2.02×** (TX) and
**125 / 60.45 = 2.07×** (RX).

### 1.3 Measurement table (nextpnr, worst corner, `--freq 125`)

| Seed | phase | eth_tx (PLL#1 @125) | eth_rx (RXC @125) | sys (PLL#2 @16) | PnR result |
|---|---|---|---|---|---|
| 7 | after placement | 104.09 | 107.17 | 37.46 | — |
| 7 | **after routing** | **61.93 FAIL** | **60.45 FAIL** | 29.13 PASS | rc=0 |
| 1 | after placement | 115.59 | 103.71 | 38.31 | — |
| 1 | **after routing** | **59.15 FAIL** | **62.89 FAIL** | 28.92 PASS | rc=0 |
| 3 | after placement | 126.50 PASS | 94.86 | 38.30 | — |
| 3 | **after routing** | **52.82 FAIL** | **65.50 FAIL** | 27.37 PASS | rc=0 |
| 11 | after placement | 123.38 | 108.52 | 40.08 | **rc=255 — router failed** |

Two things are visible right away:

1. **The seed does not close the gap.** After routing the range is 52.8–65.5 MHz; 125 is needed. No
   seed comes even close.
2. **Placement lies.** The post-placement estimate (95–127 MHz) is 1.7–2.4× more optimistic
   than the real post-routing result. Whoever looks only at the first nextpnr table thinks
   gigabit is within reach. It is not.

### 1.4 The cost of a global clock on RXC

`rxc_global=True` means Yosys may place a `CC_BUFG` on RXC. Evidence that this works
(Kosjenka's finding, independently confirmed here on this design):

```
100 Mbps build (clkbuf_inhibit):   Inserting CC_BUFG on ...crg_gatematepll1_clkout[0]
                                   Inserting CC_BUFG on ...crg_gatematepll0_clkout[0]
                                        2   CC_BUFG
GbE build     (rxc_global):        Inserting CC_BUFG on ...eth_rx_clk[0]        <---
                                   Inserting CC_BUFG on ...crg_gatematepll1_clkout[0]
                                   Inserting CC_BUFG on ...crg_gatematepll0_clkout[0]
                                        3   CC_BUFG
```

The build runs through to a bitstream — **CC_BUFG on the non-clock pin IO_EB_A7 does not crash nextpnr.**
But it has a cost: the third global clock uses an extra GLBOUT, and because of that seed 11 **no longer
routes**:

```
Info:   failed to find a route using dedicated resources. GLBOUT0 -> X111Y129/CPE.CLK_int
ERROR:  Failed to route arc 654.0 of net 'crg_gatematepll1_clkout' ...
```

So the old note ("CC_BUFG on RXC crashes nextpnr") is **wrong as a cause**, but the
observed fragility was real — only the cause was a lack of global clock resources, not
the pin itself.

### 1.1 Where exactly it fails

The critical path is NOT the RGMII serdes nor the DDR on the pads — in both domains it is the **gray counters
of the LiteEth async FIFOs at the MAC boundary**:

```
eth_rx (16,54 ns, needs ≤ 8,00 ns):   3,58 ns logic + 12,96 ns routing (78 %)
   mac_core_cdc_graycounter0_q[3] -> ... -> mac_core_cdc_graycounter0_ce -> FF
eth_tx (16,15 ns, needs ≤ 8,00 ns):   5,45 ns logic + 10,70 ns routing (66 %)
   mac_core_txdatapath_cdc_asyncfifo_re -> graycounter1_q_next_binary -> BRAM ADDRB0
```

So: **the problem is routing/placement, not the silicon and not the pin choice.** The logic alone
(3.6–5.5 ns) would fit into the 8 ns budget; the 11–13 ns of routing is what kills it.

### 1.2 The RXC pin (IO_EB_A7) is NOT the limit

Kosjenka's finding that CC_BUFG on a non-clock pin works is confirmed in practice: a build with
`rxc_global=True` (without `clkbuf_inhibit`) goes through nextpnr to a bitstream, without failure.
The `eth_rx_clk` domain holds 60.45 MHz, which is the **same order of magnitude** as the PLL-driven
`eth_tx` domain (61.93 MHz). If the USR_GLB path were to blame, RX would be dramatically worse than TX.
It is not. The pin is cleared of suspicion.

---

## 2. Hard hardware finding: the PHY has no reference clock

Checked **directly from the schematic** (`/home/klaudio/app/ulx5m-gs-hw/hardware`,
tool `regoc_system/tools/kicad_netlist.py`):

```
### ETH_CLK  (3 pins)
    R104.2   ~                      passive
    U14.46   XI                     input          <- KSZ9031 reference clock
    U4.E16   IO_EB_A3               bidirectional  <- FPGA

X1  (ECS-2520MV-250-xx, 25 MHz)  -> (dnp yes)   ethernet.kicad_sch:23337
R104 (27 R, X1 -> ETH_CLK)       -> (dnp yes)
text in the schematic: "Use EB-A3 as clock source. Or use EB-A3 as input and place X1, C118, R104"
```

So the only possible 25 MHz source for the PHY is **the FPGA via IO_EB_A3**. The gateware so far does
not drive it:

```
$ grep -c "IO_EB_A3" build/eth/gateware/intergalaktik_ulx5m_gs.ccf   ->  0
```

Without a clock on XI, the KSZ9031 internal PLL does not start: no link, no RXC, MDIO reads
0x0000. This is exactly the behaviour observed in TASK-4959 and in the old "MDIO mystery" trail.

**A bug found on the way in the sister project:** `litex-rgmii-ulx5m` drives `eth_refclk` on
`IO_EA_A8` (`intergalaktik_ulx5m_gs_platform.py:84`), and that pin is on net `N$0061`, which
has **only that one pin** — it goes nowhere. So that project also never clocked
the PHY.

### 2.1 Other findings from the schematic (relevant to GbE)

| Signal | KSZ9031 | FPGA | note |
|---|---|---|---|
| `RGMII_REFCLK` | pin 41 `CLK125_NDO/LED_MODE` | **IO_EB_B8** | the PHY can give **125 MHz** back to the FPGA; the same net also carries the `LED_MODE` strap (R66 = 4k7 to +1V8) |
| PHYAD1 / PHYAD0 | pin 15 / 17 | LEDY / LEDG | R74/R75 (pull-up) are `dnp`, R84/R85 = 4k7 to GND → **PHYAD = 0** |
| MODE[3:0], CLK125_EN, PHYAD2 | pins 27/28/31/32/33/35 | via R97–R102 = **27 Ω series** to the FPGA | these are **not** strap resistors — the strap value is set by the KSZ9031 internal pulls (default = RGMII, CLK125 enabled) |

An earlier note that assigned R66–R85 to the MODE/CLK125_EN straps **is not correct**; those
resistors sit on `RGMII_REFCLK`, `LEDY` and `LEDG`, and the RX line has only 27 Ω series resistors.

---

## 3. What was changed in the code (29 + 15 lines)

Everything is behind flags; the default repository behaviour (100 Mbps) stays untouched.

### 3.1 `--gbe` — speed-adaptive RGMII

| File | Change |
|---|---|
| `gateware/target_eth.py` | `gbe=False` parameter; `--gbe` CLI; `fixed_100m = not gbe`, `with_dynamic_link = gbe`, `rxc_global = gbe`, `line_rate_1g = gbe`; RXC period constraint 8 ns instead of 40 ns; `--gbe` raises `tx_clk_freq` to 125 MHz |
| `gateware/phy_rgmii_gatemate.py` | `line_rate_1g` parameter (sets `tx_clk_freq`/`rx_clk_freq` to 125 MHz) |
| `gateware/crg.py` | none — `tx_clk_freq` was already a parameter |

The mechanism is LiteEth's own: `LiteEthRGMIITXClock(external_tx_clk=True)` at
`link_1G` passes 125 MHz through as TXC, and at `link_100M` divides it by 5 → 25 MHz. The speed is
selected from the RGMII in-band status, without MDIO. So the same bitstream covers 10/100/1000.

### 3.2 Driving the PHY reference clock (enabled by default)

| File | Change |
|---|---|
| `gateware/ulx5m_eth_platform.py` | new IO `("eth_refclk", 0, Pins("IO_EB_A3"), SLEW=fast, DRIVE=3)` |
| `gateware/crg.py` | `self.clk25 = clk25` (exposed to the target) |
| `gateware/target_eth.py` | `self.comb += platform.request("eth_refclk").eq(self.crg.clk25)`; `--no-phy-refclk` turns it off |

This is a fix that **must also go into the 100 Mbps build** — without it the PHY does not work at all.

---

## 4. External forks — what is really there

| Source | Finding |
|---|---|
| `pu-cc/liteeth`, branch **`gatematergmii`** | `liteeth/phy/gatematergmii.py` (Patrick Urban, Cologne Chip) — a **gigabit** RGMII PHY for GateMate: one byte per clock, DDR, without the 10/100 nibble gear |
| same file | **GateMate DOES HAVE a programmable delay on the pad**: `CC_IBUF(DELAY_IBF=n)` and `CC_OBUF(DELAY_OBF=n)`, up to 16 steps; in SPEED mode 30/38/50 ps (best/typ/worst) → **max ≈ 0.5–0.8 ns**. The comment in our repository ("GateMate has no programmable delay primitive") is **wrong** |
| `pu-cc/litex-boards`, branch `olimex_gatemate_ethio` | reference usage: `tx_delay = 0.0`, `rx_delay = 0.0`, with the comment *"RTL8211E adds 2ns TXDLY=1 / RXDLY=1"* — the 2 ns RGMII shift is done by the **PHY**, not the FPGA. Clocking: `tx_clk=None` ⇒ `cd_eth_tx.clk = cd_eth_rx.clk` (**TXC derived from the PHY's RXC**, without a 125 MHz PLL) |
| `pu-cc/litex`, branch `gatemate-oddr-fix` | fix for the `CC_ODDR`/`CC_IDDR` lowering (`i_DDR = clk` + re-timing `CC_DFF`). **Already in our LiteX** (`litex/build/colognechip/common.py:108` has `i_DDR = clk` and both DFFs) — not an open issue |
| `pu-cc/liteeth`, branch **`gatemate1000basex`** | `liteeth/phy/gatemate_1000basex.py` (477 lines) — gigabit over **SerDes and 1000BASE-X**, fully bypasses RGMII and the 125 MHz fabric. Needs SFP/optics, not the KSZ9031 |
| `mmicko` | **does have** a fork `mmicko/nextpnr` (and `yosys`, `litex`, `litex-boards`) — the claim "no public nextpnr fork" does not hold; whether the fork is ahead of upstream in any way was not checked |

Conclusion: a public gigabit RGMII PHY for GateMate **does exist** (pu-cc), but it is not for this
board, and nowhere is a closed timing analysis at 125 MHz shown for it.

---

## 5. What would be needed for GbE to really work

Ordered by effect-to-risk ratio.

### P0 — without this nothing works (not even 100M)
1. **Drive 25 MHz on IO_EB_A3.** Delivered in this patch. Needs confirmation on the board:
   an MDIO read of registers 0x02/0x03 at PHYAD = 0 must give `0x0022` / `0x1620`.
   While MDIO is 0x0000, any discussion of 100 vs. 1000 Mbps is pointless.

### P1 — timing closure at 125 MHz (shortfall ≈ 2.0×)
2. **A newer nextpnr.** The local one is `nextpnr-0.10-45-g98c18d7`. Upstream has a control-set-aware
   HeAP legaliser (#1678) and an iterative `reassign_bridges` (#1697); both target exactly what
   is killing us (routing of FF groups). This is the cheapest move with the biggest potential.
3. **Shorten the gray counters of the LiteEth async FIFOs.** The critical path is
   `graycounter_q -> ce -> q_next_binary -> BRAM ADDRB0`. A shallower FIFO (fewer bits in the
   gray counter) shortens both logic and routing.
4. **A seed sweep is mandatory, not cosmetic.** Post-placement range: eth_tx
   115.6–126.5 MHz, eth_rx 94.9–108.5 MHz (seeds 1/3/11). One seed (3) even *passes*
   125 MHz on TX after placement — and then fails in the router.
5. **Try timing-driven ripup** (`--router2-tmg-ripup`), because 66–78% of the critical path is
   routing.

### P2 — throughput, not just the clock
6. Even when 125 MHz closes, `sys` at 16 MHz with `dw=8` carries **16 MB/s**, while gigabit
   needs **125 MB/s**. The measured ceiling of the `sys` domain is **29–42 MHz**. So:
   - **there is no systemic path to full gigabit at `dw=8`.** It needs `dw=32` with `sys`
     ≥ 31.25 MHz (measured 29.1–42.5 MHz → tight, but within reach) or `dw=64` with ≥ 15.6 MHz.
   - With `dw=8` and `sys` = 16 MHz, a gigabit link can *come up* and receive short frames, but
     the async FIFO overflows in the middle of a 1500 B frame. This must be measured, not assumed.

### P3 — RGMII delays (2 ns)
7. **Do not do it in the FPGA.** `CC_OBUF DELAY_OBF` gives at most ≈ 0.8 ns — too little.
   Cologne Chip in its own reference leaves 0 and lets the **PHY** add 2 ns
   (`RTL8211E: TXDLY=1 / RXDLY=1`). The KSZ9031 equivalent is RGMII-ID via MMD registers.
8. **Alternative without MDIO:** `CC_PLL` CLK90 at 125 MHz = exactly 2 ns of shift for TXC.
   `GateMatePLL.create_clkout(..., phase=90)` already supports this. This stays fully inside the FPGA
   and does not touch the pad-skew registers (which killed TX last time).

### Do not do
- ❌ write the pad-skew registers (MMD2 dev2 reg8) — this killed TX before;
- ❌ drive IO_EB_B8 as an output — it carries the `LED_MODE` strap (4k7 to +1V8) and the PHY's
  `CLK125_NDO`; it may only be an input;
- ❌ `eth_refclk` on `IO_EA_A8` — that pin goes nowhere (net `N$0061`).

---

## 7. What was tried to close the gap (and how it went)

| Attempt | Result |
|---|---|
| Seed sweep 7 / 1 / 3 at 125 MHz | 52.8–65.5 MHz after routing — the gap stays ≈ 2× |
| Seed 11 | router failed: `Failed to route arc ... net 'crg_gatematepll1_clkout'` (GLBOUT0) |
| `--router2-tmg-ripup` (timing-driven ripup), seed 7 | **does not converge**: stopped after **532 iterations** with `overused=1..3` that only oscillates. Not usable on this design |
| `--gbe` + refclk drive, seed 7 | router failed: `Failed to route arc 29.0 of net 'eth_rx_clk'` |

The last row is important: **one extra IO pin (25 MHz on IO_EB_A3) is enough for the GbE
variant to stop routing on seed 7.** A design with three global clocks at 125 MHz is on the
edge of routability — this is not "almost done", it is unstable.

### 7.1 In contrast: 100 Mbps with refclk passes easily

| Build | eth_tx | eth_rx | sys | result |
|---|---|---|---|---|
| **100 Mbps + refclk drive (default after the patch)** | 58.08 @ 25 PASS | 63.09 @ 25 PASS | 26.62 @ 16 PASS | **rc=0, bitstream 453 676 B** |

```
$ grep IO_EB_A3 build/eth/gateware/intergalaktik_ulx5m_gs.ccf
Net "eth_refclk" Loc = "IO_EB_A3" | SLEW=fast | DRIVE=3;
$ md5sum intergalaktik_ulx5m_gs.bit
fdc72cb175520564f72b82edb49215f0
```

**This is the bitstream worth trying on the board first** — for the first time ever it gives the KSZ9031
a reference clock.

---

## 6. How to reproduce this

```bash
export OSS_CAD_SUITE=/home/klaudio/Programs/oss-cad-suite
export LXROOT=/home/klaudio/app/litex-rgmii-ulx5m
cd /home/klaudio/app/litex-eth-ulx5m-gs/litex-eth-ulx5m-gs
source ./env.sh                       # NOT through a pipe -- the exports are lost in a subshell

python3 gateware/target_eth.py --build                 # 100 Mbps (default) + refclk
python3 gateware/target_eth.py --build --gbe           # 1000 Mbps datapath, eth_tx = 125 MHz
python3 gateware/target_eth.py --build --gbe --no-phy-refclk   # without driving XI

# numbers per domain:
grep -E "Max frequency" build/eth/gateware/../../..  # see build.log; last 4 lines = after routing
```

For a seed sweep without re-running synthesis:

```bash
nextpnr-himbaechel --json <build>.json --vopt ccf=<build>.ccf --device CCGM1A1 \
  --vopt out=x.txt --router router2 --timing-allow-fail --seed <N> --freq 125
```

### 6.1 A toolchain trap you need to know about

`litex/build/colognechip/peppercorn.py:73` has a **commented-out** line:

```python
#pnr_opts += " --sdc {top}.sdc"
```

So the generated `.sdc` is **never passed to nextpnr**. The only thing that really reaches
static analysis is `--freq <largest period constraint>`, which is applied to all
unconstrained clocks. Consequence: in the 100 Mbps build the target is `--freq 25`, so the numbers
"57 MHz / 79 MHz" are only *good enough for 25*, not the ceiling. Only `--gbe` (which raises
`--freq` to 125) makes the placer really push — and only then is the real ceiling visible.
This is why a naive comparison of numbers from two builds is misleading.

---

## 8. Verdict

**1 Gbps on the ULX5M-GS is not feasible today "with minimal changes".** The code is minimal
(29 lines) and the build passes, but:

- the timing gap is **≈ 2.0×** (needs 125 MHz, gets 52.8–65.5 MHz), and **the seed does not
  close it**; it would have to be closed with a newer nextpnr and by reworking the LiteEth
  async FIFOs — those are no longer minimal changes;
- even if the clock closes, `sys` at 16 MHz with `dw=8` carries 16 MB/s, while gigabit needs
  125 MB/s — a **wider datapath** (`dw=32`) is also needed;
- and before all of that, **the PHY on this board currently has no reference clock at all**, so
  even 100 Mbps does not work.

**Recommended order:** first IO_EB_A3 and evidence that MDIO at PHYAD 0 returns
`0x0022/0x1620`; then 100 Mbps on the wire end to end (ping + UDP echo); and only then
gigabit as a separate project with a newer nextpnr, `dw=32` and a CLK90 TXC.

The delivered `--gbe` flag stays useful as a **measurement instrument** and as prepared
infrastructure — not as a claim that gigabit works.
