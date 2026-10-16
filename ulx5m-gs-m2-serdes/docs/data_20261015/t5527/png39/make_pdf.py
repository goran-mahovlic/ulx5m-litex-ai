#!/usr/bin/env python3
"""TASK-5527: PDF sažetak dokaza lab39 (uputa #339). Brojke iz proof_table.md / VERIFY §18.11."""
import sys
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

pdfmetrics.registerFont(TTFont('DV', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('DVB', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
H1 = ParagraphStyle('h1', fontName='DVB', fontSize=14, leading=18, spaceAfter=4)
H2 = ParagraphStyle('h2', fontName='DVB', fontSize=11, leading=14, spaceBefore=8, spaceAfter=3)
B = ParagraphStyle('b', fontName='DV', fontSize=8.8, leading=11.5)
S = ParagraphStyle('s', fontName='DV', fontSize=7.5, leading=9.5)
D = sys.argv[1]
out = sys.argv[2]


def tab(rows, widths, hdr=True):
    t = Table([[Paragraph(str(c), S) for c in r] for r in rows], colWidths=widths)
    st = [('GRID', (0, 0), (-1, -1), 0.3, colors.grey), ('VALIGN', (0, 0), (-1, -1), 'TOP')]
    if hdr:
        st.append(('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8eef7')))
    t.setStyle(TableStyle(st))
    return t


# (B) tablica iz proof_table.md
rows = []
for ln in open(D + '/png39/proof_table.md'):
    if ln.startswith('| t') or ln.startswith('| soak'):
        rows.append([c.strip() for c in ln.strip().strip('|').split('|')])
rez = {'first': 'prihvaćen 1. put', 'G2': 'prihvaćen nakon G2', 'rejected': 'odbijen'}
rows = [r[:2] + [r[3]] + r[4:8] + [rez.get(r[8], r[8])] for r in rows]

el = [Paragraph('ULX5M GS↔M2 SerDes 2,5 G — dokaz dugotrajnog linka (lab39, 15./16.10.2026.)', H1),
      Paragraph('TASK-5527 · uputa #339 (Goran 15.10. 23:59) · Jelena · podaci: ulx5m-litex-ai/ulx5m-gs-m2-serdes/docs/'
                'data_20261015/t5527/ (lab39.out, log39/), VERIFY_20260926_RATES.md §18.10–18.11', S),
      Paragraph('Zaključak', H2),
      Paragraph('<b>Link se diže na svakom učitavanju i drži bez ijednog restarta, ali nije bez grešaka.</b> '
                '21/21 svježih učitavanja: link gore (JTAG PEER 200/200 oba smjera) za 40,8–51,3 s. Prihvaćeno učitavanje '
                '(&lt; 1e-9 oba smjera u 60 s) radilo je 4,79 h: 0 restarta brojača, 0 gubitaka sinkronizacije, BER '
                '<b>M2→GS 8,3·10⁻¹⁰, GS→M2 4,2·10⁻¹⁰</b>, bez drifta većeg od ×2 između sati. To je otprilike jedna bitna '
                'greška u sekundi u M2→GS, pa za link s 10⁻¹² treba ~×800 manje grešaka ili FEC/CRC s ponavljanjem.', B),
      Spacer(1, 3),
      Paragraph('<b>Nema fiksnog recepta.</b> Prag od 1e-9 u prvih 60 s prolazi tek 7/21 učitavanja (33 %), a s pravilom G2 '
                '10/21 (48 %). Pokus t1 nije uspio ni u 3 učitavanja. Lošiji smjer je M2→GS na 12/14 neuspjelih učitavanja. '
                'Što je učitavanje dobro, odlučuje samo učitavanje: ni startni offset ni G2 to ne predviđaju pouzdano '
                '(G2 je M2→GS popravio na 7, a pokvario na 7 od 14). Dakle, vrata + ponovno učitavanje su postupak, '
                'nisu popravak. Uzrok raspršenja još je otvoren (eye engine ne radi, §18.6).', B),
      Paragraph('Postav', H2),
      tab([['Stavka', 'Vrijednost'],
           ['Bitovi (nepromijenjeni)', 'm2_2g5.bit sha256 b1b98a5d946169d1…af4e · gs_2g5.bit sha256 36f09752d8b85ebd…e344'],
           ['Učitavanje', 'lab22: fpga-jtag m2 … -r, pa gs … -r; RX_CDR_SET_ACC 2→0; bez power-cyclea'],
           ['Recept', 'TX_AMP 12 na oba TX (G3, lab38); prihvat: oba smjera < 1e-9 u 60 s; inače G2 (PRBS-15 5 s + zamrzavanje RX) '
                      'i ponovno 60 s; inače novo učitavanje (najviše 3 po pokusu)'],
           ['Mjera', 'serijski BER (lab/ber_long.py), oba smjera istodobno, snimka svakih 60 s; svakih 15 min lock/TH_MON/OFFSET/TAPW '
                     'obje ploče + temperatura Pija'],
           ['Stanje', 'nakon Goranova popravka C143/C144 (15.10. 18:49); Pi 53,7–58,5 °C, throttled 0xd0000 (0xd0005 na 3/19 '
                      'očitanja)']], [38 * mm, 140 * mm]),
      Paragraph('(A) Soak — jedno učitavanje (soak_l2), 03:10–07:58, 278 × 60 s', H2),
      tab([['Smjer', 'bitova', 'grešaka', 'BER', '95 % interval', '60 s bez grešaka', 'restarti'],
           ['M2→GS', '2,16·10¹³', '17 844', '8,3·10⁻¹⁰', '8,15–8,39·10⁻¹⁰', '0 / 278', '0'],
           ['GS→M2', '2,16·10¹³', '8 953', '4,2·10⁻¹⁰', '4,06–4,24·10⁻¹⁰', '19 / 278', '0']],
          [18 * mm, 22 * mm, 18 * mm, 20 * mm, 32 * mm, 28 * mm, 18 * mm]),
      Spacer(1, 3),
      Paragraph('Po satu M2→GS: 6,4 / 5,9 / 10 / 7,3 / 13 ·10⁻¹⁰ (zadnji sat traje 0,79 h); GS→M2: 4,9 / 1,6 / 1,5 / 5,3 / 8,4 ·10⁻¹⁰. '
                'Najgora minuta 1,1·10⁻⁸ / 9,9·10⁻⁹. Oba RX su cijelo vrijeme imala CDR i EQA zaključane, TH_MON gs 12–13 / m2 14 '
                '(nije na +15). Jedno očitanje (04:57) dalo je m2 RX_CDR_LOCKED=0, ali bez traga u BER-u te minute i bez restarta.', B),
      Paragraph('Usporedba', H2),
      tab([['Mjerenje', 'M2→GS', 'GS→M2'],
           ['Jutro 15.10. 2,5 G, zadano (TASK-5522/5523, medijan 300 s)', '4,1·10⁻⁹', '3,6·10⁻¹⁰'],
           ['lab27 gs TAPW +2 (TASK-5525)', '4,7·10⁻⁹ / 1,1·10⁻⁸', '—'],
           ['<b>lab39 soak 4,79 h (TX_AMP 12 + prag + ponovno učitavanje)</b>', '<b>8,3·10⁻¹⁰</b>', '<b>4,2·10⁻¹⁰</b>']],
          [110 * mm, 34 * mm, 34 * mm]),
      Spacer(1, 4),
      Image(D + '/png39/proof.png', width=180 * mm, height=180 * mm * 520 / 1540),
      Paragraph('(B) Ponovljivost — svako svježe učitavanje (60 s po koraku)', H2),
      tab([['Učitavanje', 't_link s', 'offset gs / m2', 'M2→GS A', 'GS→M2 A', 'M2→GS G2', 'GS→M2 G2', 'ishod']] + rows,
          [20 * mm, 14 * mm, 20 * mm, 22 * mm, 22 * mm, 22 * mm, 22 * mm, 34 * mm]),
      Paragraph('Što nije dokazano', H2),
      Paragraph('• Link bez grešaka (BER ≤ 10⁻¹²): nije, M2→GS ima grešaka u svakoj minuti. • Fiksni recept: nije, prolazi tek '
                'svako drugo učitavanje. • Soak je skraćen na 4,79 h (kraj u 07:58, uputa #340), a ne 8 h. • 5 G nije bio dio '
                'lab39. • Jedan par ploča, jedna temperatura; nema mjerenja oka (eye engine ne radi).', B)]
SimpleDocTemplate(out, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
                  title='ULX5M SerDes 2,5 G dokaz lab39', author='Goran Mahovlic').build(el)
print(out)
