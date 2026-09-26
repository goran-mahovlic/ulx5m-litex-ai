# Bitstreamovi — ime: ETH_GateMateA1_<DDMM>_<HHMM CEST>_<Opis>.bit

Učitavanje (samo SRAM): `openFPGALoader -c dirtyJtag <bit> -r`. Svi imaju CMD_CFGRST (`gmpack --reset`).

## 1000 Mb/s (TASK-5032, grana gbe-1000m)

| Bitstream | Sadržaj | Rezultat na ploči (nova pločica, X1, switch 1G, Pi 100M) |
|---|---|---|
| **ETH_GateMateA1_2509_0211_GbE_Ping1G.bit** | **PREPORUČENI 1G.** `target_gbe.py`, seed 15, TXC = CLK90 kroz CC_BUFG, samokorigirajući TX prsten, MDIO upis u 1. prolazu (WRITE_AFTER 0), LiteX b6ae9e0b2 bez TXLastBE8; nextpnr SPEED/worst: gtx 128,0, grx 143,9 MHz | **1000FD (RF = 0348)**, ping `-s 0…1472` 5/5, prvi odgovor 6,07 / 7,15 / 5,47 s nakon `-r`, 3/3 uz prljavi 100M bitstream između, 0 RX dropova |
| ETH_GateMateA1_2509_0203_GbE_Ring10.bit | isto, seed 10, MDIO upis u 6. prolazu (drugi AN) | ping 5/5 3/3, prvi odgovor 12,2 / 6,9 / 7,1 s |
| ETH_GateMateA1_2509_0150_GbE_TXfix11.bit | TX bez čekanja `first`, prsten bez samokorekcije | tx_frames 36, tx_emit 0: prsten zaglavljen |
| ETH_GateMateA1_2509_0121_GbE_Diag13.bit | prvi s UART brojačima (D=) | RX 21/21 okvira, tx_frames 0 (PHY čekao `sink.first`) |
| ETH_GateMateA1_2509_0110_GbE_TXCg90s11.bit | TXC CLK90 kroz BUFG | 0 TX okvira (isti uzrok) |
| ETH_GateMateA1_2509_0057_GbE_TXC90s13.bit | TXC CLK90 fabric rutom iz PLL-a (5,8 ns) | link 1000FD, RXC 125 MHz, 0 TX okvira |

Build preporučenog (LiteX stablo `~/app/litex-1g-deps`):
`tools/gbe_build.sh f_s15 --seed 15` (= `python3 gateware/target_gbe.py --build --seed 15`, zadano `--txc-phase 90 --pnr-mode speed --perf-mode economy --adv 1000`)

Odabir seeda za 1G: sweep → uzmi seed gdje i `gbesoc_crg_gatematepll0_clkout0` (gtx) i `mdio_core.rxc` (grx) PASS na 125 MHz
(SPEED, worst). Prolazi ~2 od 14 seedova. `clkin`/`ref_clk` „FAIL na 125” je lažan (stvarno 25 MHz, zadani `--freq`).

## 100 Mb/s (TASK-4999)

| Bitstream | Sadržaj | Rezultat na ploči (nova pločica, X1) |
|---|---|---|
| **ETH_GateMateA1_2409_2141_Ping_MTUs13.bit** | **PREPORUČENI.** LiteEth, `--tx-clk-src io50 --mdio-core --l2-beacon`, ECONOMY, TXLastBE8, icmp_fifo_depth 2048, nextpnr seed 13 | ping prvi odgovor 2,95 s nakon flasha; `-s 0…1472` 5/5; 3/3 ponovljivo (i nakon „prljavog” bitstreama); 100FD (R1F = 0328) |
| ETH_GateMateA1_2409_2204_SeedP_s7.bit | **PRODUKCIJSKI** (bez dijagnostike: bez L2 beacona i mdio_core, LiteX MDIO sekvencer), io50, ECONOMY, seed 7 (eth_tx 50,23 MHz PASS, max kašnjenje RX takta 5,64 ns = najmanje) | ping 5/5, -s 1000 3/3 (seed sweep 22:0x) |
| ETH_GateMateA1_2409_2130_LastBE_Fix.bit | isto, icmp_fifo_depth 128, seed 6 | ping 3/3 10 s nakon flasha; `-s 0…120` 5/5; `-s ≥ 121` se odbacuje po dizajnu |
| ETH_GateMateA1_2409_2050_LiteEth_CFGRST.bit | io50 bez TXLastBE8 (seed 2) | ping `-s ≤ 18` prolazi, a okviri > 60 B imaju FCS = 0 |
| ETH_GateMateA1_2409_2050_TXC_CFGRST.bit | sirovi beacon eb50 (bez LiteEtha), okvir od 60 B | 58 okvira / 20 s + UART s MDIO registrima |

Build preporučenog:
`python3 gateware/target_eth.py --build --ip 192.168.10.212 --perf-mode economy --tx-pll-mode economy --no-phy-refclk --tx-clk-src io50 --l2-beacon --mdio-core --seed 13`
(nextpnr ne radi analizu holda, a RXC ide kroz fabric: ishod ovisi o seedu. Seed 8 iste mreže NE radi. Svaki novi build provjeri na ploči.)

Seed sweep i pravilo odabira: docs/seed_sweep_io50_20260924.txt, LESSONS H15.

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
