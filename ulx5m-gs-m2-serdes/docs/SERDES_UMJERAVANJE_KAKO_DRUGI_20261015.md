# SerDes umjeravanje: kako to rade drugi i predloženi postupak za GateMate

**Za:** Goran (pitanje 15.10.2026. u 19:38) · **Napisala:** Dora (TASK-5528) · **Datum:** 15.10.2026.
**Opseg:** ULX5M GS ↔ M2, CCGM1A1 `CC_SERDES`, 2,5 Gb/s, lanac GS → baseboard → PCIe utor → FFC adapter → M.2.
Ploče i Pi nisu dirani (mjerenja su u TASK-5527, radi ih Jelena).

Oznake: **[X1]** je vanjski izvor (popis u §8), **[L…]** je naš dokument. **IZVEDENO** znači da je zaključak moj, iz navedenih izvora,
a ne tvrdnja proizvođača. **HIPOTEZA** znači da nešto još nije izmjereno na našim pločama.

---

## 0. Kratki odgovor

1. **Pravila i alati postoje, ali svaki proizvođač ima svoje, vezano uz vlastiti čip.** Jedini javni, za sve proizvođače isti
   „workflow” je PCIe Gen3 ekvalizacija: 11 TX preseta P0–P10 i faze 0–3 s mjerilom BER < 10⁻⁴, pa fino podešavanje do BER < 10⁻¹² [X9][X10].
   Svi veliki proizvođači imaju alat koji **mete parametre i mjeri BER ili otvor oka**: Xilinx IBERT/ISI sweep [X2][X3],
   Intel Transceiver Toolkit Auto Sweep + EyeQ [X5][X6], Microchip SmartDebug [X7]. Open-source alati koji tu petlju automatiziraju
   (IBERTpy, ChipScoPy, pyIBERT) rade **samo za Xilinx** [X13][X14][X4]. Za GateMate gotov workflow nisam našla.
2. **Redoslijed je svugdje isti:** prvo TX (amplituda, pa pre/post-cursor), zatim RX (CTLE, pojačanje, DFE), CDR na kraju.
   Mjerilo je površina oka ili BER, a parametar je „gotov” tek kad se iza vrha vidi pad, tj. prekompenzacija [X6].
3. **Varijaciju po resetu svi rješavaju na jedan od tri načina:**
   (a) adaptacija na početku pa **zamrzavanje** (Xilinx HOLD portovi [X1], TI DS280DF810 zamrzne CTLE nakon locka [X11],
   Intel *initial* adaptacija [X5]);
   (b) **fiksna radna točka** iz prethodnog sweepa, uz pokrenutu samo DC offset kalibraciju (PolarFire `Static_DFE` [X7]);
   (c) **ponovna kalibracija dok mjerilo nije zadovoljeno** (PCIe faze s pragom BER [X9]; TI: re-adaptacija resetom CDR-a [X11]).
4. **Dvije stvari iz izvora izravno pogađaju naš slučaj (IZVEDENO):**
   - Xilinx izrijekom piše da DFE auto-adaptacija na 8b10b podacima koji nisu skremblirani „odluta” od ispravne točke
     i da za adaptaciju treba slučajan uzorak, barem PRBS-7 [X1 str. 210]. Naš BER okvir ima K28.5 + ID u svakoj riječi [L4].
   - Za kanale s gubitkom ispod 14 dB Xilinx savjetuje **bez TX emfaze**, uz LPM (bez DFE) [X1 str. 210]. PolarFire za kratki kanal
     (6,5 dB) na 250–5000 Mb/s predlaže CDR način bez DFE i blagi CTLE [X7 str. 13], a TX 300–500 mV bez de-emfaze [X7 str. 5].
     Naš kanal ima 3,0 / 4,8 dB [L1 §1], a radimo s TX_AMP 31 (maksimum), TX FFE ≈ −2,3 dB i DFE uključen. Pragovi na +15
     (rub DAC-a) [L2 §17.2] su potpis prejakog signala. Prvi korak zato nije „više ekvalizacije”, nego **manje**.
5. **Preporuka za nas (§6):** G1 zdravlje → G2 uzorak za adaptaciju → G3 TX amplituda na **obje** strane dok pragovi ne siđu s ruba →
   G4 TX preset tablica → G5 CTLE → G6 DFE tap (statički ili zamrznut) → G7 offset (vertikalna kada pa zaključavanje ili ponovno
   učitavanje dok kod nije dobar) → G8 CDR → G9 prihvat po ≥ 5 učitavanja. Svaki korak ima registre, mjerilo i prag.

---

## 1. Naš problem u jednoj tablici (iz naših podataka)

