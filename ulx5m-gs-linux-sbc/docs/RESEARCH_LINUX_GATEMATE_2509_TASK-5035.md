# Research: Linux on GateMate (CCGM1A1) with SDRAM — TASK-5035

Author: Dora (REGOČ), 2026-09-25. Order: Goran 10:45, instructions #28, #30, #31. This is research only. I did not touch the board or Jelena's code.

Follow-up and verification: Jelena (TASK-5038), 2026-09-25. I re-checked the local claims and closed two open points from §7 by measurement (see §11).

> **State before this report.** While the order was being written, Jelena (TASK-5033, branch `linux-vexriscv-smp`, tag `linux-boot-ok-2509`) had already booted Linux 5.14 on ULX5M-GS: VexRiscv-SMP with 1 core, I$/D$ 4 KiB, MMU, 1G CPU MAC, no SD, **CPE_LT 55%**, RAM_HALF 45/64 (`docs/SOC_PHASE2_20260925_TASK-5033.md` §9). So this document does not look for a configuration that fits. Instead it:
> (a) proves that this is the same configuration that booted Linux on the Kölsch;
> (b) lists what else can be removed so that SD also fits next to Linux;
> (c) evaluates alternative paths (nommu, SaxonSoc, VexiiRiscv).

Tags: **[SOURCE]** means a link or file backs the claim. **HYPOTHESIS** means it is not verified.

---

## 1. Board from a German manufacturer: Machdyne Kölsch

