# Bitstreamovi — ime: ETH_GateMateA1_<DDMM>_<HHMM CEST>_<Opis>.bit

Učitavanje (samo SRAM): `openFPGALoader -c dirtyJtag <bit> -r`. Svi imaju CMD_CFGRST (`gmpack --reset`).

Starije bitstreamove i CPU-less dizajne (100 Mb/s `target_eth.py`, 1 Gb/s `target_gbe.py`) ovaj repozitorij više
ne sadrži; opisi i izvori su u git tagu `pre-cleanup-20260926` (vidi `docs/REVIEW_LITEX_DUPLICATES.md`).
U mapi su samo dva bitstreama označena ispod: `grec_3` i `ghrec_1`.

## TASK-5040 (DVI / Linux fbcon / DOOM), grana sbc-dvi-usb
| Bitstream | Build | Rezultat |
|---|---|---|
| ETH_GateMateA1_2509_1651_Linux_DVI_s1.bit | dvi_1: SMP + --with-video --boot serial (2 takta, bez ETH) | DVI slika potvrđena (Goran 17:16); 0/45 ispada u mirovanju, 16/30 pod SDRAM mem_test |
| ETH_GateMateA1_2509_1732_Linux_GbE_DVI_s1.bit | gdvi_1: + --with-gbe --eth-mode mac --boot netboot, video u gtx0 s CE | Linux + fbcon + ping; slika ispada (36/40 pri bootu) |
| ETH_GateMateA1_2509_1859_Linux_GbE_DVI_neg1.bit | gneg_1: kao gdvi + --video-ce-rep --video-neg-sync | Linux + fbcon + DOOM; 0/30 u mirovanju, 2/30 uz DOOM, 4/60 pri bootu. Ostavljen na ploči (netboot linuxdvi) |
Uzrok ispada: VDD_PLL (R23 1 Ω / C42 100 nF, L5 DNP) — PLL-ovi gube lock pod SDRAM opterećenjem, docs/SBC_DVI_USB_TASK-5040.md §7.
| ETH_GateMateA1_2509_2330_Linux_GbE_DVI_lr1ref_1.bit | gref_1: gneg + STDY CSR (LOCK_REQ=1 referenca, TASK-5047) | BIOS 2x mem_test 32 MiB: 0/30 ispravnih snimaka, resync 17900 |
| ETH_GateMateA1_2509_2330_Linux_GbE_DVI_lr0_1.bit | glr0_1: + --pll-lock-req 0 | BIOS 2x mem_test: 30/30; jedan od dva Linux boota trajno crn (resync = okviri) -> vidi rec3 |
| **ETH_GateMateA1_2509_2330_Linux_GbE_DVI_lr0_rec3.bit** | grec_3: + --pll-lock-req 0 --video-recover, seed 3 | **Preporučeni.** BIOS 30/30 pod opterećenjem, Linux boot 80/80, 19 min resync 0; na ploči, TFTP linux (DTB mkdts.py build/s_grec_3) |
| ETH_GateMateA1_2509_2330_Linux_GbE_DVI_USBHID_rec1.bit | ghrec_1: grec + --with-usb-hid, seed 1 (74,8 % LT) | P&R rc=0, 0 hold; NIJE učitan; čeka test s tipkovnicom (5 V na VBUS) |