| Činjenica | Vrijednost | Izvor |
|---|---|---|
| Rasipanje među učitavanjima, isti bit | ≥ ×3·10⁴ (gs→m2 2,9·10⁻⁷ … 0); m2→gs ×340 u 10 učitavanja | [L2 §16, §14.5] |
| Unutar jednog učitavanja | BER stabilan (60 s intervali unutar ×2–4) → **stanje se postavi pri učitavanju** | [L2 §15, §16] |
| Jedino stanje koje prati BER | gs `RX_OFFSET` (ρ = −0,74, ali može biti i slučajnost); petlja offseta „sjedi na granici koda” 1↔2 | [L2 §14.5, §17.4] |
| Adaptirani pragovi | `TH_MON1/2` = +15 (rub) na 2,5 G na obje ploče → DFE tap = th1 − th2 = 0, petlja nema gradijent | [L2 §17.2, §17.5] |
| Ručni tap | gs `RX_TAPW` +2 → m2→gs ×3–28 bolje (3/3 učitavanja), kontrolni smjer nepromijenjen | [L2 §17.5] |
| Niža m2 TX amplituda | pomaže gs RX (×5–7), ali kvari m2 RX (×30–40) → odbačeno | [L2 §17.5] |
| Eye counteri | ne broje ni s alatima Cologne Chipa ni s Patrickovim bitom | [L2 §17.3, §17.6] |
| Kalibracija terminacije | `RX/TX_CALIB_CAL` 0/0 = dobra razdoblja, 9/7 = loša (korelacija, ne dokaz) | [L2 §16] |
| Kanal | 3,0 dB nazivno / 4,8 dB najgore na 2,5 GHz | [L1 §1] |

---

## 2. Tablica: proizvođač → alat → koraci → kriterij

| Proizvođač / čip | Alat | Koraci i redoslijed | Kriterij | Varijacija po resetu | Izvor |
|---|---|---|---|---|---|
| **AMD/Xilinx** GTX/GTH/GTY | IBERT / In-System IBERT (ISI), Vivado Serial I/O Analyzer, Tcl `create_hw_sio_sweep` / `run_hw_sio_sweep` | 1) PRBS link (PRBS-7 ili viši) 2) sweep TX diff swing × pre/post-cursor × RX (LPM ili DFE, Auto: > 14 dB → DFE) 3) 2D eye scan svake točke 4) najbolja točka natrag u Wizard atribute | **Open area** 2D oka (statističko oko log10 BER), BER | Adaptacijske petlje (offset OS, AGC, KH/KL, DFE) imaju `{HOLD, OVRDEN}`: 00 = adaptira, 10 = zamrzni, x1 = fiksna vrijednost iz atributa; HOLD nakon treninga (T_DLOCK) | [X1 str. 199, 210, 224–225], [X2], [X3], [X15] |
| **Intel/Altera** Arria 10, Stratix 10 | Transceiver Toolkit (System Console): Auto Sweep + EyeQ | Grupirano: {VOD} → {1. pre/post tap} → {2. pre/post tap} → {VGA, EQ/CTLE}; svaka grupa ±3 koraka oko trenutnog najboljeg; ponavljaj dok se ne vidi pad (prekompenzacija) | Visina i širina oka (EyeQ) + BER | *Initial* adaptacija pri paljenju ili kad se kanal promijeni, *continuous* u pozadini; DFE može biti *triggered* ili kontinuiran | [X5], [X6] (str. 6 metode), [X16] |
| **Lattice** CertusPro-NX | Radiant: eye monitor (2D eye scan) po RX kanalu | TX 3-tap FIR (de-emfaza / pre-shoot) → CTLE (`RxA2gain`, mijenja se samo između susjednih kodova) → 1-tap DFE (`RxA1gain`) | BER mapa iz eye monitora | **Bez adaptacije: CTLE na minimum (kod 0, najravniji odziv)**, jer CTLE ovisi o procesu, temperaturi i naponu (PVT) | [X8 str. 88–92, 100] |
| **Lattice** ECP5 / ECP5-5G | Diamond PCS konfiguracija, SERDES Eye Demo | TX amplituda i ±1 tap de-emfaze; RX LEQ | BER (PRBS) | statičke postavke (adaptacija nije opisana) | [X17], [X18] |
| **Microchip** PolarFire | SmartDebug: Debug Transceiver (PRBS, static pattern, Eye Monitor > 3,125 Gb/s), sweep 29 TX postavki | 1) TX amplituda + de-emfaza (preporuke po duljini kanala) 2) RX CTLE (63 postavke; tablica po gubitku i brzini) 3) DFE (5 tapova) „Optimize Receiver” 4) izvoz natrag u Libero | BER, oko poslije CTLE + DFE | Kalibracija: **None (CDR)** / **On-Demand** / **On-Demand + First Lock** / **Static_DFE** (DC offset kalibracija radi, DFE koeficijenti H1–H5 fiksni iz SmartDebuga ili simulacije); inkrementalna rekalibracija za drift V/T | [X7 str. 3–5, 13, 16–20], [X19] |
| **TI** DS280DF810 (retimer) | SigCon Architect (GUI), SMBus registri | CTLE se adaptira **tijekom lock acquisition** po FOM-u iz HEO/VEO; DFE se uključuje ručno (samo tijekom locka ili kontinuirano, ili ručni tapovi uz isključenu adaptaciju); TX 3-tap FIR | FOM = HEO/VEO (unutarnji EOM) | **CTLE se zamrzne nakon locka** dok se ne zatraži re-adaptacija ili dok CDR ne izgubi lock; re-adaptacija = reset CDR-a | [X11 str. 17, 19, 26], [X12] |
| **TI** DS160PR410 (linearni redriver) | ručno, EQ indeks 0–15 | biraj EQ indeks prema gubitku kanala prije redrivera; TX preset se prenosi kroz redriver | otvor oka, uspjeh link-traininga | statički (pinovi/I²C) | [X20] |
| **PCIe Gen3** (standard, svi proizvođači) | LTSSM Recovery.Equalization | Faza 0: DSP pošalje preset; Faza 1: link do **BER < 10⁻⁴**; Faza 2/3: fino podešavanje preseta svake strane | BER < 10⁻¹² nakon faze 3 | **Ponavlja se pri svakom link-upu** (adaptivno, dogovorno) | [X9], [X10] |
| **ADI** (JESD204 / ADRV904x) | `jesd-eye-scan-gtk` (prikaz eye scana s Xilinx GT-a u ADI referentnim dizajnima); AN-2594 SERDES tuning | — | — | **AN-2594 nisam uspjela otvoriti iz kontejnera (timeout)**, pa njen sadržaj ne navodim | [X21], [X22] |

