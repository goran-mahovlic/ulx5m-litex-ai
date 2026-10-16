#!/usr/bin/env python3
"""serdes_cmp.py <a.bit> <b.bit> [--names A B] [--md out.md] — CC_SERDES configuration of two GateMate bitstreams.

Reads the raw CMD_SERDES block (cmd 0xD7, 186 bytes, header and data CRC-16/X-25 checked) straight from each .bit,
so it works on gmpack output that gmunpack cannot parse (TASK-5054) and on p_r output alike. The block is decoded with
the prjpeppercorn SerdesBitDatabase field table (add_word_settings in TileBitDatabase.cpp; bit i = byte i//8, bit
i%8). Bits outside the table are reported as UNKNOWN_<bit>. The raw bytes are compared too, so nothing is hidden by
the table. Fields set explicitly in gateware/ber/cc_serdes_params.vh are marked "explicit".
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB_CPP = os.environ.get('PEPPERCORN_DB', '/home/klaudio/app/raid/tools/nextpnr-a2fix/prjpeppercorn/libgm/src/TileBitDatabase.cpp')
PARAMS_VH = os.path.join(HERE, '..', '..', 'gateware', 'ber', 'cc_serdes_params.vh')
CMD_SERDES, SERDES_LEN = 0xD7, 186


def crc16(data, crc=0xFFFF):
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return crc ^ 0xFFFF


def serdes_blocks(bit):
    """All CMD_SERDES data blocks whose header and data CRC check (A1 = one block, A2 = one per die)."""
    out, i = [], 0
    while True:
        i = bit.find(bytes([CMD_SERDES, SERDES_LEN]), i)
        if i < 0 or i + 4 + SERDES_LEN + 2 > len(bit):
            return out
        hdr, h = bit[i:i + 2], bit[i + 2:i + 4]
        data = bit[i + 4:i + 4 + SERDES_LEN]; d = bit[i + 4 + SERDES_LEN:i + 6 + SERDES_LEN]
        if crc16(hdr) == int.from_bytes(h, 'little') and crc16(hdr + h + data) == int.from_bytes(d, 'little'):
            out.append(data); i += 6 + SERDES_LEN
        else:
            i += 1


def field_db(path=DB_CPP):
    src = open(path).read()
    body = src[src.index('SerdesBitDatabase::SerdesBitDatabase'):]
    body = body[:body.index('\n}')]
    return {n: ((int(w, 16) << 4) + int(b), int(l))
            for n, w, b, l in re.findall(r'add_word_settings\("(\w+)",\s*\(0x([0-9a-fA-F]+)\s*<<\s*4\)\s*\+\s*(\d+),\s*(\d+)\)', body)}


def decode(block, db):
    bits = [(block[i // 8] >> (i % 8)) & 1 for i in range(len(block) * 8)]
    vals = {n: sum(bits[s + k] << k for k in range(l)) for n, (s, l) in db.items()}
    known = {s + k for s, l in db.values() for k in range(l)}
    return vals, [i for i, v in enumerate(bits) if v and i not in known]


def txt_serdes(path):
    """.serdes section of a gmpack .txt (nextpnr output / gmunpack output; gmunpack omits zero fields)."""
    vals, on = {}, False
    for line in open(path):
        if line.startswith('.'):
            on = line.startswith('.serdes')
            continue
        p = line.split()
        if on and len(p) == 2:
            vals[p[0]] = int(p[1], 2)
    return vals


def explicit_fields(path=PARAMS_VH, db=None):
    """Fields set in cc_serdes_params.vh; a .vh word split into _0.._n bits in the table (RX_EN_EQA_EXT_VALUE) counts."""
    names = set(re.findall(r'^\s*\.([A-Z0-9_]+)\s*\(', open(path).read(), re.M))
    return names | {f for f in (db or ()) if re.sub(r'_\d+$', '', f) in names}


def diff(a, b):
    return [(k, a.get(k, 0), b.get(k, 0)) for k in sorted(set(a) | set(b)) if a.get(k, 0) != b.get(k, 0)]


def group(name):
    for g in ('CALIB', 'EQA', 'CDR', 'RTERM', 'TERM', 'PLL', 'AFE', 'DFE'):
        if g in name:
            return g
    return name.split('_')[0]


def main(argv):
    names = ['A', 'B']; md = None; files = []
    it = iter(argv)
    for a in it:
        if a == '--names': names = [next(it), next(it)]
        elif a == '--md': md = next(it)
        else: files.append(a)
    db = field_db(); exp = explicit_fields(db=db)
    dec = []
    for f in files:
        blk = serdes_blocks(open(f, 'rb').read())
        if len(blk) != 1:
            sys.exit(f'{f}: {len(blk)} CMD_SERDES blocks (expected 1, CCGM1A1)')
        v, unk = decode(blk[0], db)
        dec.append((blk[0], v, unk))
    (ra, va, ua), (rb, vb, ub) = dec
    d = diff(va, vb)
    nbytes = sum(x != y for x, y in zip(ra, rb))
    lines = [f'# CC_SERDES {names[0]} vs {names[1]}', '',
             f'- {names[0]}: `{files[0]}`', f'- {names[1]}: `{files[1]}`',
             f'- raw CMD_SERDES block: {SERDES_LEN} B, differing bytes: **{nbytes}**',
             f'- fields in table: {len(db)}, explicit in cc_serdes_params.vh: {len(exp & set(db))}, '
             f'differing fields: **{len(d)}**, unknown bits set: {names[0]} {ua or 0}, {names[1]} {ub or 0}', '']
    if d:
        lines += [f'| field | group | explicit | {names[0]} | {names[1]} |', '|---|---|---|---|---|']
        lines += [f'| {k} | {group(k)} | {"yes" if k in exp else "no"} | {x} | {y} |' for k, x, y in d]
    lines += ['', '<details><summary>all fields</summary>', '',
              f'| field | group | explicit | {names[0]} | {names[1]} |', '|---|---|---|---|---|']
    lines += [f'| {k} | {group(k)} | {"yes" if k in exp else "no"} | {va[k]} | {vb[k]} |' for k in sorted(db)]
    lines += ['', '</details>', '']
    text = '\n'.join(lines)
    if md:
        open(md, 'w').write(text)
    print('\n'.join(lines[:7]))
    for k, x, y in d:
        print(f'  DIFF {k} ({group(k)}, {"explicit" if k in exp else "implicit"}): {x} -> {y}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
