#!/usr/bin/env python3
"""READ-ONLY CC_SERDES status over JTAG for ONE board (the bitstream owns the config).

    fpga-jtag gs run python3 serdes_status.py [--samples 20] [--json]
    fpga-jtag m2 run python3 serdes_status.py [--samples 20] [--json]

Only IR 0x25 with wren=0/mask=0 (address select) + IR 0x26 (read) are issued: no field is
written, no PLL/TRX reset. Replaces gs_rx_readonly.py / gs_rx_char.py / check_status.py."""
import argparse
import json
import time

from loopback import loopback_line
from serdes_jtag import Serdes, STATUS_FIELDS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--samples', type=int, default=20, help='polls of CDR/ALIGN/RST (default 20)')
    ap.add_argument('--period', type=float, default=0.25)
    ap.add_argument('--rx80', type=int, default=4, help='RX_DATA[79:0] snapshots (default 4)')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()

    sd = Serdes()
    out = {'board': sd.board, 'busdev': sd.busdev, 'idcode': '0x%08X' % sd.idcode(),
           'reg_0x5C': '0x%04X' % sd.word(0x5C), 'fields': {}, 'polls': {}, 'rx80': []}
    out['loopback'] = sd.loopback()
    for n in STATUS_FIELDS:
        try:
            out['fields'][n] = sd.field(n)
        except Exception as e:                     # keep going, report the failing field
            out['fields'][n] = 'ERR %r' % e
    cnt = {'RX_CDR_LOCKED': 0, 'RX_BYTE_IS_ALIGNED': 0, 'RX_RESET_DONE': 0, 'TX_RESET_DONE': 0}
    for _ in range(a.samples):
        for k in cnt:
            cnt[k] += sd.field(k)
        time.sleep(a.period)
    out['polls'] = {k: '%d/%d' % (v, a.samples) for k, v in cnt.items()}
    for _ in range(a.rx80):
        out['rx80'].append('0x%020X' % sd.rx80())
        time.sleep(0.2)
    sd.close()

    if a.json:
        print(json.dumps(out, indent=1))
        return
    print('board=%s busdev=%s idcode=%s reg0x5C=%s  (READ-ONLY)' % (
        out['board'], out['busdev'], out['idcode'], out['reg_0x5C']))
    print('  ' + loopback_line(out['loopback']))
    for n, v in out['fields'].items():
        print('  %-20s = %s' % (n, v))
    print('  polls: ' + '  '.join('%s %s' % kv for kv in out['polls'].items()))
    for r in out['rx80']:
        print('  rx80=%s' % r)


if __name__ == '__main__':
    main()
