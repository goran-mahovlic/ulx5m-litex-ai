#!/usr/bin/env python3
"""gs UART side of ber_top.v: read 1/s status lines, send commands, measure BER and line rate.

    python3 ber_mon.py watch [--secs 10]          raw decoded lines
    python3 ber_mon.py cmd z|Z|e|E                z clear gs, Z clear gs+m2, e inject 1 error on gs TX,
                                                  E m2 injects 1 error on its TX
    python3 ber_mon.py run --secs 300 [--clear] [--json]   BER run (both directions) + line rates
    python3 ber_mon.py inject e|E [--n 3]         negative control: send N injections, check the
                                                  far checker counted exactly N more error words
    python3 ber_mon.py state [--secs 3]           one-line state, used by verify_external_link.sh:
        prints 'GS=<UP|DOWN> M2=<UP|DOWN|UNKNOWN> ...'  (UP = synced, words moving, no new errors)
The port is the DirtyJTAG if01 by-id path of gs (never /dev/ttyACMn)."""
import argparse
import json
import sys
import time

import serial

from ber_parse import parse, rate, ber

import os
# gs console = DirtyJTAG interface 01, by-id path (never /dev/ttyACMn). Override with SERDES_GS_UART.
PORT = os.environ.get('SERDES_GS_UART', '/dev/serial/by-id/usb-Jean_THOMAS_DirtyJTAG_E660583883501E2C-if01')


def lines(ser, n, timeout=None):
    out, t0 = [], time.time()
    timeout = timeout or n * 1.5 + 3
    buf = b''
    while len(out) < n and time.time() - t0 < timeout:
        buf += ser.read(512)
        while b'\n' in buf:
            l, buf = buf.split(b'\n', 1)
            d = parse(l.decode('ascii', 'replace'))
            if d:
                d['_t'] = time.time()
                out.append(d)
    return out


def open_port():
    s = serial.Serial(PORT, 115200, timeout=0.2)
    s.reset_input_buffer()
    lines(s, 1)                     # drop a possibly half-buffered line (ttyACM keeps old data)
    return s


def send(ser, c):
    ser.write(c.encode()); ser.flush()