---

## 3. Detalji po proizvođaču (samo ono što nam treba)

### 3.1 Xilinx: LPM ili DFE, i kada smrznuti

- **LPM** je za kratke kanale niske refleksije, s gubitkom ≤ 14 dB na Nyquistu, i za uzorke koji nisu slučajni. Uz to:
  „for low loss channels (less than 14 dB at Nyquist), it is advised to not use any TX emphasis and let the RX adaptation handle all
  the equalization” [X1 str. 210].
- **DFE** je za kanale ≥ 8 dB i za refleksije. Važna je i ova napomena: „the auto adaptation in DFE mode requires incoming data to be
  random … 8B/10B encoded … repeated patterns can cause the auto adapting algorithms to drift away from the ideal equalization setting.
  Patterns with characteristics similar to PRBS7 (or higher polynomials) are sufficiently random” [X1 str. 210].
- Svaka adaptacijska petlja ima par `{HOLD, OVRDEN}`, uključujući **offset cancelation loop** (`RXOSHOLD`, `RXOSOVRDEN`): 2'b00 adaptira,
  2'b10 zamrzne trenutnu vrijednost, 2'bx1 je fiksna vrijednost iz atributa [X1 str. 199]. To je isti mehanizam kao naš `RX_EN_EQA_EXT_VALUE`.
- Xilinx savjetuje zamrznuti AGC i LF petlje nakon treninga (T_DLOCK ≈ 1,02·10⁸ bitova) [X15, sažetak advisoryja 47128; stranica
  se iz kontejnera ne učitava].
- **Eye scan:** drugi uzorkivač s horizontalnim i vertikalnim pomakom broji neslaganja s podatkovnim uzorkom, pa je BER(x, y) = greške / uzorci.
  Radi na živim podacima bez promjene RX postavki [X1 str. 225]. Taj isti mehanizam CC_SERDES ima (`RX_EYE_MEAS_*`), ali kod nas ne broji [L2 §17.3].

### 3.2 Intel: auto sweep po grupama

- Metoda opisana u [X6 §6]: (1) svaki parametar se mete posebno, ostali ostaju na zadanim vrijednostima; (2) iz najboljih vrijednosti
  nastaje matrica S; (3) TX grupa (VOD, pre/post tapovi) i RX grupa (DC gain, EQ, VGA) mete se zasebno u rasponu ±3 oko S;
  (4) ponavlja se dok se ne vidi pad: „The degradation of metrics denotes the over-compensation and it marks the transition from the maxima”.
  Mjerilo je oko (EyeQ visina i širina) + BER, uzorak PRBS-31.
- Adaptacija: *initial* adaptacija „on device power up or when there is change in the physical channel”, *continuous* u pozadini [X5,
  sažetak pretrage; stranice intel.com se iz kontejnera preusmjeravaju na 404, pa citat nisam mogla provjeriti na izvoru].

### 3.3 PolarFire: najbliži našem planu

