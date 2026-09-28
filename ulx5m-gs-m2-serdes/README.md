# ulx5m-gs-m2-serdes — SerDes link between ULX5M-GS and ULX5M-M2

Two GateMate CCGM1A1 boards talk to each other over their SerDes lane:
- **gs**: [ULX5M-GS](https://github.com/intergalaktik/ulx5m-gs) on a CM4 IO baseboard,
- **m2**: ULX5M-M2 (GateMate on an M.2 card), plugged into the baseboard's PCIe slot through a PCIe-to-M.2 adapter.

The only connection between the two FPGAs is this SerDes lane (TX and RX pairs). Both boards use the same
100 MHz LVDS reference clock. It comes from the oscillator on the GS board; the oscillator on the M2 was removed.

**Continuing this work (person or AI)?** Start with [`docs/SERDES_KNOWLEDGE.md`](docs/SERDES_KNOWLEDGE.md): everything we know
in one place: setup, settings per rate, results, traps, how to reproduce, open items.

## What works

- **8b10b link in both directions, bit-exact, at 0.3 Gb/s.** The same bitstream runs on both boards
  (`bitstreams/serdes_p1_rxpol1_CFGRST.bit`, CologneChip `serdes_lb.v`, K28.5 + D10.2). Each receiver decodes exactly
  what the other board sends: 6 place-and-route seeds × 2 boards × 30 reads = **360/360 correct**.
- **The P/N polarity of the lane is swapped, in both directions.** Without `RX_POLARITY=1` every receiver sees
  D21.5 (0xB5, the inverse of D10.2) instead of D10.2. K28.5 is symmetric under inversion, so byte alignment
  still locks. The fix is `RX_POLARITY_I=1` in the bitstream on both boards.
- **BER at 0.3 Gb/s, measured with a fabric checker** (`gateware/ber/`): 1.125·10⁹ words in each direction,
  0 bit errors, 0 8b10b code errors. That gives **BER < 6.7·10⁻¹¹ at 95 % confidence** (40 checked bits per
  word). The checker counts injected errors exactly: 3 errors injected on gs TX were counted as 3 on m2, and
  5 injected on m2 TX were counted as 5 on gs. (Measured with the first version of `ber_top`. The sources here
  add pipelining for higher rates and change m2's ID from 2 to 3; that version is re-measured in the rate sweep.)
- **1.25 Gb/s with 0 errors** using the in-spec ADPLL recipe N1·N2·N3 = 1·5·5 (DCO 2500 MHz), OUTDIV 4: 1.885·10⁹
  words per direction, **BER < 4·10⁻¹¹**. The rate is measured from the clock counters: 1250.0 Mb/s in both directions.
- **The data really goes over the cable** (see [How to check it yourself](#how-to-check-it-yourself)). Every
  word carries the sender's ID. If m2's TX is idled, gs loses the data, and the other way round.
- **Every bitstream starts with a configuration reset** (`gmpack --reset`, CMD_CFGRST), checked with `tools/gm_cfgrst_check.py`.

## Summary by rate

| Rate | Result |
|---|---|
| 0.3 Gb/s | 0 errors (BER < 6.7·10⁻¹¹) |
| 1.25 Gb/s | 0 errors (BER < 4·10⁻¹¹) |
| 2.5 Gb/s | Works, but not error-free. With 1 µF on GS C127/C128/C42: gs→m2 6·10⁻¹⁰, m2→gs 1·10⁻¹¹ (median of 3 loads × 300 s), much less spread between loads than before |
| 5 Gb/s | Does not work: BER 10⁻² … 10⁻¹ |

## What does not work yet / not proven

- **2.5 Gb/s works, but not without errors** (1·5·5, OUTDIV 2, measured 2500.02 Mb/s). With the pu-cc 5G analog set
  in the bitstream (`PROFILE=1`), 300 s runs give BER about 10⁻⁹ … 10⁻¹¹ per direction. The pair in `bitstreams/`
  (`ber_*_2g5_p1_*`, `TX_NEG=1` on m2 only) gave m2→gs 6.7·10⁻¹¹ and gs→m2 1.2·10⁻⁹. With `TX_NEG=1` on gs as well
  (§9.3, built from the same sources) the best load gave m2→gs 1.6·10⁻¹¹ and gs→m2 4.7·10⁻¹⁰, but the same
  bitstreams loaded again were 25 to 3000 times worse. The cause is that nextpnr does not time the fabric↔SerDes ports (`delay.cc`: SERDES =
  `TMG_IGNORE`), so the TX/RX paths change with every placement. `TX_NEG=1` on gs improves gs→m2 about 60 times.
  RX AFE `GAIN 0` is needed (the as-built GAIN 8 gave 10⁻⁴). Details: `docs/VERIFY_20260926_RATES.md` §9.3, §9.7.
- **1 µF on the GS SerDes supplies makes 2.5 Gb/s better and repeatable** (27.09.2026, TASK-5078/5079). 1 µF in parallel to
  C128 (VDD_SER), C127 (VDD_SER_PLL) and C42 (VDD_PLL) on **GS**. Same bitstreams before and after (the best pair
  `ber_gs_2g5_p1_txneg_s7` + `ber_m2_2g5_p1_txneg_s2`), 3 loads × 300 s:

  | | gs→m2 typical / worst | m2→gs typical / worst | spread between loads |
  |---|---|---|---|
  | before | 2.4·10⁻⁹ / 1.2·10⁻⁸ | 8.5·10⁻¹⁰ / 4.5·10⁻⁸ | ×26 / ×2900 |
  | **after** | **6.0·10⁻¹⁰ / 6.9·10⁻¹⁰** | **1.3·10⁻¹¹ / 2.6·10⁻¹⁰** | **×1.6 / ×32** |

  At 5 Gb/s the change is 1.5–2×, which is within the noise (PROFILE 2: gs→m2 7.3·10⁻² → 4.9·10⁻²). The same capacitor on
  C42 (VDD_PLL) also removed the fabric PLL lock drops under SDRAM load (DVI). Repeat with `docs/data_20260927/t5079/lab9.sh`.
  Details: `docs/VERIFY_20260926_RATES.md` §10.1–§10.4.
- **5 Gb/s does not work.** The PLL locks (measured 5000.04 Mb/s), but the CDR does not hold lock and the fabric BER
  stays at 10⁻² … 10⁻¹. About 60 register settings were tried (RX AFE and DFE, CDR, TX FFE, VCM, refclk
  termination, seeds, `PROFILE` 2 and 3 in the bitstream). None left that range. The RX words read over JTAG,
  without the fabric, already have 2.5–17.5 % bad headers. Extra decoupling on the GS SerDes supplies did not change 5 G
  either (above). The next suspects are in hardware: the refclk at M2, the FFC→M.2 adapter chain, and crosstalk.
  Details: `docs/VERIFY_20260926_RATES.md` §9.8–§9.10, `docs/TUNING_5G.md`.
- **The PCB channel is not what limits 5 Gb/s** (SI analysis, TASK-5086). GS v005 on JLC's default 6-layer stack is 97–103 Ω
  (M2 88 Ω). The whole chain loses 3.0 dB (nominal) to 4.8 dB (worst) at 2.5 GHz, and a linear model with a 3-tap DFE keeps a
  5 Gb/s eye of 0.59–0.70. 5 Gb/s is also the silicon maximum (DS1001). Left for 5 G: the refclk at M2, the unidentified
  FFC→M.2 adapter, FFC crosstalk. Details and next-revision changes: `docs/SI_SERDES_GS_v004.md`.
- **A local oscillator on M2 is prepared, not fitted** (TASK-5087, `docs/LOCAL_REFCLK_M2.md`). Only one driver per net: fit X2
  on M2 and remove C136/C137. With two oscillators the CDR frequency integrator must be on (`CDR_CKI=1` on both; 2 is worse,
  4 is unstable). DS1001 gives no ppm tolerance for the CDR, so that has to be measured once X2 is on. The X2 in the
  schematics is a 2.5 V part on a 1.8 V rail: order the 1.8 V variant (`511J…`). Bits: `ber_*_2g5_p1_txneg_cki1_*`.
- The on-chip eye counters (regfile 0x14–0x1D) never count; the upstream `tc_eyemeas` is an empty stub.
- **The 1·2·3 recipe is only clean at 0.3 Gb/s.** Its DCO runs at 600 MHz, below the 1250–2500 MHz in DS1001.
  At 0.6 Gb/s one direction has errors, and at 1.2 Gb/s both do. Use 1·5·5.
- Rate sweep table: `docs/VERIFY_20260926.md` §6.
- **The hard PRBS checker in CC_SERDES is not a BER instrument here.** PRBS select codes 3 and 4 are *reserved*
  (DS1001 p.70/p.86). Only 1 (PRBS-7) and 2 (PRBS-15) exist. Our old tests used 4, so the counter stayed at 0x7FFF.
  BER is measured with the fabric checker instead.
- **The loopback bits in the regfile do not show what the bitstream set.** With `*_LOOPBACK_OVR=0`, the regfile
  fields do not mirror the fabric ports (`RX_POLARITY` reads 0 while `RX_POLARITY_I=1`). `LOOPBACK_SEL=0` in the
  tools therefore only proves that no regfile override is active. The proof that there is no loop comes from the
  sender IDs and the idle/cable tests.
- **The nextpnr "setuphold" patch from pu-cc (abd0731) is wrong, so we do not use it.** It treats the rise/fall
  timing values in the GateMate chipdb as speed corners and so swaps setup and hold on BRAM inputs, which makes
  real BRAM setup failures look like passes; upstream nextpnr is correct, and the SerDes designs have no BRAM, so it
  cannot help the link speed. Details: `docs/NEXTPNR_SETUPHOLD_PATCH.md`.
- The source of the polarity swap (GS, CM4 baseboard, adapter or M2) has not been traced in the schematics.

## Layout

| Folder | Contents |
|---|---|
| `gateware/baseline/` | The passing link test: `serdes_lb_p1.v` (CologneChip `serdes_lb.v` + `RX_POL` parameter, `RX_POLARITY_I=RX_POL`), `serdes_lb_dut.v` (the same file with `RX_POLARITY_I=0`), `dut_top.v`, `dut_top.ccf` (the same pins on both boards), `build.sh` |
| `gateware/ber/` | Fabric BER generator/checker (`ber_link.v`), top level (`ber_top.v`, `top_gs`/`top_m2`), `.ccf` for gs and m2, `build_ber.sh`, simulation (`sim/`, iverilog) |
| `gateware/upstream/` | Unchanged CologneChip `serdes_lb.v`, for reference |
| `bitstreams/` | Bitstreams tested on the boards (all with CFGRST) + `SHA256SUMS` |
| `tools/` | JTAG and UART tools, `verify_external_link.sh`, `si/` (PCB SI extraction, 2-D field solver, channel cascade), unit tests |
| `docs/` | `REVIEW_20260926.md` (review and measurements), `SOURCES_20260926.md` (datasheet and reference designs), `VERIFY_20260926.md` (verification report), `VERIFY_20260926_RATES.md` (2.5 / 5 Gb/s, TASK-5063/5066/5073), `TUNING_5G.md` (what to tune for 5 Gb/s), `SI_SERDES_GS_v004.md` (PCB SI of GS v005 / M2, max rate, next-revision changes, TASK-5086), `LOCAL_REFCLK_M2.md` (local oscillator on M2, TASK-5087), `NEXTPNR_SETUPHOLD_PATCH.md`, **`SERDES_KNOWLEDGE.md` (handover: everything in one place)** |

## Bitstreams

| File | Load on | What it does |
|---|---|---|
| `serdes_p1_rxpol1_CFGRST.bit` | **both** gs and m2 | 0.3 Gb/s, 8b10b, K28.5 + 7 × D10.2, `RX_POLARITY_I=1`. Check with `serdes_link_check.py` (expect `DATA_OK 30/30`). |
| `ber_gs_0g3_CFGRST.bit` + `ber_m2_0g3_CFGRST.bit` | gs + m2 | BER design, 0.3 Gb/s. Used by `verify_external_link.sh --load`. |
| `ber_gs_1g25_CFGRST.bit` + `ber_m2_1g25_CFGRST.bit` | gs + m2 | BER design, 1.25 Gb/s (1·5·5). |
| `ber_gs_2g5_p1_CFGRST.bit` + `ber_m2_2g5_p1_txneg_CFGRST.bit` | gs + m2 | BER design, 2.5 Gb/s, `PROFILE=1`, `TX_NEG` on m2 only. Works, not error-free. |
| **`ber_gs_2g5_p1_txneg_s7_CFGRST.bit` + `ber_m2_2g5_p1_txneg_s2_CFGRST.bit`** | gs + m2 | **Best 2.5 Gb/s pair**: `PROFILE=1`, `TX_NEG` on both. Used for every hardware A/B (1 µF on GS: 6·10⁻¹⁰ / 1·10⁻¹¹). |
| `ber_gs_2g5_p1_txneg_cki1_CFGRST.bit` + `ber_m2_2g5_p1_txneg_cki1_CFGRST.bit` | gs + m2 | the best pair + `CDR_CKI=1`, for a local oscillator on M2 |
| `ber_*_5g_p2_txneg_*` / `ber_*_5g_p3_txneg_*` | gs + m2 | BER design, 5 Gb/s, `PROFILE` 2 / 3. Reference for hardware changes; not usable. |

All of them are listed in `bitstreams/README.md` with their results. They are rebuilt byte for byte from the sources here (`gateware/baseline/build.sh 1`,
`gateware/ber/build_ber.sh`; see `bitstreams/README.md`), with oss-cad-suite 2026-09-23.

**Measure BER yourself** (BER design loaded, gs UART on the gs probe's interface 01):

    python3 tools/ber_mon.py run --secs 300 --clear     # both directions + measured line rate
    python3 tools/ber_mon.py inject e --n 3             # negative control: m2 must count exactly 3

## How to repeat it on another computer

**You need:**
- the two boards connected by the SerDes lane (on our setup: ULX5M-GS on a CM4 IO baseboard, ULX5M-M2 in its PCIe
  slot through a PCIe-to-M.2 adapter),
- **one JTAG probe per board.** We use two DirtyJTAG probes, and on the gs probe interface 01 is also the gs UART console,
- a Linux PC (we use a Raspberry Pi) with `openFPGALoader`, Python 3, `pyusb` and `pyserial`,
- to build: oss-cad-suite 2026-09 or newer (yosys, nextpnr-himbaechel, gmpack).

**Selecting the right probe.** Both GateMates have the same IDCODE, and both DirtyJTAGs have the same USB VID:PID.
openFPGALoader opens the *first* DirtyJTAG it finds and ignores `--busdev-num`. Loading the "gs" bitstream can
therefore end up on the wrong board. We use a small wrapper, `fpga-jtag gs|m2 …`: it finds the probe by its USB
serial number and forces openFPGALoader onto it with an `LD_PRELOAD` shim. Our Python tools choose the probe from
`FPGA_JTAG_BUSDEV=<bus>:<addr>` and refuse to run if several probes are present and the variable is not set.
Without such a wrapper, connect only one probe at a time.

**1. Load (SRAM only):**

    fpga-jtag m2 bitstreams/serdes_p1_rxpol1_CFGRST.bit -r
    fpga-jtag gs bitstreams/serdes_p1_rxpol1_CFGRST.bit -r

**2. Check both receivers (read-only JTAG):**

    fpga-jtag gs run python3 tools/serdes_link_check.py --samples 30
    fpga-jtag m2 run python3 tools/serdes_link_check.py --samples 30

Each line must end with `rx: DATA_OK 30/30 -> PASS` and show `LOOPBACK_SEL=0`.

`tools/serdes_status.py` prints all CC_SERDES status fields and every loopback bit.

## How to check it yourself

The goal is to prove that (a) the data goes over the **external** lane and not through an internal loop, (b) what
the BER is, and (c) up to which rate the link works.

With the baseline bitstream you can already do the idle test:

    fpga-jtag m2 run python3 tools/serdes_tx_ctl.py idle on      # m2 TX in electrical idle
    fpga-jtag gs run python3 tools/serdes_link_check.py           # must FAIL: IDLE_FF
    fpga-jtag m2 run python3 tools/serdes_tx_ctl.py idle off
    fpga-jtag gs run python3 tools/serdes_link_check.py           # PASS again

Do not trust `RX_CDR_LOCKED` or `RX_BYTE_IS_ALIGNED`. They stay 1 while the far transmitter is idle. The verdict
must come from the received data.

The complete check uses the BER design (`gateware/ber/`) and `tools/verify_external_link.sh`. It runs these steps
and prints PASS/FAIL for each: initial state → idle m2 TX (gs must drop) → restore → idle gs TX (m2 must drop) →
restore → inject exactly 3 errors on each TX (the other side must count exactly 3) → replace m2's data with a fixed
pattern (gs must reject it) → **"pull the SerDes cable now"** (both sides must drop) → **"put the cable back"**
(both must recover). Instructions: `tools/README_verify_external_link.hr.md` (Croatian). The automatic part
(`--no-cable`) passed 9/9 on 26 September 2026. The cable steps need a person at the boards.

## Next steps

1. 5 Gb/s: hardware first. The GS supply decoupling is done (no effect at 5 G). Next: the refclk at M2 (scope, or the local X2), then the channel. Judge each change
   by the 3-load median of synced share and BER against PROFILE 2 and 3 (`tools/lab/ab_table.py --runs --rank`).
2. 2.5 Gb/s error-free: the fabric↔SerDes ports need timing constraints in nextpnr. Until then, pick seeds by
   several loads, not by one.
3. Cable steps of `verify_external_link.sh` on the boards.
4. Eye scan: `tools/eyescan.py` is ready, but the counters do not count — ask CologneChip how to start them.
5. Trace the P/N swap in the schematics (GS → CM4 baseboard → PCIe slot → adapter → M2).

## Built on

| Project | What we use |
|---|---|
| [CologneChip gm_serdes_lb](https://github.com/pu-cc/gm_serdes_lb/tree/fbe1966) (Patrick Urban), as copied in [openCologne 7.SerDes/1.serdestool_by_gm @ 27eb53a](https://github.com/chili-chips-ba/openCologne/tree/27eb53ae74cbec76a8066ff108776bce127523bf/7.SerDes/1.serdestool_by_gm) | `serdes_lb.v` (CC_SERDES instance and parameters) and `serdestool.py` (regfile map, JTAG access). ISC-style permission notice, © 2022–2025 Cologne Chip AG, kept in the file headers. Our changes: `serdes_lb_dut.v`/`serdes_lb_p1.v` fix `calcTxK` and add the `RX_POL` parameter; `tools/serdestool.py` has a chain-bypass fix for one device per probe, and two Python 3.12-only f-strings in the code generator are removed. |
| [oss-cad-suite 2026-09-23](https://github.com/YosysHQ/oss-cad-suite-build/releases/tag/2026-09-23): Yosys, nextpnr-himbaechel, gmpack, openFPGALoader | Synthesis, place and route, packing, loading |

Our own files are BSD-2-Clause, like the rest of this repository.
