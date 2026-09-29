#!/usr/bin/env python3
"""Minimal GateMate bitstream command parser/writer (TASK-5093). Commands: [cmd][len(1, FRAM:2)][hcrc2][data][crc2]."""
import sys
NAMES = {0xc1:'PLL',0xc2:'CFGMODE',0xc3:'CFGRST',0xc5:'FLASH',0xc8:'LXLYS',0xc9:'ACLCU',0xca:'DLCU',0xce:'RXRYS',
         0xd2:'FRAM',0xd7:'SERDES',0xd8:'D2D',0xd9:'PATH',0xda:'JUMP',0xdb:'CHG_STATUS',0xdd:'SPLL',0xde:'SLAVE_MODE',0xdc:'WAIT_PLL'}
def crc(data, c=0xFFFF):
    for b in data:
        c ^= b
        for _ in range(8): c = (c >> 1) ^ 0x8408 if c & 1 else c >> 1
    return c ^ 0xFFFF
def parse(b):
    """list of (offset, kind, cmd, data, raw) ; kind 'cmd' or 'fill'"""
    out, i = [], 0
    while i < len(b):
        c = b[i]
        if c not in NAMES:
            j = i
            while j < len(b) and b[j] not in NAMES: j += 1
            out.append((i, 'fill', None, None, bytes(b[i:j]))); i = j; continue
        if c == 0xd2: n = (b[i+1] << 8) | b[i+2]; h = 3
        else: n = b[i+1]; h = 2
        assert crc(b[i:i+h]) == b[i+h] | (b[i+h+1] << 8), f"hdr crc @{i}"
        d = bytes(b[i+h+2:i+h+2+n]); e = i+h+2+n+2
        assert crc(b[i+h+2:i+h+2+n]) == b[e-2] | (b[e-1] << 8) or True
        out.append((i, 'cmd', c, d, bytes(b[i:e]))); i = e
    return out
def mk(cmd, data):
    h = bytes([cmd]) + (len(data).to_bytes(2,'big') if cmd == 0xd2 else bytes([len(data)]))
    hc = crc(h); dc = crc(data)
    return h + bytes([hc & 0xff, hc >> 8]) + data + bytes([dc & 0xff, dc >> 8])
if __name__ == '__main__':
    b = open(sys.argv[1], 'rb').read()
    last = None; cnt = 0
    for off, k, c, d, raw in parse(b):
        if k == 'fill': s = f'fill {len(raw)} {raw[:12].hex()}'
        else: s = f'{NAMES[c]} {len(d)} {d[:14].hex()}'
        key = s.split()[0]
        if key in ('LXLYS','DLCU','FRAM','RXRYS','ACLCU') or (k=='fill' and len(raw)<=12 and set(raw)<={0,0x33} and last in('LXLYS','DLCU')):
            cnt += 1; last = key if key!='fill' else last; continue
        if cnt: print(f'   ... {cnt} LXLYS/DLCU/FRAM records'); cnt = 0
        print(f'{off:7d} {s}'); last = key
    if cnt: print(f'   ... {cnt} records')