| Item | Kölsch | Source |
|---|---|---|
| Manufacturer | Machdyne UG (a German company form) | [X/Twitter Machdyne](https://x.com/machdyne/status/1651920765619511297), [Cologne Chip news](https://colognechip.com/news/machdyne-announced-board-with-a1/) |
| FPGA | **CCGM1A1** ("Cologne Chip GateMate CCGM1A1 FPGA (20K LUTs, 4 PLLs)"), so the same chip as ours, not A2/A4 | [machdyne.com/product/kolsch-computer](https://machdyne.com/product/kolsch-computer/) |
| RAM | "64MB 16-bit LPSDR SDRAM (166MHz)", in LiteX the `W989D6DBGX6` module on `GENSDRPHY`, 1:1 | product page; `litex_boards/targets/machdyne_kolsch.py` l. 26, 103–107 |
| SDRAM clock | `DDROutput(1, 0, sdram_clock, ClockSignal("sys_ps"))`, PLL `sys_ps` with 90° phase | `machdyne_kolsch.py` l. 37, 51–53 |
| Other | VGA (4096 colours), composite video, microSD (SPI), RP2040 configures the FPGA | product page; [github.com/machdyne/kolsch](https://github.com/machdyne/kolsch) |

### 1.1 Linux on the Kölsch: what is publicly proven

- **linux-on-litex-vexriscv `--board=kolsch`**: [PR #428](https://github.com/litex-hub/linux-on-litex-vexriscv/pull/428), author Miodrag Milanović (mmicko, YosysHQ), merged 2025-07-02. Commit `b988251` "Added support for Machdyne Kolsch":
  ```python
  class Kolsch(Board):
      soc_kwargs = {"sys_clk_freq": int(24e6)}
      ... soc_capabilities={"serial", "spisdcard"}
  ```
  The PR depends on three upstream patches, all merged:
  - [litex-boards #679](https://github.com/litex-hub/litex-boards/pull/679) (board);
  - [litedram #366](https://github.com/enjoy-digital/litedram/pull/366) ("Added W989D6DBGX6");
  - [litex #2274](https://github.com/enjoy-digital/litex/pull/2274) ("colognechip: DDR should not be inverted").

  **Our local LiteX (`~/app/litex-1g-deps/litex`, 2026.08) already contains #2274** (`git log`: `dbca01b0e`), and litedram contains `W989D6DBGX6` (`modules.py:574`).
- **The exact CPU configuration** is in the YosysHQ test case [`prjpeppercorn-test-cases/112-litex-linux-kolsch`](https://github.com/YosysHQ/prjpeppercorn-test-cases/tree/main/112-litex-linux-kolsch), commit `6d11041` "Added Linux on Kolsch with SDRAM" (2025-06-27, Milanović). The netlist is `VexRiscvLitexSmpCluster_Cc1_Iw32Is4096Iy1_Dw32Ds4096Dy1_ITs4DTs4_Ldw16_Ood_Hb1.v`:
  - **1 core, I$ 4 KiB/1 way, D$ 4 KiB/1 way, ITLB/DTLB 4, MMU (Sv32), no FPU;**
  - native LiteDRAM 16 bit, out-of-order decoder, 1 hardware breakpoint;
  - `kolsch.sdc`: `sys_clk` period 41.666 ns = **24 MHz**;
  - yosys: `-nomx8` and `setattr -unset ram_style a:ram_style=distributed`;
  - since commit `8ed68d7` (2025-08-18) multipliers are enabled (`-nomult` was removed).
- **Kölsch utilisation is not published.** The test case has no P&R report, and the toolchain is not in this container, so I could not reproduce it. **HYPOTHESIS:** about 60% CPE_LT, because the composition (SMP + SDRAM + serial + SPI-SD) is closest to Jelena's `smp_1` (61%, SMP + serial + LiteSDCard).
- **I did not find a public Kölsch boot log**: it is not in PR #428, not in prjpeppercorn, and not on Machdyne's pages. The evidence that Linux works is indirect:
  1. the board is in the main branch of linux-on-litex-vexriscv;
  2. the author later added only fixes;
  3. the commit title says "Linux on Kolsch with SDRAM".

  **The strongest evidence of a boot on CCGM1A1 + SDRAM today is our own:** `docs/linux/linux_boot_smp8_9.txt` on branch `linux-vexriscv-smp` and Kosjenka's independent 3/3 check (TASK-5034, commit `47985a8`).

**Conclusion §1.** Jelena's configuration (`…Cc1_Iw32Is4096Iy1_Dw32Ds4096Dy1_ITs4DTs4_Ldw16_Ood.v`) and the Kölsch one differ only by `Hb1`. It is the same core, on the same chip, with the same SDRAM width. We run at 20 MHz, the Kölsch at 24 MHz. **The path is confirmed and there is no need to look for another CPU.**

## 2. Other GateMate boards

| Board | Chip | RAM | Linux profile | Evidence / status |
|---|---|---|---|---|
| Cologne Chip GateMate EVB | CCGM1A1 (`device="A1"`, A2 can be set) | **HyperRAM 8 MB** (W958D6NW) | `colognechip_gatemate_evb`, 24 MHz, serial + SD | [PR #422](https://github.com/litex-hub/linux-on-litex-vexriscv/pull/422): "note it does have 8MB of RAM". prjpeppercorn [108-litex-linux-evb](https://github.com/YosysHQ/prjpeppercorn-test-cases/tree/main/108-litex-linux-evb) README: "**Still in progress, working on Linux image**". Netlist `…_Ood_Wm_Hb1` (Wishbone memory, because HyperRAM has no native port). |
| Olimex GateMateA1-EVB | CCGM1A1 | QSPI PSRAM | not in linux-on-litex-vexriscv | prjpeppercorn [119](https://github.com/YosysHQ/prjpeppercorn-test-cases/tree/main/119-litex-vexriscv_smp_dual): **2-core SMP, I$/D$ 8 KiB, 20 MHz on A1** (P&R test only). [120](https://github.com/YosysHQ/prjpeppercorn-test-cases/tree/main/120-litex-vexriscv_smp_quad) (4 cores): "**This test is for A2 only, does not fit in A1**". [121](https://github.com/YosysHQ/prjpeppercorn-test-cases/tree/main/121-litex-vexiiriscv-linux): VexiiRiscv `--cpu-variant linux`. |
| Trenz (TEG2000 etc.) | — | — | — | I found no Linux profile or log (GitHub/web search, 09-25) |
| **ULX5M-GS (ours)** | CCGM1A1 | SDRAM 64 MB IS42VM16320 | own `target_soc.py` | **Linux 5.14 root shell, 3/3** (TASK-5033/5034) |

**Lesson from tests 119 and 120:** the Olimex tests have no SDRAM and no MAC, and even two SMP cores with 8 KiB cache fit on A1. So on A1 the CPU is not the tight part; the peripherals around it are (MAC + LiteSDCard + Etherbone + FIFO). Jelena's lesson J7 says the same: the placer fails above ~71–76% CPE_LT, and CC_MULT is not the cause.

## 3. Issue #164 (linux-on-litex-vexriscv)

[Issue #164](https://github.com/litex-hub/linux-on-litex-vexriscv/issues/164) "Prebuilt Bitstreams and Linux/OpenSBI images" was opened by enjoy-digital on 2020-12-15. It is not a bug, but a permanently open download place:
- `linux_2022_03_23.zip` (Image + rootfs.cpio + opensbi.bin), `arty_…zip`, `orangecrab_…zip`;
- "The .dts/.dtb are included in the archives and can be regenerated with `./make.py --board=xy`."

It proposes nothing else. **Jelena already uses exactly these images** (`tools/linux/README.md`). Consequences she already lists:
- kernel 5.14 has no `IP_PNP`, so `ip=` does not work;
- `rootfs.cpio` reports "invalid magic".

The fix is our own Buildroot (`./make.py` → `buildroot/configs/litex_vexriscv_defconfig`) with a fragment containing `CONFIG_IP_PNP=y`. This is the next step, not a new gateware option.

## 4. VexRiscv-SMP: minimal configuration

This is our working composition and the Kölsch one (1 core, 4K/4K, TLB 4, no FPU, Ldw16):

| Build (Jelena, TASK-5033) | CPE_LT | RAM_HALF | Result |
|---|---|---|---|
| SMP + 1G CPU MAC + netboot, no SD | 22 644 (55%) | 45/64 | **Linux 3/3 on the board** |
| SMP + serial + SD | 25 356 (61%) | 38 | P&R PASS, not booted |
| SMP + MAC + SD | 31 643 (77%) | 54 | placer fails |

Further core reduction. All of these are options in `litex/soc/cores/cpu/vexriscv_smp/core.py`, l. 71–95:

| Lever | Effect | Condition / risk |
|---|---|---|
| `--without-out-of-order-decoder` | less decoder logic (help: "Reduce area at cost of peripheral access speed") | **needs netlist regeneration** (SBT + Java). `pythondata-cpu-vexriscv_smp` only has prebuilt `…_Ood` variants. Savings not measured (HYPOTHESIS: a few hundred CPEs). |
| `--icache-size 2048 --dcache-size 2048` | saves BRAM (about 2–3 RAM_HALF), fewer CPEs | same (regeneration). Slower Linux. |
| `--itlb-size 2 --dtlb-size 2` | a few CPEs | same. More TLB misses. |
| `--hardware-breakpoints 0` | already so (our netlist has no `Hb1`) | — |
| `-nomult` / CC_MULT | **does not help**: lesson J7 disproves it by experiment | — |

**Conclusion §4.** The core does not need further cutting. If we had to, the only worthwhile lever is regeneration without the OoO decoder, which needs SBT/Java, and those are not in this container. The bigger gain is in the peripherals (§6).

## 5. Linux without MMU (nommu, uClinux) — instruction #28 (7)

| Question | Answer | Source |
|---|---|---|
| Does the kernel support rv32 nommu? | Yes. `CONFIG_MMU=n` stays. A proposal to remove it (2024) was withdrawn after Lohr's objection: "NOMMU Linux on RISC-V is the avenue used by many FPGA soft cores for Linux". | [LKML 2403.3/07337](https://lkml.iu.edu/hypermail/linux/kernel/2403.3/07337.html) |
| Buildroot + elf2flt for rv32 | Patchset "Add RISC-V 32 NOMMU support" (12/2022): elf2flt rv32, uClibc rv32, `-fPIC` | [buildroot patchwork](https://patchwork.ozlabs.org/project/buildroot/cover/20221217051337.3778405-1-Mr.Bossman075@gmail.com/), [elf2flt patch](https://lists.buildroot.org/pipermail/buildroot/2022-December/720522.html) |
| Minimum CPU requirements | **rv32ima + Zicsr, M-mode, CLINT (mtime/mtimecmp)**. The kernel needs atomics (A). The reference emulator mini-rv32ima implements exactly this. | [cnlohr/mini-rv32ima](https://github.com/cnlohr/mini-rv32ima) |
| Userspace | bFLT (`CONFIG_BINFMT_FLAT=y`), `vfork` instead of `fork`, `-Wl,-elf2flt=-r` | [popovicu.com: 789 KB Linux without MMU](https://popovicu.com/posts/789-kb-linux-without-mmu-riscv/) (6.5.5, rv64, QEMU) |
| RAM | tinyconfig kernel is 789 KB uncompressed. A Buildroot system fits in a few MB, and we have 64 MB, so this is not a limit. | same |
| Working example on LiteX/VexRiscv? | **I did not find one.** All LiteX Linux examples use an MMU (VexRiscv-SMP/linux). Known rv32 nommu examples are emulators (mini-rv32ima, uc-rv32ima on ESP32-C3) and KianV (own SoC; also has an Sv32 variant). | [xhackerustc/uc-rv32ima](https://github.com/xhackerustc/uc-rv32ima), [splinedrive/kianRiscV](https://github.com/splinedrive/kianRiscV) |
| Can it run on our **Lite** SoC? | **Not directly.** `lite` is `rv32im` (GCC_FLAGS: `-march=rv32i2p0_m`), so it has M (iterative, 0 CC_MULT), **but no A**. Correction to §9 in SOC_PHASE2, which says "lite has no A/M": it has M. The nommu candidate is the **`imac`** variant: `GenCoreDefault --csrPluginConfig all --atomics true --compressedGen true`, with the same 4K cache as `standard`, but with an MMU. Emulating A in a trap handler is not possible because the kernel runs in M-mode (HYPOTHESIS). | `litex/soc/cores/cpu/vexriscv/core.py` l. 34–80; `pythondata-cpu-vexriscv/verilog/Makefile` l. 15–25 |
| Is it worth it? | **No.** `standard` (derived from the same core as `imac`) with netboot does not fit (76%, J7), while SMP with MMU fits at 55%. The difference comes from SMP connecting LiteDRAM natively (Ldw16) and accessing peripherals more slowly. nommu would also need our own kernel and a uClibc + elf2flt userspace, which is a lot of software work with no hardware gain. | Jelena's table §9 + J7 |

## 6. SaxonSoc — instruction #28 (6)

- [SpinalHDL/SaxonSoc](https://github.com/SpinalHDL/SaxonSoc) (branch dev-0.3) has BSPs for **ULX3S (ECP5), Arty-A7 and Efinix Xyloni**. **There is no GateMate BSP.**
- For ULX3S there is a bitstream `saxonsoc-ulx3s-linux-12f.bit`, so Linux with MMU on ECP5 12F (about 12k LUT4) and 32 MB SDRAM ([dok3r/ulx3s-saxonsoc wiki](https://github.com/dok3r/ulx3s-saxonsoc/wiki/SaxonSoc-on-ULX3s), [LinuxGizmos](https://linuxgizmos.com/lattice-fpga-sbcs-can-run-linux-on-risc-v-softcore/)). The exact configuration (cache, clock) and utilisation are not on those pages.
- **HYPOTHESIS:** SaxonSoc on ECP5 12F proves that VexRiscv with MMU is small enough for the ~20k LUTs of GateMate too. Our SMP at 55% already proves the same.
- **Assessment:** a GateMate port needs a new BSP in SpinalHDL, SBT/Java, our own U-Boot and DTS, and it has no LiteEth/1G MAC. It has no advantage over the LiteX SMP that already works. **I do not recommend it.**

## 7. Shrinking the rest of the LiteX SoC (so that SD fits next to Linux and ETH)

The goal is to bring `SMP + MAC + SD` down from 77% to below ~71%, the placer limit from J7. We need to save about 2 500–3 000 CPE_LT.

| # | Lever | Expected effect | Evidence / source | Risk |
|---|---|---|---|---|
| R1 | **SPI-SD instead of LiteSDCard** (`add_spi_sdcard()`, as on the Kölsch: `"spisdcard"`) | LiteSDCard (native, DMA, FIFOs) is the 55% → 77% difference, about 9 000 CPE. SPI-SD is a simple SPI master with a few hundred CPEs (HYPOTHESIS). Linux sees it through `mmc_spi`: DTS `compatible = "litex,litespi"`, `litespi,sck-frequency = <1500000>`. | `make.py` l. 350–353; Kölsch `soc_capabilities={"serial","spisdcard"}`; `litex_json2dts_linux.py` l. 998–1021 | slow: SCK 1.5 MHz gives about 0.18 MB/s, enough for a persistent rootfs, not for large transfers. The kernel must have LiteSPI and `mmc_spi`: **prebuilt 5.14 has them** (verified, §11.2). `spisdcard` pins for ULX5M-GS already exist in litex-boards (§11.3). |
| R2 | ROM 64 KiB → 32 KiB (BIOS lite) | −16 RAM_HALF, few CPEs | Jelena §9: ROM is the largest BRAM consumer, and J13 says ROM 48K does not save | BIOS must keep netboot |
| R3 | SRAM 8 KiB → 6 KiB | −1 RAM_HALF | the linux-on-litex-vexriscv default is `integrated_sram_size 0x1800` (`boards.py` l. 13–16) | low |
| R4 | no hardware stack (ICMP FIFO, Etherbone, ARP) | already done (`--eth-mode mac`) | Jelena smpMn | — |
| R5 | ethmac 2 RX + 2 TX slots → 1 + 1 | −2 to −4 RAM_HALF | Jelena §9 | lower RX throughput |
| R6 | yosys `setattr -unset ram_style a:ram_style=distributed` | moves LUT-RAM (regfile, TLB etc.) into BRAM, so it saves CPEs. YosysHQ tests 108/112 build this way too. | prjpeppercorn 112 Makefile | more RAM_HALF, and BRAM is short unless R2 is done. Not measured on our SoC. |
| R7 | `--without-out-of-order-decoder` | see §4 | — | needs SBT |

**Recommended order:** R1 → measure; if above 71%, add R6; if BRAM runs out, add R2.

## 8. Options table (summary)

| Option | Resources | Evidence | Risk | Recommendation |
|---|---|---|---|---|
| **A. VexRiscv-SMP 1c 4K/4K MMU + 1G MAC, no SD** (current) | 55% LT, 45/64 RAM_HALF, 4 MULT, 4/4 BUFG | **Linux 5.14 on the board 3/3** (TASK-5033/5034); same core as Kölsch | low | **KEEP as the baseline** |
| **B. A + SPI-SD** (Kölsch style) | HYPOTHESIS about 57–60% LT | Kölsch profile (`spisdcard`) | medium: needs P&R; kernel drivers and pins already exist (§11.2, §11.3), and the DTS node `litex,litespi` + `mmc-slot` is generated by `litex_json2dts_linux` | **NEXT STEP** for a persistent rootfs |
| C. A + LiteSDCard | 77% LT | placer fails (smpM) | high | no |
| D. Own Buildroot (`IP_PNP`, correct cpio) | 0 gateware | #164 + `make.py` | low, only build time | **YES**, in parallel with B |
| E. VexRiscv `linux` (non-SMP) | 83% / 79% (no-dsp) | placer fails | high | no |
| F. nommu on `imac` | HYPOTHESIS about 70–76% (standard 76% fails) | no LiteX example | high, large software effort | no |
| G. nommu on `lite` | — | lite has no A | blocked | no |
| H. SaxonSoc | unknown on GateMate | ULX3S 12F Linux | high (BSP port) | no |
| I. VexiiRiscv `linux` | unknown (only P&R test 121 on Olimex A1) | prjpeppercorn 121 | medium: newer LiteX, not booted on GateMate | experiment only |
| J. A2/A4 (larger chip) | — | test 120 (4 cores) A2 only | needs a new board | not applicable to ULX5M-GS |

## 9. DOOM (instruction #30)

Per instruction #31 I do not duplicate this chapter. See Jelena's document **`docs/RESEARCH_DOOM_DVI_2509_TASK-5036.md`** on branch `doom-dvi-2509` (commit `3684e8e`) and my review (§10, corrections D1–D8, commit `5337c88`, TASK-5037).

Link to Linux:
- DVI needs 2 global nets, and the 1G SoC uses 4/4 CC_BUFG. So **Linux + 1G + DVI cannot run at the same time**.
- DOOM as an application runs on a SoC without 1G.
- For DOOM speed the D-cache is decisive (SMP has one), not CC_MULT.

## 10. Sources

- https://github.com/litex-hub/linux-on-litex-vexriscv (`boards.py` l. 871–908, `make.py` l. 240–353; commit `05fc5e4`, 2026-09-14)
- https://github.com/litex-hub/linux-on-litex-vexriscv/pull/428 , /pull/422 , /issues/164
- https://github.com/litex-hub/litex-boards/pull/679 , /pull/673 ; https://github.com/enjoy-digital/litedram/pull/366 ; https://github.com/enjoy-digital/litex/pull/2274
- https://github.com/YosysHQ/prjpeppercorn-test-cases (108, 112, 119, 120, 121; commits `6d11041`, `7aa28ed`, `8ed68d7`)
- https://machdyne.com/product/kolsch-computer/ ; https://github.com/machdyne/kolsch
- https://github.com/SpinalHDL/SaxonSoc ; https://github.com/dok3r/ulx3s-saxonsoc/wiki/SaxonSoc-on-ULX3s
- https://lkml.iu.edu/hypermail/linux/kernel/2403.3/07337.html ; https://github.com/cnlohr/mini-rv32ima ; https://popovicu.com/posts/789-kb-linux-without-mmu-riscv/
- local: `~/app/litex-1g-deps/{litex,litedram,pythondata-cpu-vexriscv,pythondata-cpu-vexriscv_smp}`; `docs/SOC_PHASE2_20260925_TASK-5033.md`; `docs/LESSONS_GATEMATE.md` (J7)

## 11. Follow-up and verification (Jelena, TASK-5038)

### 11.1 Repeated check of local claims

| Claim (§) | Command | Output | Result |
|---|---|---|---|
| Local LiteX contains #2274 (§1.1) | `git -C ~/app/litex-1g-deps/litex log --oneline \| grep invert` | `dbca01b0e colognechip: DDR should not be inverted` | ✅ |
| litedram has `W989D6DBGX6` (§1.1) | `grep -n W989D6DBGX6 litedram/modules.py` | `574:class W989D6DBGX6(SDRModule):` | ✅ |
| SMP core reduction options (§4) | `sed -n 60,100p litex/soc/cores/cpu/vexriscv_smp/core.py` | `--without-out-of-order-decoder`, `--icache/dcache-size`, `--itlb/dtlb-size`, `--hardware-breakpoints` (default 1) exist | ✅ |
| `lite` = rv32im, `imac` = rv32imac (§5) | `grep -n 'lite\|imac' litex/soc/cores/cpu/vexriscv/core.py` | l. 65: `-march=rv32i2p0_m`, l. 70: `-march=rv32i2p0_mac` | ✅ Dora's correction holds: `lite` has M, no A. SOC_PHASE2 (branch `linux-vexriscv-smp`, l. 195) still says "lite has no A/M", so that line should be fixed in the next commit on that branch. |

### 11.2 Does the prebuilt 5.14 kernel have an SPI-SD driver? — YES

Dora left this as a HYPOTHESIS (§7 R1). I checked the `Image` from `linux_2022_03_23.zip`, the same one that boots on the board (`~/.tmp/t5033/linux/Image`, 7 531 468 B):

```
$ strings Image | grep -m1 "Linux version"
Linux version 5.14.0 (florent@panda) (riscv32-buildroot-linux-gnu-gcc.br_real (Buildroot 2021.08-381-g279167ee8d) 10.3.0, ...) #1 SMP Tue Sep 21 12:57:31 CEST 2021
$ strings -n4 Image | grep -E "mmc_spi|litespi|litex,mmc"
litex,litespi
litex,mmc
litespi,max-bpw
litespi,sck-frequency
litespi,num-cs
litespi
mmc_spi
```

- `litex,litespi` and `litespi,*` are strings of the LiteX SPI master driver, and `mmc_spi` is MMC-over-SPI. These are exactly the keys that `litex_json2dts_linux.py` l. 998–1021 writes when the SoC has `spisdcard`.
- `litex,mmc` (LiteSDCard) is also in the kernel, so software is not the reason option C is dropped. It is dropped because of P&R (77%).
- Counts: `ext4` 315 hits, `vfat` 3, which means the kernel can mount a persistent rootfs from the card.
- `IP-Config` 0 hits: confirms Jelena's finding that this kernel has no `IP_PNP` (§3), so `ip=` really does not work.

**Consequence:** option B does not need our own Buildroot (D). A gateware with `add_spi_sdcard()` and a DTS from `mkdts.py` is enough. D is still needed only for `ip=` and a correct `rootfs.cpio`.

Limit of this check: the strings prove the code is built in (`=y`), but not that it works on our board. Only a boot with the card proves that.

### 11.3 SPI-SD pins on ULX5M-GS already exist

`gateware/target_soc.py` l. 103 uses `intergalaktik_ulx5m_gs.Platform`, and that platform (`litex-boards/.../intergalaktik_ulx5m_gs.py` l. 73–84) has both resources on the same slot:

```
("spisdcard", 0, clk IO_NA_A3, mosi IO_NA_B3, cs_n IO_NA_A2, miso IO_NA_A1)
("sdcard",    0, data IO_NA_A1 IO_NB_A5 IO_NA_B2 IO_NA_A2, cmd IO_NA_B3, clk IO_NA_A3)
```

SPI-SD uses a subset of the native SD pins (CLK, CMD→MOSI, DAT3→CS, DAT0→MISO). So option B needs no platform change. It only needs `self.add_spi_sdcard()` instead of `self.add_sdcard()` in `target_soc.py` l. 188 (a new choice, e.g. `--sdcard spi|native`).

### 11.4 What changes in the recommendation

| Option | Before (Dora) | After follow-up |
|---|---|---|
| B. A + SPI-SD | medium risk: kernel and DTS unverified | **lower risk:** kernel has `mmc_spi` + `litex,litespi`, pins exist; only P&R (HYPOTHESIS 57–60% CPE_LT) and a boot with the card remain |
| D. own Buildroot | "in parallel with B" | no longer a prerequisite for B, only for `ip=` and a correct cpio |

**The best option is still A + B** (VexRiscv-SMP 1c 4K/4K MMU + 1G MAC + SPI-SD, Kölsch style). First step on the board: build `smp8_9 … --sdcard spi` and measure CPE_LT. If it is below ~71%, boot with `root=/dev/mmcblk0p2` follows.

Hand-off status: the instruction on TASK-5033 returns HTTP 409 (task closed), so Dora handed in the findings as TASK-5039 (waiting for Goran's decision). This document belongs to the GATEMATE_ETH project, not to the PRJ-033 inbox.