- Tri razine: tradicionalno (iskustvo, „does not ensure the ideal performance”), IBIS-AMI simulacija, SmartDebug na hardveru [X7 str. 3].
- Za kratke kanale i 250–5000 Mb/s zadano je **CDR način bez DFE**, CTLE „No Peak + 2.8 dB” [X7 tabl. 1-4]; TX 300–500 mV,
  0 dB [X7 tabl. 1-1].
- **`None (Static_DFE)`:** „DC Offset Calibration of the CDR is performed, however, the DFE Coefficients are set through PDC commands …
  These values are gathered by the SmartDebug tool or by simulation” [X7 str. 18]. To je točno naš recept „TAPW +2 fiksno”.

### 3.4 TI retimer: zamrzni nakon locka, re-adaptiraj resetom CDR-a

- „Once the CDR locks and the CTLE adapts, the CTLE boost level is frozen until a manual re-adapt command is issued or until the CDR
  re-enters the lock acquisition state. The CTLE can be re-adapted by resetting the CDR” [X11 str. 17].
- DFE: „when the DFE is configured manually the DFE auto-adaption should be disabled” [X11 str. 19]. Isto vrijedi kod nas (EXT_VALUE).

### 3.5 PCIe Gen3 preseti (za našu TX tablicu)

| Preset | Pre-shoot (dB) | De-emfaza (dB) | c₋₁ | c₊₁ |
|---|---|---|---|---|
| P4 | 0,0 | 0,0 | 0 | 0 |
| P1 | 0,0 | −3,5 | 0 | −0,167 |
| P0 | 0,0 | −6,0 | 0 | −0,250 |
| P9 | 3,5 | 0,0 | −0,166 | 0 |
| P8 | 3,5 | −3,5 | −0,125 | −0,125 |
| P7 | 3,5 | −6,0 | −0,100 | −0,200 |
| P5 | 1,9 | 0,0 | −0,100 | 0 |
| P6 | 2,5 | 0,0 | −0,125 | 0 |
| P3 | 0,0 | −2,5 | 0 | −0,125 |
| P2 | 0,0 | −4,4 | 0 | −0,200 |
| P10 | 0,0 | −9,5 ± 1,5 | — | — |

Izvor: [X10 tabl. 8]. Tolerancija je ±1 dB, osim za P10.

---

## 4. Varijacija po resetu: kako je drugi rješavaju

| Mehanizam | Tko | Kako | Što znači za nas (IZVEDENO) |
|---|---|---|---|
| **Foreground** kalibracija pri resetu, pa zamrzavanje | Xilinx HOLD [X1], TI CTLE freeze [X11], Intel initial [X5] | adaptira se na poznatom ili slučajnom uzorku, zatim HOLD | Kod nas petlja i dalje radi poslije locka (gs `RX_OFFSET` šeta 1↔2 unutar prozora [L2 §17.4]). Zamrzavanje = `RX_EN_EQA=0` + `EXT_VALUE` |
| **Background** (kontinuirana) adaptacija | Intel continuous [X5], TI DFE continuous [X11], Xilinx po zadanom | prati V/T drift | Na granici koda kontinuirana petlja dithera. Za kratki kanal na sobnoj temperaturi koristi joj je mala |
| **Fiksna radna točka** iz sweepa | PolarFire Static_DFE [X7], Xilinx OVRDEN [X1], TI manualni DFE [X11] | DC offset se i dalje kalibrira, EQ koeficijenti su fiksni | Recept „TAPW +2 u bitstreamu” (power-up `RX_EN_EQA=0`, `RX_TAPW`, `EXT_VALUE`) [L2 §17.5] |
| **Ponovi kalibraciju dok mjerilo nije OK** | PCIe faze (prag BER 10⁻⁴, pa fino) [X9]; TI re-adapt = reset CDR-a [X11] | petlja: kalibriraj → izmjeri → ako nije dobro, ponovi | Ako je kod offseta loš, ponovi RX reset ili ponovno učitaj, pa izmjeri kratko (10 s na 2,5 G = 2,5·10¹⁰ bitova, dovoljno za 10⁻⁹) |
| **Uzorak za adaptaciju** | Xilinx: slučajni podaci, ≥ PRBS-7 [X1] | adaptacija na PRBS-u, ne na 8b10b okviru | Probati: adaptacija dok obje TX šalju PRBS-15 (`TX_PRBS_SEL=2`), zamrznuti, zatim prebaciti na BER okvir |
| **Sporija petlja** | Xilinx loop CFG atributi „use the Wizard value” [X1 str. 208] | manji korak = manje ditheringa | CC_SERDES ima `RX_EQA_CKP_OFFSET` (zadano 0x01), `RX_EQA_CKP_LF/HF` (0xA3) [L5][L3 §1.3]. Smjer djelovanja je NEPROVJEREN |

---

## 5. Open-source repozitoriji i alati

