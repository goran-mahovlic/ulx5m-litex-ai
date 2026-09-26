# Revizija: duplikati LiteX-a i nepotrebne datoteke (26. 9. 2026.)

Pitanje: LiteX projekti obično imaju malo datoteka, jer je većina već u LiteX-u. Što je u `ulx5m-gs-linux-sbc/`
duplo ili višak?

Usporedba je rađena prema LiteX stablu `~/app/litex-1g-deps` (LiteX `b6ae9e0b2`, LiteEth `9654767`, LiteDRAM
`51de2b0`, LiteX-Boards `8741034`, LiteSDCard `17718d9`, Migen `e19524c`). Kriterij „koristi se” = preporučeni build
`grec_3` (naredba u korijenskom README.md) i build `ghrec_1` (isti + `--with-usb-hid`), jer su to jedina dva
bitstreama u `bitstreams/`.

Stanje prije čišćenja je sačuvano u tagu **`pre-cleanup-20260926`** (tamo su i CPU-less dizajni `target_eth.py`
/ `target_gbe.py` i sva dijagnostika). Stari zapisnici u `docs/` i dalje spominju te datoteke. To je povijest i
ne mijenja se, a datoteke se nalaze u tagu.

## Sažetak

| | prije | poslije |
|---|---|---|
| datoteka u `ulx5m-gs-linux-sbc/` (git) | 261 | 113 |
| `gateware/` | 29 (Python 4 248 redaka + 2 Verilog modula) | 14 (Python 1 368 redaka, Verilog samo Emardov USB) |
| `sim/` | 27 | 6 |
| `tools/` | 153 | 47 |
| `test_script/` | 3 | 0 |
| lokalne izmjene LiteX-a | 2 (patch) | **0** (čisti upstream `b6ae9e0b2`) |

(113 = 109 nakon brisanja + ovaj dokument + `tools/README.md` + `sim/tb_mdio_core_equiv.py` + `tools/dj_probe.sh`; `mdio_core.v` zamijenjen s `mdio_core.py`.)

## Kako je provjereno da se dizajn nije promijenio

1. Elaboracija bez P&R (`target_soc.py` bez `--build`, tj. LiteX generira Verilog i prevede BIOS) s naredbom iz
   korijenskog README-a, uz `SOURCE_DATE_EPOCH` i `--no-ident-version`, da datum ne ulazi u izlaz. Dva uzastopna
   pokretanja daju bajt-identičan izlaz, pa je usporedba smislena.
2. Usporedba svih datoteka u `build/<x>/gateware/` bez komentara (`/* … */` sadrži stablo hijerarhije kojemu se
   poredak mijenja od pokretanja do pokretanja) i bez apsolutne putanje builda.
3. Rezultat, korak A (brisanje i čišćenje koda, LiteX patch još aktivan):

   | build | `.v` (13 524 / 13 755 redaka) | `.ccf` | `.sdc` | `rom.init` | `mem.init` | VexRiscv `.v` | `csr.json` |
   |---|---|---|---|---|---|---|---|
   | grec_3 | isti | isti | isti | isti | isti | isti | isti |
   | ghrec_1 (`--with-usb-hid`) | isti | isti | isti | isti | isti | isti | — |

   Jedina razlika je u `.ys`: `read_verilog …/tools/uhello/mdio_core.v` → `…/gateware/verilog/mdio_core.v`
   (datoteka je premještena s `git mv`, sadržaj je isti).
4. Korak B (bez LiteX patcha, bez `CONFIG_BIOS_PRINT_IDENT`): logika je ista, a BIOS je 96 B manji (36 500 → 36 404 B),
   pa ROM ima 9 101 umjesto 9 125 riječi. Razlika u `.v` je samo `reg [31:0] rom[0:9124]` → `rom[0:9100]`.
   U BIOS-u nedostaje jedan redak ispisa („Ident: …”). Bitstreamovi u `bitstreams/` su izgrađeni prije toga i taj
   redak još ispisuju.
5. Simulacije koje su ostale: `tb_gbe_phy` ALL TESTS PASSED, `tb_scaler2x` PASS, `tb_sticky_lock` ALL PASS,
   `tb_watchdog` PASS. `sim/test_boot_option.py` 5/5 PASS (none, serial, sdcard, netboot, sdnet).