def pair_rates(L, key):
    """Median rate over consecutive lines (1 s apart): immune to the 32-bit wrap of t25 (171.8 s)
    and of the word counters, which a first/last difference is not."""
    v = sorted(rate(x, y, key) for x, y in zip(L, L[1:]))
    return v[len(v) // 2] if v else 0.0


def summary(a, b, L=None):
    """Differences between two parsed lines (L = all lines between them, for rate and duration)."""
    L = L or [a, b]
    r = {
        'secs': round(sum(((y['t25'] - x['t25']) & 0xFFFFFFFF) for x, y in zip(L, L[1:])) / 25e6, 2),
        'gs_tx_rate_bps': pair_rates(L, 'tcnt'), 'm2_tx_rate_bps': pair_rates(L, 'rcnt'),
        'loopback_sel_gs_design': b['loopback_sel'], 'rx_pol': b['rx_pol'], 'outdiv': b['outdiv'],
        'm2_to_gs': {'synced': b['synced'], 'self_seen': b['self_seen'], 'loss': b['loss'],
                     'words': b['words'], 'errw': b['errw'], 'errb': b['errb'], 'code_err': b['code'],
                     'new_words': (b['words'] - a['words']) & ((1 << 48) - 1),
                     'new_errb': (b['errb'] - a['errb']) & 0xFFFFFFFF},
        'gs_to_m2': {'synced': b['psynced'], 'self_seen': b['pself_seen'], 'loss': b['ploss'],
                     'words': b['pwords'], 'errw': b['perrw'], 'errb': b['perrb'], 'code_err': b['pcode'],
                     'new_words': (b['pwords'] - a['pwords']) & ((1 << 48) - 1),
                     'new_errb': (b['perrb'] - a['perrb']) & 0xFFFFFFFF,
                     'fresh': b['pframes'] != a['pframes'], 'loopback_sel_m2_design': b['pcfg'] >> 5},
        'gs_inj': b['inj'], 'm2_inj': b['pinj'],
    }
    for k in ('m2_to_gs', 'gs_to_m2'):
        m, ub = ber(r[k]['errb'], r[k]['words'])
        r[k]['ber'], r[k]['ber_95_upper'] = m, ub
    return r


def fmt(r):
    def side(n, s):
        b = ('BER=%.3g' % s['ber']) if s['ber'] else 'BER=0'
        if s['ber_95_upper']:
            b += ' (<%.2g @95%%)' % s['ber_95_upper']
        return '%s synced=%d self=%d loss=%d words=%d errw=%d errb=%d code=%d %s' % (
            n, s['synced'], s['self_seen'], s['loss'], s['words'], s['errw'], s['errb'], s['code_err'], b)
    return ('t=%.1fs  rate gs_tx=%.2f Mb/s m2_tx=%.2f Mb/s  OUTDIV=%s RX_POL=%d LOOPBACK_SEL gs=%d m2=%d\n  %s\n  %s%s'
            % (r['secs'], r['gs_tx_rate_bps'] / 1e6, r['m2_tx_rate_bps'] / 1e6, r['outdiv'], r['rx_pol'],
               r['loopback_sel_gs_design'], r['gs_to_m2']['loopback_sel_m2_design'],
               side('m2->gs', r['m2_to_gs']), side('gs->m2', r['gs_to_m2']),
               '' if r['gs_to_m2']['fresh'] else '  [m2 status STALE: no back-channel frames]'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=('watch', 'cmd', 'run', 'state', 'inject'))
    ap.add_argument('arg', nargs='?')
    ap.add_argument('--secs', type=int, default=None)
    ap.add_argument('--clear', action='store_true')
    ap.add_argument('--n', type=int, default=3)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    s = open_port()
    if a.mode == 'cmd':
        send(s, a.arg); time.sleep(0.2); print('sent %r' % a.arg); return 0
    if a.mode == 'inject':
        key = {'e': 'perrw', 'E': 'errw'}[a.arg]          # e: gs TX -> m2 counts; E: m2 TX -> gs counts
        b0 = lines(s, 1)[0]
        for _ in range(a.n):
            send(s, a.arg); time.sleep(0.3)
        b1 = lines(s, 3)[-1]
        got = (b1[key] - b0[key]) & 0xFFFFFFFF
        who = 'gs TX -> m2 checker' if a.arg == 'e' else 'm2 TX -> gs checker'
        print('INJECT %s: sent=%d counted=%d -> %s' % (who, a.n, got, 'PASS' if got == a.n else 'FAIL'))
        return 0 if got == a.n else 1
    if a.mode == 'watch':
        for d in lines(s, a.secs or 10):
            print({k: d[k] for k in ('synced', 'words', 'errw', 'errb', 'code', 'psynced', 'pwords', 'perrw', 'perrb', 'pframes', 'inj', 'pinj', 'exec', 'pexec')})
        return 0
    if a.mode == 'run':
        if a.clear:
            send(s, 'Z'); lines(s, 3)
        L = lines(s, 1); t0 = time.time()
        while time.time() - t0 < (a.secs or 60):
            n = lines(s, 1)
            if n:
                L.append(n[0])
        r = summary(L[0], L[-1], L)
        r['lines'] = len(L)
        print(json.dumps(r, indent=1) if a.json else fmt(r))
        ok = all(r[k]['synced'] and r[k]['errb'] == 0 and r[k]['new_words'] > 0 for k in ('m2_to_gs', 'gs_to_m2'))
        return 0 if ok else 1
    if a.mode == 'state':
        L = lines(s, a.secs or 3)
        if len(L) < 2:
            print('GS=NOUART M2=UNKNOWN (no status lines from gs: is ber_top loaded on gs?)'); return 2
        r = summary(L[0], L[-1], L)
        g, m = r['m2_to_gs'], r['gs_to_m2']
        gs_up = g['synced'] and g['new_words'] > 0 and g['new_errb'] == 0 and not g['self_seen']
        if not m['fresh']:
            m2s = 'UNKNOWN'
        else:
            m2s = 'UP' if (m['synced'] and m['new_words'] > 0 and m['new_errb'] == 0 and not m['self_seen']) else 'DOWN'
        print('GS=%s M2=%s  gs_rx: synced=%d new_words=%d new_errb=%d self=%d | m2_rx: synced=%d new_words=%d new_errb=%d fresh=%d'
              % ('UP' if gs_up else 'DOWN', m2s, g['synced'], g['new_words'], g['new_errb'], g['self_seen'],
                 m['synced'], m['new_words'], m['new_errb'], m['fresh']))
        return 0


if __name__ == '__main__':
    sys.exit(main())
