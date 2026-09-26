# Bitstreams — naming: ETH_GateMateA1_<DDMM>_<HHMM CEST>_<Description>.bit

Loading (SRAM only): `openFPGALoader -c dirtyJtag <bit> -r`. All of them have CMD_CFGRST (`gmpack --reset`).

Older bitstreams and CPU-less designs (100 Mb/s `target_eth.py`, 1 Gb/s `target_gbe.py`) are no longer in this
repository; their descriptions and sources are in git tag `pre-cleanup-20260926` (see `docs/REVIEW_LITEX_DUPLICATES.md`).
The folder holds only the two bitstreams marked below: `grec_3` and `ghrec_1`.

## TASK-5040 (DVI / Linux fbcon / DOOM), branch sbc-dvi-usb
| Bitstream | Build | Result |
|---|---|---|
| ETH_GateMateA1_2509_1651_Linux_DVI_s1.bit | dvi_1: SMP + --with-video --boot serial (2 clocks, no ETH) | DVI image confirmed (Goran 17:16); 0/45 dropouts at idle, 16/30 under SDRAM mem_test |
| ETH_GateMateA1_2509_1732_Linux_GbE_DVI_s1.bit | gdvi_1: + --with-gbe --eth-mode mac --boot netboot, video in gtx0 with CE | Linux + fbcon + ping; image drops out (36/40 at boot) |
| ETH_GateMateA1_2509_1859_Linux_GbE_DVI_neg1.bit | gneg_1: like gdvi + --video-ce-rep --video-neg-sync | Linux + fbcon + DOOM; 0/30 at idle, 2/30 with DOOM, 4/60 at boot. Left on the board (netboot linuxdvi) |
Cause of the dropouts: VDD_PLL (R23 1 Ω / C42 100 nF, L5 DNP) — the PLLs lose lock under SDRAM load, docs/SBC_DVI_USB_TASK-5040.md §7.
| ETH_GateMateA1_2509_2330_Linux_GbE_DVI_lr1ref_1.bit | gref_1: gneg + STDY CSR (LOCK_REQ=1 reference, TASK-5047) | BIOS 2x mem_test 32 MiB: 0/30 good captures, resync 17900 |
| ETH_GateMateA1_2509_2330_Linux_GbE_DVI_lr0_1.bit | glr0_1: + --pll-lock-req 0 | BIOS 2x mem_test: 30/30; one of two Linux boots permanently black (resync = frames) -> see rec3 |
| **ETH_GateMateA1_2509_2330_Linux_GbE_DVI_lr0_rec3.bit** | grec_3: + --pll-lock-req 0 --video-recover, seed 3 | **Recommended.** BIOS 30/30 under load, Linux boot 80/80, 19 min resync 0; on the board, TFTP linux (DTB mkdts.py build/s_grec_3) |
| ETH_GateMateA1_2509_2330_Linux_GbE_DVI_USBHID_rec1.bit | ghrec_1: grec + --with-usb-hid, seed 1 (74.8% LT) | P&R rc=0, 0 hold; NOT loaded; waiting for a test with a keyboard (5 V on VBUS) |