| Repozitorij / alat | Što radi | Primjenjivo na GateMate? | Link |
|---|---|---|---|
| **IBERTpy** (mvsoliveira) | generira Vivado Tcl, mete polaritet, PRBS, swing, emfazu; eye scan + eye mask, histogrami horizontalnog, vertikalnog i ukupnog otvora; LaTeX izvještaj | **Ideja da** (struktura sweepa i izvještaja), kod ne (Vivado) | https://github.com/mvsoliveira/IBERTpy |
| **ChipScoPy** (Xilinx, službeni) | Python API za IBERT: eye scan, parametri, sweep | ne (cs_server, Versal/US+) | https://github.com/Xilinx/chipscopy |
| pyIBERT / XilinxTCL.py (UNESP) | Python + Vivado: automatski tuning TXDIFFSWING, TXPRE, TXPOST, RXTERM, DFE po open area | ideja da; repozitorij nije javno naveden | [X4] |
| **jesd-eye-scan-gtk** (ADI) | prikaz eye scana s Xilinx GT-a (JESD204) | ne | https://github.com/analogdevicesinc/jesd-eye-scan-gtk |
| **LiteICLink** (enjoy-digital) | SerDes jezgre za GTP/GTX/GTH/GTY/ECP5, PRBS i loopback CSR-ovi | **Nema workflowa za podešavanje:** `TXDIFFCTRL=0b1000`, `TXPOSTCURSOR`/`TXPRECURSOR=0` su tvrdo zadani (`gtp_7series.py` L808–892 @ `6e69216`); ECP5 TX drajver je fiksan (`serdes_ecp5.py` L932–943); GateMate nije podržan [L6 S11] | https://github.com/enjoy-digital/liteiclink |
| **pu-cc/gm_serdes_lb** (Cologne Chip, Patrick Urban) | `serdestool.py`: regfile, PRBS, eye_freeze / capture / diagnose (eye engine kod nas ne radi) | **da**, jedini alat za CC_SERDES; već je kod nas (`tools/serdestool.py`) | https://github.com/pu-cc/gm_serdes_lb |
| colognechip/gatemate-pipe | PCIe Gen1 PIPE wrapper: TX_AMP 30, bez FFE, DFE isključen | referenca za Gen1 postavke | https://github.com/colognechip/gatemate-pipe |
| LiteX `soc/cores/prbs.py` | fabric PRBS7/15/31 TX/RX | da, za fabric checker | https://github.com/enjoy-digital/litex |

**Nije nađeno:** javni, za sve proizvođače isti „SerDes tuning workflow” izvan PCIe EQ-a. Nema open-source sweep alata za GateMate,
Lattice ni PolarFire. Ni retimer tuning rutina kao kod (TI to radi kroz zatvoreni SigCon Architect [X12]). ADI AN-2594 nije učitan.

---

## 6. Predloženi postupak za GateMate CC_SERDES (2,5 Gb/s)

**Načela iz izvora:** TX prije RX, CDR zadnji [X6][X13]. Kratki kanal znači manje ekvalizacije [X1][X7][X8].
Adaptacija samo na slučajnom uzorku, zatim zamrzavanje ili fiksna točka [X1][X7][X11]. Svaki korak ima prag, a parametar je
„gotov” kad se iza vrha vidi pad [X6].
**Naša pravila (iz [L1 §5]):** sve analogno ide u bitstream (JTAG služi samo za smjer), svaki ishod se procjenjuje po ≥ 3 učitavanja
(medijan i najgore), oba smjera zajedno (zbroj BER), JTAG PEER 200/200 prije i poslije.

