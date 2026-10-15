#!/usr/bin/env python3
"""TASK-5524: pictures of the M2 -> GS SerDes path (M2 TX -> C143/C144 -> J10 ... GS J1 -> GS RX) on both boards.
    python3 render_m2_gs_path.py <out_dir>
Inputs: M2 as built = FAST-TRACK-SIM copy (= panel gerbers 02.06.2026, SI_SERDES_GS_v004.md section 1.2),
        GS v005 = ~/app/ulx5m-gs-hw hardware/ulx5m-gs.kicad_pcb (61b6709)."""
import os, sys, json
from PIL import Image, ImageDraw, ImageFont
from path_render import Board, render, FONT, FONTB, COL

M2_PCB = os.path.expanduser('~/app/raid/FAST-TRACK-SIM/boards/ulx5m-m2/ulx5m-m2.kicad_pcb')
GS_PCB = os.path.expanduser('~/app/ulx5m-gs-hw/hardware/ulx5m-gs.kicad_pcb')
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', '..', 'docs', 'data_20260927', 't5086')
M2_TX = {'P': ['/M.2 M Key/PCIe_TX_P', '/M.2 M Key/PET0P'], 'N': ['/M.2 M Key/PCIe_TX_N', '/M.2 M Key/PET0N']}
GS_RX = {'P': ['/cm4-hsio/PCIe_RX_P'], 'N': ['/cm4-hsio/PCIe_RX_N']}
Y = (255, 255, 120); G = COL['hl']; W_ = (230, 230, 230); R = COL['FP']; O = COL['FN']; B = COL['BP']
M2_VER = 'M2 = AS BUILT (FAST-TRACK-SIM 02.06.2026 = panel gerberi, AC kapovi 0201) - NE GitHub f29c5aa (tamo 0402)'


def seg_len(js, label, net):
    return json.load(open(os.path.join(DATA, js)))[label]['nets'][net]


def lengths():
    m = lambda l, n: seg_len('m2_built.json', l, n); g = lambda l, n: seg_len('gs_v005.json', l, n)
    t = {}
    t['m2_tx'] = [m('TX(U4->C143/4)', '/M.2 M Key/PCIe_TX_' + s) for s in 'PN']
    t['m2_pet'] = [m('PET0(C->J10)', '/M.2 M Key/PET0' + s) for s in 'PN']
    t['gs_rx'] = [g('RX(J1->U4)', '/cm4-hsio/PCIe_RX_' + s) for s in 'PN']
    t['gs_txbc'] = [g('TX_BC(U4->C134/5)', '/serdes/PCIe_TX_BC_' + s) for s in 'PN']
    t['gs_tx'] = [g('TX(C->J1)', '/cm4-hsio/PCIe_TX_' + s) for s in 'PN']
    t['m2_rx'] = [m('RX(J10->U4)', '/M.2 M Key/PCIe_RX_' + s) for s in 'PN']
    return t