6. Puni P&R nije pokrenut: generirani Verilog, `.ccf` i `.sdc` su isti, pa bi s istim seedom i alatima dao isti
   bitstream. Ništa nije flashano.

## Tablica: `gateware/`

„U LiteX-u?” znači postoji li u LiteX stablu nešto što radi isti posao.

| Datoteka | U LiteX-u? | Odluka | Razlog |
|---|---|---|---|
| `target_soc.py` | djelomično: `litex_boards/targets/intergalaktik_ulx5m_gs.py` | **ostaje, očišćen** (521 → 420 redaka) | Upstream target ima samo CPU, SDRAM i LED. Nema Ethernet, DVI ni USB, a CRG mu troši globalnu mrežu na `sys_ps` (`targets/intergalaktik_ulx5m_gs.py:48-50`), koje s 1G Ethernetom nema (4 mreže: sys, gtx, TXC, grx). Upstream koristi `IS42S16160` (32 MB, `:79`), a ploča ima IS42VM16320E (64 MB). Platforma se ne kopira: koristi se upstream `intergalaktik_ulx5m_gs.Platform`, a pinovi za ETH, DVI i USB dodaju se s `add_extension`, jer ih upstream platforma nema (`platforms/intergalaktik_ulx5m_gs.py:14-86`). Uklonjene opcije: hwstack (hardverski ARP/ICMP/Etherbone), dvotaktni DVI, `--video-terminal`, `--video-det-load`, `--video-pix-freq`, `--with-usb` (OHCI), `--sdram-drive`, `--sdram-slew`, `--sdram-clk ps90`, `--ip`. `--sdram-clk inv` i `--eth-mode mac` ostaju kao jedina vrijednost, da naredba iz README-a i dalje radi. |
| `target_soc.py: IS42VM16320` | ne (`litedram/modules.py:448,457` imaju samo `IS42S16160`, `IS42S16320`) | ostaje | `IS42S16320` ima istu geometriju, ali je 3,3 V dio s drugim vremenima (tRP/tRCD 20 ns, tREFI 64 ms/8192). IS42VM16320E-75 je 1,8 V mobilni SDR: tRP/tRCD 22,5 ns, tRAS 45 ns, a tREFI je smanjen na 7,6 µs jer LiteDRAM zaokružuje prema gore (TASK-5047). Zamjena bi promijenila kontroler. |
| `target_soc.py: add_cpu_mac_regions()` | da, dio `SoC.add_ethernet()` (`litex/soc/integration/soc.py:2618`) | ostaje | `add_ethernet(data_width=8)` gradi MAC s `dw=32` u domenama `eth_tx`/`eth_rx` (`soc.py:2656-2672`). `with_sys_datapath` uključuje samo za `data_width=32`, a to je isprobano: RX nikad ne preda okvir CPU-u (TASK-5033). Naš PHY nema domene `eth_tx`/`eth_rx`, radi u sys. Kombinacija `dw=8` + `with_sys_datapath=True` kroz `add_ethernet` ne postoji, pa se regije, IRQ i konstante dodaju ručno, istim pozivima kao u LiteX-u. |
| `target_soc.py: _eth` (pinovi) | ne (platforma nema `eth`) | ostaje (premješten iz `target_gbe.eth_io()`) | Bez njega bi `target_soc.py` ovisio o CPU-less dizajnu. |
| `gbe_phy.py` | ne (`liteeth/phy/` ima samo PHY-eve za ECP5, 7-series, US, Gowin, Efinix, Agilex; nijedan za GateMate) | ostaje | LiteEth RGMII PHY-evi drže asinkrone CDC FIFO-e u domenama od 125 MHz. Na GateMateu ti putovi nakon routinga rade samo na 52–65 MHz (`docs/GBE_FEASIBILITY_20260921_TASK-4961.md`). `gbe_phy.py` na 125 MHz drži samo IO registre i posmačni registar, a okvir prelazi u sys kroz BRAM. |
| `pll_stdy.py` | djelomično: `GateMatePLL` (`litex/soc/cores/clock/colognechip.py`) | ostaje (32 retka, podklasa) | Upstream `GateMatePLL` spaja `USR_LOCKED_STDY_RST = 0` i `USR_PLL_LOCKED_STDY = Open()` (`colognechip.py:154,156`). Nama treba sticky flag za CSR `pll_stdy` (dijagnostika PLL šuma, TASK-5047). `lock_req` je već upstream (`colognechip.py:37,148`) i koristi se. |
| `sticky_lock.py` | ne | ostaje | Upstream PLL resetira domene iz sirovog `USR_PLL_LOCKED` (`colognechip.py:104,157,162`). Na ovoj ploči flag trza (24/29 JTAG uzoraka), pa bi svaki trzaj resetirao sys. |
| `video_sbc.py` | djelomično: `VideoHDMIPHY`, `VideoFrameBuffer`, `VideoTimingGenerator` (`litex/soc/cores/video.py:1237, 1022, 194`) | **ostaje, očišćen** (267 → 223 retka) | `VideoTimingGenerator` i `TMDSEncoder` se koriste iz LiteX-a. `VideoHDMIPHY` traži zasebnu domenu piksel-takta; ovdje su sve 4 globalne mreže zauzete, pa video radi u `gtx0` (125 MHz) s clock-enableom 1/5 (`DVIPHY`, `_Serializer10to2`). `VideoFrameBuffer` čita 640x480 rgb565: to je 92 % propusnosti 16-bitnog SDRAM-a na 20 MHz. `FrameBuffer2x` čita 320x240 i udvostručuje piksele u hardveru. Uklonjen je dvotaktni put (`Divide5`, grane bez CE), jer bez Etherneta nije u preporučenom buildu. |
| `usb_hid.py` + `verilog/usbhost/*` (7) | djelomično: `USBOHCI` (`litex/soc/cores/usb_ohci.py:29`) | ostaje | Koristi ga `ghrec_1` (bitstream u `bitstreams/`). OHCI traži PLL od 48 MHz (5. globalna mreža uz 1G) i kernel s `CONFIG_USB_OHCI_HCD_PLATFORM`, a prebuilt 5.14 ga nema. Emardov low-speed HID host radi na 125 MHz/21 preko lokalnog routinga. Licenca GPL (`verilog/usbhost/README.md`). |
| `verilog/mdio_core.v` → `mdio_core.py` | djelomično: `LiteEthPHYMDIO` (`liteeth/phy/common.py:34`) | **prepisan u Migen** (uputa #69), Verilog uklonjen | LiteEth ima samo bit-bang MDIO preko CSR-a, dakle PHY bi konfigurirao softver. KSZ9031 mora oglašavati samo 1000FD prije nego BIOS krene s netbootom, bez CPU-a. `MDIOCore` to radi u hardveru i daje registre za CSR `phy_status0/1`. Dokaz ekvivalencije i proba na ploči: odjeljak „MDIO: Verilog → Migen” niže. |
| `__init__.py` | — | **uklonjen** | Oznaka paketa za `from gateware.eth_stack import …`. Nitko ne uvozi `gateware` kao paket. |
| `eth_stack.py` | da: `LiteEthUDPIPCore` (liteeth) + `TXLastBE8` | **uklonjen** | Koristio se samo u hwstack načinu (`--eth-mode hwstack`), koji preporučeni build ne koristi. `TXLastBE8` je već bio ugašen (`tx_last_be_fix=False`), jer LiteX ≥ 7fca6dba sam postavlja `last_be`. |
| `target_eth.py` | — | **uklonjen** | CPU-less 100 Mb/s dizajn (TASK-4999). Nije dio SBC-a. Bitstreamovi mu nisu u repozitoriju. U tagu `pre-cleanup-20260926`. |
| `target_gbe.py` | — | **uklonjen** | CPU-less 1 Gb/s dizajn (ping bez CPU-a, TASK-5032). Iz njega je u `target_soc.py` prenesena samo lista pinova. U tagu. |
| `phy_rgmii_gatemate.py` | da: kopija LiteEth RGMII PHY-a s GateMate primitivima | **uklonjen** | 100M PHY za `target_eth.py`. 1G koristi `gbe_phy.py`. |
| `ulx5m_eth_platform.py` | ne | **uklonjen** | Pinovi za `target_eth.py`. |
| `crg.py` | da: CRG iz `targets/intergalaktik_ulx5m_gs.py` | **uklonjen** | CRG za `target_eth.py`. `target_soc.py` ima svoj `SoCCRG`. |
| `mdio_sequencer.py` | da: `LiteEthPHYMDIO` + softver | **uklonjen** | 100M upisi (TASK-4963). U 1G SoC-u to radi `mdio_core.v`. |
| `mdio_diag.py`, `jtag_probe.py`, `verilog/jtag_mailbox.v`, `pll_serial.py`, `status_leds.py`, `beacon.py`, `l2_beacon.py`, `raw_tx.py` | — | **uklonjeni** | Dijagnostika iz faze traženja kvara (UART dump MDIO registara, JTAG mailbox, serijski PLL bitovi, LED-ovi, UDP/L2 beacon, sirovi TX okviri). Koristio ih je samo `target_eth.py` ili `target_gbe.py`. |
| `pll_stdy.py`, `sticky_lock.py`, `gbe_phy.py`, `video_sbc.py`, `usb_hid.py` | vidi gore | ostaju | |

Platforma ploče nije kopirana nigdje: svi dizajni koriste `litex_boards.platforms.intergalaktik_ulx5m_gs`.

`_status_leds` u `target_soc.py` ostaje. Upstream ima iste pinove kao `user_led_n` (aktivni u nuli, drugi redoslijed
LED 4/5), a naš dizajn ih vozi izravno (bez inverzije) s `DRIVE=3`. Zamjena bi promijenila polaritet i redoslijed LED-ova.

## Tablica: ostalo

| Datoteka / mapa | Odluka | Razlog |
|---|---|---|
| `docs/litex-b6ae9e0b2-local.patch` | **uklonjen** | Dio za tristate (`common.py`) je NO-OP. Python izraz `~a if c else ~b` isti je kao `~(a if c else b)`. Dokaz: build s vraćenim upstream `common.py` daje identičan `.v` (13 524 retka; `CC_IOBUF` se koristi 64 puta, dakle kod je stvarno bio izveden). Dio za BIOS ispisuje samo jedan redak („Ident: …”). Uputa #32 ga je uvela jer su se u bannerima vidjele dvije adrese (.212 hardver, .213 CPU). Hardverski stog je sada uklonjen, a BIOS pri netbootu sam ispisuje „Local IP: 192.168.10.213” (`bios/boot.c:848`) i ima naredbu `ident`. Zato patch više ne treba, i LiteX je čisti upstream. |
| `docs/litex-bios-print-ident.patch` | **uklonjen** | Duplikat drugog dijela gornjeg patcha. |
| `ter-u16b.bdf` | **uklonjen** | Terminus font (licenca OFL). Nijedna datoteka ga ne koristi (`grep -r ter-u16b` = 0 pogodaka). |
| `build/Makefile` | **uklonjen** | Gradi i flasha `target_eth.py` (`build/eth/…`), dakle 100M dizajn. |
| `build/s_grec_3/`, `build/s_ghrec_1/` (`csr.json`, `csr.csv`) | ostaju | `tools/linux/mkdts.py` iz njih radi DTS za dva bitstreama u `bitstreams/`. |
| `test_script/` (3) | **uklonjen** | UDP echo i UART proba za CPU-less dizajne. |
| `sim/tb_gbe_phy.py`, `tb_scaler2x.py`, `tb_watchdog.py`, `tb_sticky_lock.py`, `test_boot_option.py` | ostaju | Testiraju module koji su ostali. Iz `tb_sticky_lock.py` je izbačen dio s `mdio_sequencer`. `test_boot_option.py` je prilagođen: nema hwstacka, dodan `sdnet`. |
| `sim/tb_beacon, tb_l2_beacon, tb_io50, tb_lastbe, tb_mdio_diag, tb_mdio_sequencer, tb_rgmii_tx_sf, tb_stack, tb_txc_phase`, `lastbe_env.sh`, `test_refclk_oe.sh`, `io50rtl/`, `postsynth/` | **uklonjeni** | Testiraju uklonjene module ili su jednokratne provjere (TASK-4999 100M, LiteX `last_be` regresija). |
| `tools/soc_build.sh`, `tools/sbc_env.sh` | ostaju | `soc_build.sh` sada sourca `sbc_env.sh` (prije su obje imale iste putanje). Redak za `pythondata-misc-usb_ohci` je maknut: OHCI je uklonjen, a `env.sh` ionako dodaje sve `pythondata-*`. |
| `tools/linux/` (`mkdts.py`, `netboot_app.sh`, `linux_boot.sh`, `lx_cmd.sh`, `README.md`) | ostaju | Linux: DTS, TFTP, boot na ploči. |
| `tools/linux/rv32_grec_3.dts`, `rv32_ghrec_1.dts` | ostaju | DTS za dva bitstreama u repozitoriju. Korijenski README koristi `rv32_grec_3.dts`. |
| `tools/linux/rv32_dvi_1, gcer_1, gdvi_1, gdvi_9, smp8_9, spisd_1.dts` | **uklonjeni** | DTS-ovi za buildove čiji bitstreamovi nisu u repozitoriju. `mkdts.py` ih napravi iz svakog builda. |
| `tools/doom_linux/`, `tools/rootfs/`, `tools/usbhidd/` | ostaju (`.empty` uklonjen) | DOOM, rootfs i USB tipkovnica za Linux. |
| `tools/speedtest/` | ostaje (duplikat `netboot_app.sh` uklonjen) | Mjerenje propusnosti (otvoreno pitanje „throughput under Linux”). `eth_speedtest.sh` više nema zadani bitstream kojeg nema u repozitoriju (`BIT=` je obavezan), a koristi `tools/linux/netboot_app.sh`. |
| `tools/dvi/testimg_cmds.sh`, `tools/sd/bios_cmds.sh` | ostaju | Testna slika u framebufferu i upis BIOS naredbi. |
| `tools/dvi/{idle_series,loadtest,lx_session,mitigation_sweep,pll_discriminator,vtest}.sh` | **uklonjeni** | Jednokratna mjerenja ispada slike (TASK-5040/5044/5047) s HDMI captureom na Piju. Rezultati su u `docs/SBC_DVI_USB_TASK-5040.md` i `…5047.md`. |
| `tools/t5007/`, `fabtest/`, `pnr_probe/`, `uhello/`, `uloop/`, `gbe/`, `pll_*.py` (6), `jtag_bert.py`, `jtag_mailbox.py`, `mbprobe_top.*`, `nt_all.sh`, `rxstart.sh`, `gbe_build.sh` | **uklonjeni** | Jednokratni testovi iz traženja kvara (PLL, JTAG, MDIO, fabric, nextpnr bug repro) i build/prihvat CPU-less dizajna. Nalazi su u `docs/HW_DIAG_20260923_TASK-4999.md` i `docs/LESSONS_GATEMATE.md`, a skripte u tagu. |

## Što nije dirano

- `docs/` (osim dva patcha i ovog dokumenta): zapisnici mjerenja i istraživanja. Spominju uklonjene datoteke, a
  one su u tagu `pre-cleanup-20260926`.
- `gbe_phy.py` iznutra: `txc_bufg=False` grana i `txc_sel` ostaju. To je mali, testirani PHY (`tb_gbe_phy.py`).
- `--with-sdcard` / `--sdcard spi` / `--boot sdnet`: SD kartica je u radu (korijenski README: „What does not work
  yet”), pa te opcije ostaju.
- `--video-640x240`: radna opcija (80x30 teksta) i pokrivena je s `tb_scaler2x.py`.

## MDIO: Verilog → Migen (uputa #69, #70)

`gateware/verilog/mdio_core.v` je prepisan u `gateware/mdio_core.py` (`MDIOCore`, LiteXModule): isti parametri
(`write_after`, `reg9`, `reg4`, `reg0`), isti `snap` (256 bita), isti `rst_n` PHY-a, svi registri bez reseta kao u
Verilogu. Izbačeni su UART ispis i ulaz `dbg`, jer ih SoC nije spajao (pinovi pripadaju BIOS serialu).

### 1. Simulacija (prije ugradnje)

`sim/tb_mdio_core_equiv.py`: stari Verilog (iz gita, commit `251bcb7`) i Migen modul pretvoren u Verilog vrte se
jedan do drugoga u Icarus Verilogu, svaki sa svojim modelom KSZ9031 MDIO slavea (ID 0x0022/0x1622, registri se
resetiraju s RESET_N, upisi se pamte). Svaki sys takt uspoređuje se MDC, razriješena MDIO linija, `moe`, `mdo`,
RESET_N i cijeli `snap`. RXC je asinkron, a RX_CTL pseudo-slučajan.

| slučaj | ciklusa | razlika | na kraju (snap) |
|---|---|---|---|
| SoC: WRITE_AFTER=0, REG9=0200, REG4=0001, REG0=1200, PHYAD 3 | 10 598 097 | **0** | 3456 MDC bridova, idm=08, r4=0001, r9=0200 (upis pročitan natrag) |
| WRITE_AFTER=2, REG9=0000, REG4=0101, PHYAD 0 | 14 823 601 | **0** | 4416 MDC bridova, idm=01, r4=0101, r9=0000 |
| negativna kontrola (`--mutate`: novi modul dobije REG4^0x0400) | 10 598 097 | 4 234 113 | usporedba stvarno hvata razliku (rc=1) |

### 2. Ploča (ULX5M-GS, samo `fpga-jtag gs … -r`, konzola `/dev/serial/by-id/…E660583883501E2C-if01`)

Prvo mali SoC (VexRiscv standard + BIOS + 1G, `--boot none`, `--phy-snap-csr`), pa tek onda Linux SoC.
Mapiranje kabel → ploča potvrđeno 26. 9. u 10:53: BIOS učitan s `fpga-jtag gs` ispisuje na by-id konzolu.
Svi bitstreamovi imaju `gmpack --reset` (provjereno u `build_*.sh`).

| korak | bitstream | kroz novi modul pročitano | zaključak |
|---|---|---|---|
| kontrola | stari Verilog (`mdo_1`, isti mali SoC) | R1=796D, R1F=0348, RXC 125 MHz | referentni link 1000FD |
| (a) ID | `mdt_3` (REG4=0001) | idm=0x08 → reg2 = 0x0022 na PHYAD 3 (addr=3) | MDIO čitanje radi |
| (b) upis ≠ trenutno | `mdt_2` (REG4=0C01, upis u 255. prolazu) nakon dizajna koji piše 0001 | r4=0C01, r9=0200, wrote=1 | upis novim modulom, pročitan natrag |
| (c) hardverski reset | `mdt_2` pa `mdt_4` (nikad ne piše) | poslije `mdt_2`: r4=0C01; u `mdt_4`: r0=1140, r4=01E1, r9=0300, wrote=0 | RESET_N novog modula vratio PHY na tvorničke vrijednosti |
| link | `mdt_3` (produkcijski parametri) | R1=796D, R1F=0348, RA=3800, RXC 125 MHz | isto kao stari Verilog |

Usput: s REG4=0x0C01 (pause bitovi) AN se na ovom switchu ne završi (R1=7949, RXC 25 MHz), sa 0x0001 i s tvorničkim
0x01E1 završi. To je svojstvo testne vrijednosti, ne modula (A/B s istim SoC-om).

Prva dva pokušaja (10:37, 10:45) odbačena su: na Pi je spojen drugi DirtyJTAG, a `openFPGALoader -c dirtyJtag`
otvara prvu sondu i ignorira `--busdev-num`. Pi skripte u `tools/` zato učitavaju preko `fpga-jtag` (`tools/dj_probe.sh`).

### 3. Timing i seed

Svaka promjena netliste mijenja placement, pa seed nije prenosiv. Kriterij: 0 hold prekršaja i grx (RXC) PASS na
125 MHz. Buildovi s hold prekršajima u VexRiscv D-cache BRAM putu vrte BIOS u petlji resetiranja na memtestu (mg_1:
8 prekršaja, mdt_4 seed 1: 3); svi ispravni imaju 0. Linux SoC s novim modulom (naredba iz README-a, samo seed):

| seed | hold | grx | CPU | P&R |
|---|---|---|---|---|
| 1 | 8 | 127,8 PASS | 22,7 | petlja resetiranja na ploči |
| 2 | 0 | 123,4 FAIL | 21,7 | |
| **3** | **0** | **138,7 PASS** | **25,4** | **na ploči: Linux login nakon 707 s, ping .213 5/5 i 10/10, iz Linuxa `csrpeek 0xf0002804 2` = `796d0348 38006400` (R1F=0348 = 1000FD, RXC 125 MHz)** |
| 4 | 0 | 111,0 FAIL | 23,2 | |
| 6 | 0 | 125,3 PASS | 21,3 | Linux se diže (init), rub timinga |
| 7 / 8 / 12 | 0 | 121,5 / 123,2 / 124,0 FAIL | | |
| 10 | 0 | 131,6 PASS | 21,5 | |

Seed 3 je i dalje ispravan izbor za naredbu iz korijenskog README-a, pa se naredba ne mijenja. Bitstreamovi u
`bitstreams/` ostaju oni izgrađeni prije ove revizije (stari Verilog MDIO, LiteX s patchem). Build iz sadašnjeg koda
sa seedom 3 je provjeren na ploči (gore), ali nije dodan u `bitstreams/`.