| Korak | Što | Registri (CC_SERDES param / regfile) | Raspon | Mjerilo i prag | Napomena |
|---|---|---|---|---|---|
| **G1 Zdravlje** | refclk, PLL, kalibracija terminacije | `PLL_CAP_FT` (0x55), `RX_CALIB_DONE/CAL` 0x02[10:7], `TX_CALIB_CAL` 0x3C[10:7], `TX_CALIB_EN=1` | — | 0,0 ppm; CAP_FT ~500 bez OF/UF; zapiši CALIB_CAL | 9/7 = sumnja na napajanje [L2 §16]; dalje ne idi bez čistog G1 |
| **G2 Uzorak za adaptaciju** | adaptacija na PRBS-u, ne na 8b10b okviru | `TX_PRBS_SEL=2` (PRBS-15) na obje TX → `RX_EN_EQA=1` → čekaj → zamrzni (`RX_EN_EQA=0`, `RX_EN_EQA_EXT_VALUE`) → `TX_PRBS_SEL=0` | A/B: adaptirano na PRBS vs na okviru | rasipanje među ≥ 5 učitavanja (omjer najgore/medijan) | HIPOTEZA iz [X1 str. 210]; jeftin test, bez novog bita (JTAG) |
| **G3 TX amplituda (obje strane zajedno)** | spusti swing dok pragovi ne siđu s ruba | `TX_AMP` (0x30[14:10]), FFE isključen (`TX_SEL_PRE=TX_SEL_POST=0`) | 31 → 24 → 20 → 16 → 12, **simetrično** | `RX_TH_MON` < 15 na obje RX **i** zbroj BER oba smjera | Asimetrično (samo m2) je već odbijeno [L2 §17.5]; simetrično nije probano. PolarFire za kratki kanal: 300–500 mV [X7] |
| **G4 TX FFE kao tablica preseta** | probaj svaki preset, svaka RX strana sudi za suprotnu TX | `TX_BRANCH_EN_PRE/POST` (0x31), `TX_SEL_PRE/POST` (0x30); dB = 20·log((N_BRA−2·(SEL_PRE+SEL_POST))/N_BRA) [L3 §1.1] | Q0 0/0 = 0 dB (≈P4); Q1 BR_POST 31, SEL_POST 6 = −1,2 dB; Q2 SEL_POST 12 = −2,6 dB (≈P3); Q3 SEL_POST 17 = −3,9 dB (≈P1); Q5 BR_PRE 12, SEL_PRE 3 = −0,7 dB pre-shoot; P1 profil 5/5 = −2,3 dB | BER smjera tog RX-a, medijan po 3 učitavanja | Po Xilinxu [X1] i PolarFireu [X7] očekujem da Q0 pobjeđuje na 2,5 G (IZVEDENO) |
| **G5 CTLE** | najmanja ekvalizacija koja ne kvari BER | `RX_AFE_PEAK` (0x09[4:0], **0 = max, 31 = min**), `RX_AFE_GAIN` (0x09[8:5]) ostaje 0 | PEAK 31, 28, 24, 20, 16 | BER + TH_MON s ruba | 2,5 G: 20–31 bilo ravno [L3]; Lattice: bez adaptacije uzmi minimum [X8] |
| **G6 DFE tap** | kada po tapu, zatim fiksno | `RX_EN_EQA`, `RX_TAPW` (0x06), `RX_EN_EQA_EXT_VALUE[2]` (štiti TH_MON1 **i** TAPW); slijed: EXT=0 → piši → EXT zadnje (`eyescan.pin_fields`) | −3 … +4 oko adaptiranog | dno kade; potvrdi na ≥ 3 nova učitavanja | Gotovo za gs (+2) [L2 §17.5]; nakon G3–G5 kada se pomiče, pa izmjeri ponovno. Za m2 nije mjereno. U bitstream: `RX_EN_EQA=0`, `RX_TAPW`, `RX_EN_EQA_EXT_VALUE` (= PolarFire Static_DFE [X7]) |
| **G7 Offset (glavni izvor varijacije)** | vertikalna kada pa odluka | `RX_AFE_OFFSET` (0x06[10:6], 5 b) uz `RX_EN_EQA_EXT_VALUE[3]` (štiti TH_MON2 **i** AFE_OFFSET); očitanje `RX_OFFSET` 0x07[13:10] (predznak + iznos) | adaptirani kod ±3 | BER m2→gs po kodu (60 s) | **Prvo izmjeri preslikavanje** `RX_OFFSET` (predznak + iznos) → `RX_AFE_OFFSET` (bez predznaka, zadano 8). Upstream ga krivo piše [L2 §17.1]. Zatim (a) zaključaj najbolji kod ili (b) „retry”: nakon učitavanja pročitaj `RX_OFFSET`; ako nije u dobrom skupu, napravi RX reset ili ponovno učitaj (TI re-adapt [X11], PCIe prag [X9]). Opcija (c) `RX_EQA_CKP_OFFSET` manji, NEPROVJERENO |
| **G8 CDR** | zadnji | `RX_CDR_CKP` 0x0A[7:0], `RX_CDR_CKI` 0x0A[15:8] = 0 (dijeljeni refclk), `RX_CDR_TRANS_TH` 0x0B[14:8], `RX_CDR_LOCK_CFG` 0xD5 | CKP 0x3E, 0x1E, 0x7E; TRANS_TH 8, 16 | BER + udio sinkroniziranog vremena | 2,5 G: CKP 0x3E / TH 8 je polazna točka [L1 §3] |
| **G9 Prihvat** | potvrda cijelog recepta u bitstreamu | — | ≥ 5 svježih učitavanja × 300 s, isprepleteno A/B | medijan i **najgore** učitavanje; cilj najgore < 10⁻⁹, medijan < 10⁻¹¹ | „Bolje” znači da je bolje i najgore učitavanje, ne samo medijan [L2 §16] |

