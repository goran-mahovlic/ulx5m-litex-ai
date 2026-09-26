"""Decode the 'B …' status line printed by ber_top.v on gs (UART by-id if01, 115200 8N1).
FIELDS must equal gw/gen_report_fmt.py (test tests/test_ber_parse.py checks it)."""
FIELDS = [
    ('t25', 32), ('tcnt', 32), ('rcnt', 32), ('flg', 8), ('words', 48), ('errw', 32), ('errb', 32),
    ('code', 32), ('inj', 8), ('exec', 8), ('cmd', 8), ('cfg', 8),
    ('pwords', 48), ('perrw', 32), ('perrb', 32), ('pcode', 32), ('pflg', 8), ('pexec', 8),
    ('pcmd', 8), ('pinj', 8), ('pver', 8), ('pcfg', 8), ('pframes', 32),
]
PAYLOAD_BITS = 40          # checked bits per word (bytes 2..6)
LINE_BITS = 80             # line bits per word (8 x 10b)
F_CLK25 = 25_000_000


def parse(line):
    t = line.strip().split()
    if len(t) != len(FIELDS) + 1 or t[0] != 'B':
        return None
    d = {}
    for (n, bits), v in zip(FIELDS, t[1:]):
        if len(v) != bits // 4:
            return None
        d[n] = int(v, 16)
    for p in ('', 'p'):
        f = d[p + 'flg']
        d[p + 'synced'] = f >> 7 & 1
        d[p + 'self_seen'] = f >> 6 & 1
        d[p + 'loss'] = f & 0x1F
    c = d['cfg']
    d['loopback_sel'] = c >> 5
    d['rx_pol'] = c >> 4 & 1
    d['outdiv'] = {0: 1, 1: 2, 3: 4}.get(c >> 2 & 3, '?')
    return d


def rate(a, b, key):
    """Line rate in bit/s from two parsed lines: word clock count delta over clk25 delta, x80."""
    dt = (b['t25'] - a['t25']) & 0xFFFFFFFF
    dn = (b[key] - a[key]) & 0xFFFFFFFF
    return dn * F_CLK25 / dt * LINE_BITS if dt else 0.0


def ber(errb, words):
    """(measured BER, 95 % upper bound). With 0 errors the bound is 3/bits (rule of three)."""
    bits = words * PAYLOAD_BITS
    if bits == 0:
        return None, None
    return errb / bits, (3.0 / bits if errb == 0 else None)