def main(out):
    os.makedirs(out, exist_ok=True)
    m2 = Board(M2_PCB); gs = Board(GS_PCB)
    for ref in ('C143', 'C144'):
        assert m2.fps[ref]['lib'].endswith('C_0201_0603Metric') and m2.fps[ref]['value'] == '220nF', ref
    L = lengths()
    files = []
    # 1) M2 overview
    files.append(render(m2, M2_TX, ['C143', 'C144', 'R110'], (151.5, 93.5, 177.5, 145.0),
        os.path.join(out, '1_m2_tx_cijeli_put.png'), ppm=40, panel_w=1040,
        title='M2: TX put U4 -> C144/C143 -> J10 (smjer M2->GS)',
        labels=[
            (164.48, 96.86, 'U4.U13 = TX_P\n(164.48, 96.86)', -330, -10, R),
            (165.28, 96.86, 'U4.V13 = TX_N\n(165.28, 96.86)', -330, 90, O),
            (167.74, 96.46, 'R110 DNP 0402\npločice NA vodu', -150, -95, G),
            (171.79, 99.34, 'via 1 P (171.79, 99.34)\nvia 1 N (172.34, 99.54)\nF.Cu -> B.Cu', -330, 190, Y),
            (165.0, 120.0, 'B.Cu ~50 mm\nP 50,8 / N 49,8 mm\nw 0,147 / razmak 0,253', 120, -30, B),
            (157.0, 138.31, 'via 2 P (157.00, 138.31)\nvia 2 N (157.70, 138.31)\nB.Cu -> F.Cu', -10, -190, Y),
            (157.31, 139.38, 'C144 (P) + C143 (N)\n220 nF 0201', 140, -40, G),
            (157.3, 142.93, 'J10.43 = PET0P (M.2 PERp0)\nJ10.41 = PET0N (M.2 PERn0)\nM.2 zlatni prsti', 120, 10, W_),
        ],
        notes=[M2_VER,
               'Datoteka: ~/app/raid/FAST-TRACK-SIM/boards/ulx5m-m2/ulx5m-m2.kicad_pcb  (koordinate u mm, KiCad)',
               'TX_P: F.Cu %.2f + B.Cu %.2f mm (2 vie) -> C144 -> F.Cu %.2f -> J10.43 = %.2f mm' % (
                   L['m2_tx'][0]['by_layer']['F.Cu'], L['m2_tx'][0]['by_layer']['B.Cu'], L['m2_pet'][0]['total'],
                   L['m2_tx'][0]['total'] + L['m2_pet'][0]['total']),
               'TX_N: F.Cu %.2f + B.Cu %.2f mm (2 vie) -> C143 -> F.Cu %.2f -> J10.41 = %.2f mm' % (
                   L['m2_tx'][1]['by_layer']['F.Cu'], L['m2_tx'][1]['by_layer']['B.Cu'], L['m2_pet'][1]['total'],
                   L['m2_tx'][1]['total'] + L['m2_pet'][1]['total']),
               'Polaritet na M2 ispravan: TX_P ide na p-pin (43), TX_N na n-pin (41) M.2 standarda.',
               'Plavo = B.Cu (donja strana): ~50 mm voda je s DONJE strane ploče, vidljivo samo odozdo.'],
        notes_font=21))
    # 2) M2 zoom on the AC caps and J10
    files.append(render(m2, M2_TX, ['C143', 'C144'], (154.2, 136.9, 160.2, 143.9),
        os.path.join(out, '2_m2_ac_kapovi_C143_C144.png'), ppm=170, panel_w=1040,
        title='M2: AC kondenzatori C144 (P) / C143 (N) uz J10',
        labels=[
            (156.93, 139.38, 'C144 = TX_P\n220 nF 0201\n(156.93, 139.38)', -330, -170, G),
            (157.69, 139.38, 'C143 = TX_N\n220 nF 0201\n(157.69, 139.38)', 170, -170, G),
            (157.0, 138.31, 'via 2 P', -250, -40, Y),
            (157.70, 138.31, 'via 2 N', 160, -40, Y),
            (157.05, 142.93, 'J10.43 PERp0', -330, -60, R),
            (157.55, 142.93, 'J10.41 PERn0', 120, -60, O),
            (156.05, 142.93, 'J10.47/49 = M2 RX\n(drugi smjer)', -300, -150, W_),
        ],
        notes=[M2_VER,
               'Pločice 0201: 0,46 x 0,40 mm, razmak centara 0,64 mm (procjep 0,18 mm); razmak C144-C143 0,76 mm.',
               'Ispod pločica pune GND1 (In1) bez izreza -> pločica ~43 ohm (SI_SERDES_GS_v004 par. 3).',
               'U datoteci: C143/C144 NISU DNP, Value=220nF, MPN polje PRAZNO. Na stolu provjeri lupom jesu li zalemljeni.',
               'Nema drugih kondenzatora na ovom vodu na M2: jedan C po žici, uz odašiljač (PCIe konvencija).',
               'Vrijednost 220 nF je u PCIe prozoru (Gen1/2 75-265 nF, Gen3 176-265 nF) -> OK, ne treba mijenjati.',
               '0402 umjesto 0201: ručno stane (kontakti 0402 na 0,25..0,50 mm od centra padaju na pločice 0,09..0,55; '
               'tijela 0,5 mm na razmaku 0,76 -> 0,26 mm zraka), ALI veće tijelo = veći kapacitivni skok; SI razloga nema. '
               'Mijenjati samo ako kap fali/oštećen ili vrijednost upitna (npr. GS-ov GRM155R60J104KA01D 100 nF, LCSC C1525).'],
        notes_font=21, legend=False))
    # 3) M2 BGA breakout
    files.append(render(m2, M2_TX, ['R110'], (161.5, 93.8, 174.5, 102.6),
        os.path.join(out, '3_m2_bga_izlaz_U4.png'), ppm=80, panel_w=1040,
        title='M2: izlaz TX iz U4 (BGA) i prijelaz na B.Cu',
        labels=[
            (164.48, 96.86, 'U4.U13 TX_P', -300, -60, R),
            (165.28, 96.86, 'U4.V13 TX_N', -200, 120, O),
            (167.74, 96.46, 'R110 DNP 0402\n(prazne pločice\npreko para)', 60, -120, G),
            (171.79, 99.34, 'via 1 P', 40, 80, Y),
            (172.34, 99.54, 'via 1 N', 80, -60, Y),
        ],
        notes=[M2_VER,
               'F.Cu ~10 mm od BGA do via 1, zatim B.Cu ~50 mm. Vod je na suženju 0,13 mm uz BGA.',
               'R110 (DNP) - dvije prazne 0402 pločice izravno na TX paru (mali kapacitivni skok, SI doc G3).'],
        notes_font=21, legend=False))
    # 4) GS RX
    files.append(render(gs, GS_RX, ['R107', 'C134', 'C135'], (80.8, 82.6, 93.2, 97.4),
        os.path.join(out, '4_gs_rx_J1_U4.png'), ppm=80, panel_w=1040,
        title='GS v005: RX put J1.16/18 -> U4.U11/V11 (smjer M2->GS)',
        labels=[
            (91.21, 95.835, 'J1.16 = PCIe_RX_P (CM 116)\n(91.21, 95.84) B.Cu', -60, 60, R),
            (90.81, 95.835, 'J1.18 = RX_N (CM 118)', -420, 80, O),
            (85.41, 94.105, 'via P (85.41, 94.11)\nvia N (85.41, 94.70)\nB.Cu -> F.Cu', -380, -160, Y),
            (84.97, 94.36, 'R107 DNP 0402\npločice NA RX vodu', -380, 0, G),
            (90.26, 84.18, 'U4.U11 = RX_P\n(90.26, 84.18)', -420, -40, R),
            (90.26, 84.98, 'U4.V11 = RX_N', 120, 40, O),
            (85.0, 91.0, 'C134/C135 100 nF 0402\n= GS TX (drugi smjer)', -420, -40, W_),
        ],
        notes=['GS v005 (na stolu): ~/app/ulx5m-gs-hw/hardware/ulx5m-gs.kicad_pcb @ 61b6709 (= v05 gerberi)',
               'RX_P: B.Cu %.2f + F.Cu %.2f = %.2f mm, 1 via;  RX_N: B.Cu %.2f + F.Cu %.2f = %.2f mm, 1 via' % (
                   L['gs_rx'][0]['by_layer']['B.Cu'], L['gs_rx'][0]['by_layer']['F.Cu'], L['gs_rx'][0]['total'],
                   L['gs_rx'][1]['by_layer']['B.Cu'], L['gs_rx'][1]['by_layer']['F.Cu'], L['gs_rx'][1]['total']),
               'NEMA AC kondenzatora na GS RX (ispravno: kondenzator je na M2 TX). Na vodu samo R107 DNP pločice.',
               'Polaritet na GS ispravan: J1.16 = CM5 pin 116 PCIe_RX_P -> U4.U11 RX_P.',
               'Pogled odozgo. J1 je s donje strane (B.Cu), kratko B.Cu ~7 mm, via kod R107, pa F.Cu ~20 mm (meandri) do BGA.'],
        notes_font=21))
    files.append(chain(os.path.join(out, '5_lanac_M2_GS_pin_po_pin.png'), L))
    return files