**Zašto baš ovaj redoslijed za nas (IZVEDENO):** pragovi na +15 su rub DAC-a [L2 §17.2]. Dok je signal prevelik, DFE i offset petlja nemaju
gradijent, pa ishod adaptacije ovisi o početnim uvjetima pri resetu. To je mogući mehanizam za „lutriju po učitavanju”, ali je **HIPOTEZA**.
Zato G3 (manji swing) ide prije G6/G7. Kad pragovi siđu s ruba, adaptirani tap i offset mogli bi sami pasti u dobru točku.
Ako ne padnu, G6/G7 ih zaključavaju.

**Kriterij koraka:** dok eye counteri ne rade, „oko” je BER kada po jednom parametru (kao lab26d). To je Intelova metoda [X6] s BER-om
umjesto EyeQ-a. Za svaku kadu: 60 s po točki, A-korak (adaptirano) između točaka, kao u [L2 §17.5].

---

## 7. Što nije nađeno ili nije provjereno

- Javni workflow za podešavanje **GateMate** SerDesa: ne postoji (ni kod Cologne Chipa: `tc_eyemeas` u upstreamu ne mjeri [L6 S3], [L2 §17]).
- Nisam našla rad o „varijaciji po resetu” baš na FPGA SerDesu, s mjerenjem. Mehanizmi u §4 su iz dokumentacije proizvođača, ne iz studije.
- Intelove stranice (683723 E-tile, PMA Tuning Guidelines, Auto Sweep help) iz kontejnera daju 404/redirect. Tvrdnje [X5] su iz
  sažetka web pretrage s tim URL-ovima, **nisu čitane na izvoru**. Advisory Xilinxa 47128/72808 ima isti problem (stranice se ne renderiraju).
- ADI AN-2594 (ADRV904x SERDES tuning): timeout, sadržaj nepoznat.
- Mapiranje `RX_OFFSET` → `RX_AFE_OFFSET` i učinak `RX_EQA_CKP_OFFSET` na CC_SERDES: nigdje nije dokumentirano (DS1001 / serdestool) [L3].
- Retimer tuning rutine kao open-source kod: nisu nađene. TI to radi u zatvorenom SigCon Architectu [X12].

---

## 8. Izvori

Vanjski (lokalne kopije PDF-ova i tekstovi: `~/app/tmp/zadaci/TASK-5528_kako-se-serdes-umjerava-na/src/`):

- [X1] Xilinx UG578 v1.3, *UltraScale Architecture GTY Transceivers*: str. 199 (tabl. 4-9 HOLD/OVRDEN), 208, 210 (LPM/DFE, 8b10b i adaptacija), 224–225 (eye scan). https://0x04.net/~mwk/xidocs/ug/ug578-ultrascale-gty-transceivers.pdf
- [X2] Xilinx PG246 *In-System IBERT v1.0*: str. 7, 21 (eye scan i sweep testovi). https://www.xilinx.com/support/documents/ip_documentation/in_system_ibert/v1_0/pg246-in-system-ibert.pdf
- [X3] Xilinx PG196 *IBERT for UltraScale GTY* (TX swing, pre/post, RX LPM/DFE, Auto > 14 dB → DFE). https://www.xilinx.com/content/dam/xilinx/support/documents/ip_documentation/ibert_ultrascale_gty/v1_2/pg196-ibert-ultrascale-gty.pdf ; Tcl: UG835 `create_hw_sio_sweep` https://docs.amd.com/r/2025.1-English/ug835-vivado-tcl-commands/get_hw_sio_sweeps
- [X4] Finotti, Cascadan, *Tuning System for Xilinx MGT Transceivers* (INFIERI 2017; Python + Vivado, open area). https://indico.cern.ch/event/566138/contributions/2466179/attachments/1407100/2151955/INFIERI_2017_Autotuning.pdf
- [X5] Intel/Altera: E-tile adaptacija (initial / continuous) https://www.intel.com/content/www/us/en/docs/programmable/683723/current/e-tile-transceiver-phy-overview.html ; statusni kodovi adaptacije https://www.intel.com/content/www/us/en/support/programmable/articles/000077327.html ; Transceiver Toolkit https://www.intel.com/content/www/us/en/docs/programmable/683552/18-1/transceiver-toolkit-commands.html (*nije učitano na izvoru, vidi §7*)
- [X6] Khan i sur., *Optimization of multi-gigabit transceivers for high speed data communication links in HEP Experiments*, arXiv:1901.02722, §6 (TTK auto sweep, grupe, ±3, prekompenzacija). https://arxiv.org/pdf/1901.02722
- [X7] Microchip AN5667 (DS00005667A, 2025) *PolarFire Transceiver Tuning*: str. 3–5, 13, 16–20 (Static_DFE, On-Demand, First Lock). https://ww1.microchip.com/downloads/aemDocuments/documents/FPGA/ApplicationNotes/ApplicationNotes/PolarFire_FPGA_Transceiver_Signal_Integrity_AC483_V1.pdf
- [X8] Lattice FPGA-TN-02245-1.4 *CertusPro-NX SerDes/PCS User Guide*: str. 88–92 (FIR, CTLE, DFE), 100 (eye monitor). https://www.frontgrade.com/sites/default/files/documents/fpga-tn-02245-1_4-certuspro-nx-serdes-pcs-user-guide.pdf
- [X9] TI SNLA415 *PCIe Link Training Overview*, §6 (faze 0–3, BER < 10⁻⁴, < 10⁻¹²). https://www.ti.com/lit/pdf/snla415
- [X10] TI TIDU796 *TIDA-00423 PCIe Gen-3*, tabl. 8 (preseti P0–P10, c₋₁/c₊₁). https://www.ti.com/lit/ug/tidu796/tidu796.pdf
- [X11] TI DS280DF810 datasheet SNLS538B: str. 17 (CTLE FOM, freeze nakon locka), 19 (DFE), 26 (HEO/VEO). https://www.ti.com/lit/ds/symlink/ds280df810.pdf
- [X12] TI SNLU214A *SigCon Architect* (adapt modes u GUI-ju). https://www.ti.com/lit/ug/snlu214a/snlu214a.pdf
- [X13] IBERTpy. https://github.com/mvsoliveira/IBERTpy
- [X14] ChipScoPy. https://github.com/Xilinx/chipscopy
- [X15] AMD advisory 47128 (7-series GTH, HOLD nakon T_DLOCK) https://adaptivesupport.amd.com/s/article/47128 ; 72808 (US+ GTY adaptation loop override) https://adaptivesupport.amd.com/s/article/72808 ; 45148 (CTLE/DFE frozen) https://adaptivesupport.amd.com/s/article/45148 (*stranice se ne renderiraju; navod iz sažetka pretrage*)
- [X16] Intel Transceiver Toolkit (Auto Sweep, EyeQ). https://www.intel.in/content/www/in/en/software/programmable/quartus-prime/transceiver-toolkit.html
- [X17] Lattice FPGA-TN-02206-1.7 *ECP5 and ECP5-5G SerDes/PCS User Guide* (str. 24–25 LEQ, de-emfaza). https://0x04.net/~mwk/doc/lattice/ecp5/FPGA-TN-02206-1-7-ECP5-and-ECP5-5G-SerDes-PCS-User-Guide.pdf
- [X18] Lattice *SERDES Eye Demo for ECP5 Versa*. https://www.latticesemi.com/-/media/LatticeSemi/Documents/UserManuals/RZ/SERDESEyeDemoECP5VersaDevKitUG93.ashx?document_id=50998
- [X19] Microchip UG0773 *PolarFire SmartDebug* (Debug Transceiver, Eye Monitor > 3,125 Gb/s). https://coredocs.s3.amazonaws.com/Libero/pf_2_3_0/Tool/pf_smartdebug_ug.pdf
- [X20] TI SNLA337A *How to Tune DS160PR410 for Best Signal Integrity*. https://www.ti.com/lit/an/snla337a/snla337a.pdf
- [X21] ADI jesd-eye-scan-gtk. https://github.com/analogdevicesinc/jesd-eye-scan-gtk ; ADI wiki https://wiki.analog.com/resources/tools-software/linux-software/jesd_eye_scan
- [X22] ADI AN-2594 *ADRV904x SERDES Tuning*. https://www.analog.com/en/resources/app-notes/an-2594.html (*nije učitano*)
- LiteICLink @ `6e69216` (2026-10-08): `liteiclink/serdes/gtp_7series.py` L808–892, `serdes_ecp5.py` L932–943. https://github.com/enjoy-digital/liteiclink

Naši dokumenti (u ovom repozitoriju):

- [L1] `docs/SERDES_KNOWLEDGE.md` (stanje 28.09., §1 kanal, §3 profili, §5 zamke)
- [L2] `docs/VERIFY_20260926_RATES.md` §14.5, §15, §16, §17
- [L3] `docs/TUNING_5G.md` §1.1 (TX formule), §1.3–1.4 (RX, CDR registri)
- [L4] `gateware/ber/ber_link.v` (okvir: K28.5 + ID + 40-bitni PRBS payload)
- [L5] yosys `share/yosys/gatemate/cells_bb.v` L58–76 (oss-cad-suite 2026-09-23): `RX_EQA_CKP_*`, `RX_EN_EQA_EXT_VALUE`, `RX_TAPW`, `RX_AFE_OFFSET`
- [L6] `docs/SOURCES_20260926.md` (S3 gm_serdes_lb, S11 LiteICLink)
- `tools/upstream_cc_20261015/serdestool.py` L349–362 (polja EXT_VALUE, AFE_OFFSET, RX_OFFSET), L1354 `eye_freeze`