def chain(out, L):
    """Pin-by-pin chain + per-segment lengths, both directions."""
    Wd, Hd = 1080, 2300
    img = Image.new('RGB', (Wd, Hd), COL['bg']); d = ImageDraw.Draw(img)
    fT = ImageFont.truetype(FONTB, 30); f = ImageFont.truetype(FONT, 22); fb = ImageFont.truetype(FONTB, 22)
    fs = ImageFont.truetype(FONT, 19)
    d.text((20, 14), 'Lanac M2 -> GS (lošiji smjer), pin po pin', fill=COL['txt'], font=fT)
    blocks = [
        ('M2 PCB (as built)', 'U4.U13/V13 -> F.Cu %.1f -> 2 vie -> B.Cu %.1f/%.1f mm\n-> C144/C143 220 nF 0201 -> F.Cu 3,3 -> J10.43 (P) / J10.41 (N)'
         % (L['m2_tx'][0]['by_layer']['F.Cu'], L['m2_tx'][0]['by_layer']['B.Cu'], L['m2_tx'][1]['by_layer']['B.Cu']),
         'PROVJERENO (kicad_pcb)', (60, 140, 60)),
        ('M.2 utor adaptera', 'J10.43/41 = M.2 PERp0/PERn0 (= RX hosta)\n-> FFC pin 7/8 (PCIE_RX_P/N po RPi standardu)',
         'NEPROVJERENO - adapter nije identificiran', (150, 60, 40)),
        ('FFC 16-pin 0,5 mm', 'pin 7/8 RX par, GND 6 i 9 oko njega;\nRPi spec: <= 50 mm, 90 ohm, kontakti na suprotnim stranama',
         'NEPROVJERENO - duljina i tip kabela', (150, 60, 40)),
        ('Waveshare CM5-IO-BASE-A', 'P1.7 PCIE_RX_P / P1.8 PCIE_RX_N -> CM5 pin 116 / 118\nbez serijskih kondenzatora na RX',
         'PROVJERENO shema (CM5-IO-BASE-A_Sch.pdf); duljina nepoznata', (120, 110, 40)),
        ('GS v005', 'J1.16/18 -> B.Cu %.1f/%.1f -> 1 via -> F.Cu %.1f/%.1f -> U4.U11/V11\nbez AC kondenzatora, R107 DNP pločice na vodu'
         % (L['gs_rx'][0]['by_layer']['B.Cu'], L['gs_rx'][1]['by_layer']['B.Cu'], L['gs_rx'][0]['by_layer']['F.Cu'], L['gs_rx'][1]['by_layer']['F.Cu']),
         'PROVJERENO (kicad_pcb)', (60, 140, 60)),
    ]
    y = 70
    for i, (h, body, tag, c) in enumerate(blocks):
        d.rounded_rectangle([20, y, Wd-20, y+150], 12, outline=c, width=4)
        d.text((36, y+10), h, fill=COL['txt'], font=fb)
        d.multiline_text((36, y+44), body, fill=COL['txt'], font=f, spacing=6)
        d.text((36, y+116), tag, fill=c if c != (60, 140, 60) else (120, 255, 120), font=fs)
        y += 150
        if i < len(blocks)-1:
            d.polygon([(Wd/2-14, y+4), (Wd/2+14, y+4), (Wd/2, y+26)], fill=COL['txt']); y += 30
    y += 20
    p_m2 = L['m2_tx'][0]['total'] + L['m2_pet'][0]['total']; n_m2 = L['m2_tx'][1]['total'] + L['m2_pet'][1]['total']
    p_gs, n_gs = L['gs_rx'][0]['total'], L['gs_rx'][1]['total']
    p_gt = L['gs_txbc'][0]['total'] + L['gs_tx'][0]['total']; n_gt = L['gs_txbc'][1]['total'] + L['gs_tx'][1]['total']
    p_mr, n_mr = L['m2_rx'][0]['total'], L['m2_rx'][1]['total']
    rows = [('Duljine po segmentu (mm, P / N)', '', ''),
            ('M2->GS: M2 U4 -> J10 (s C144/C143 0,64)', '%.2f / %.2f' % (p_m2 + .64, n_m2 + .64), '2 vie'),
            ('M2->GS: adapter + FFC + baseboard', '? / ?', 'izmjeriti'),
            ('M2->GS: GS J1 -> U4', '%.2f / %.2f' % (p_gs, n_gs), '1 via'),
            ('M2->GS ukupno na pločama', '%.2f / %.2f' % (p_m2 + .64 + p_gs, n_m2 + .64 + n_gs), 'skew %.2f' % abs((p_m2 + p_gs) - (n_m2 + n_gs))),
            ('GS->M2: GS U4 -> J1 (s C134/C135 0,96)', '%.2f / %.2f' % (p_gt + .96, n_gt + .96), '1 via'),
            ('GS->M2: M2 J10 -> U4', '%.2f / %.2f' % (p_mr, n_mr), '2 vie'),
            ('GS->M2 ukupno na pločama', '%.2f / %.2f' % (p_gt + .96 + p_mr, n_gt + .96 + n_mr), 'skew %.2f' % abs((p_gt + p_mr) - (n_gt + n_mr)))]
    for i, (a, b_, c_) in enumerate(rows):
        fnt = fb if i == 0 or 'ukupno' in a else f
        d.text((30, y), a, fill=COL['txt'], font=fnt); d.text((640, y), b_, fill=COL['txt'], font=fnt); d.text((900, y), c_, fill=COL['txt'], font=fnt)
        y += 34
    y += 14
    notes = ['SUMNJIVO / ZA PROVJERU:',
             '1) P/N zamjena u OBA smjera (RX_POLARITY_I=1 na obje ploče): GS, Waveshare P1 i M2',
             '   ispravni po shemi/PCB-u -> zamjena je u adapteru. Trag: službena RPi CM5 IO ploča',
             '   (KiCad, PCIe-M2 list) NAMJERNO križa P/N oba para na M.2 (TX_P->pin 47 n, RX_P<-41 n);',
             '   adapter rađen po RPi M.2 uzoru radi isto. Bezopasno (PCIe dopušta), osim ako križa vijama.',
             '2) Kondenzatori u seriji: na pločama točno 1 po smjeru. Ima li ADAPTER svoje kapove?',
             '   2 u seriji (220 nF + x) radi, ali dodaje 2 pločice-skoka. Pogledati adapter.',
             '3) Nepoznata duljina adaptera/FFC-a: RPi spec FFC <= 50 mm. Dulji kabel = više gubitka.',
             '4) GND povrat preko FFC-a: pinovi 3, 6, 9, 12 - provjeriti kontinuitet GND M2 <-> GS.',
             'PREPORUKA KONDENZATORA:',
             'PCIe Gen1/2 (2,5/5 Gb/s): 75-265 nF, tipično 100 nF; Gen3: 176-265 nF (220 nF).',
             'M2 220 nF 0201 = OK (i za Gen3). GS 100 nF 0402 = OK za Gen1/2. Ne mijenjati zbog SI.',
             'SI poboljšanje (sljedeća revizija, SI doc G2): izrez GND1 ispod pločica kapova, 0201.',
             'IZMJERITI (Goran): duljinu FFC-a, model adaptera (foto obje strane), kapove na adapteru,',
             'C143/C144 lupom (zalemljeni?); DMM bez napajanja: J10 prst 43 <-> C144 pad 1 = 0 ohm,',
             'preko C144 = otvoreno (isto prst 41 / C143).']
    for t in notes:
        d.text((30, y), t, fill=(255, 220, 120) if t.endswith(':') and t.isupper() else COL['txt'], font=f); y += 31
    img = img.crop((0, 0, Wd, min(Hd, y + 20)))
    img.save(out)
    return out


if __name__ == '__main__':
    for p in main(sys.argv[1] if len(sys.argv) > 1 else 'out'):
        print(p, Image.open(p).size)
