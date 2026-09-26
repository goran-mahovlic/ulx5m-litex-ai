"""Loopback state of CC_SERDES decoded from regfile words 0x2A (RX) and 0x40 (TX).

LOOPBACK_I (the fabric port, 3 bit: 001 near PCS, 010 near PMA, 100 far PMA, 110 far PCS, DS1001
p.62) is not a regfile field. The regfile holds per-block bits plus *_LOOPBACK_OVR; per DS1001 the
0x2A RX_PMA/RX_PCS_LOOPBACK bits are the FAR-end loopbacks and 0x40 TX_PMA_LOOPBACK (01 = from TX
driver)/TX_PCS_LOOPBACK the NEAR-end ones.
MEASURED 26.09.2026 (VERIFY_20260926.md §1): with OVR=0 the fields do NOT mirror the fabric port
(RX_POLARITY reads 0 with RX_POLARITY_I=1 in the bitstream; a LOOPBACK_I=010 bitstream reads 0).
With OVR=1 (regfile override) they do read back. So LOOPBACK_SEL=0 here proves "no regfile loopback
override" only; that no loop is active is proven by content (ber_top ids) and the idle/cable tests.

LOOPBACK_SEL printed by the tools is a composite of all loopback bits:
    bit0 RX_PMA_LOOPBACK, bit1 RX_PCS_LOOPBACK, bits2-3 TX_PMA_LOOPBACK, bit4 TX_PCS_LOOPBACK
It is 0 only when every loopback bit is 0."""

LOOPBACK_WORDS = (0x2A, 0x40)


def _bits(w, hi, lo):
    return (w >> lo) & ((1 << (hi - lo + 1)) - 1)


def decode_loopback(w2a, w40):
    d = {
        'RX_PMA_LOOPBACK': _bits(w2a, 0, 0),
        'RX_PCS_LOOPBACK': _bits(w2a, 1, 1),
        'RX_LOOPBACK_OVR': _bits(w2a, 8, 8),
        'TX_PMA_LOOPBACK': _bits(w40, 1, 0),
        'TX_PCS_LOOPBACK': _bits(w40, 2, 2),
        'TX_LOOPBACK_OVR': _bits(w40, 10, 10),
    }
    d['LOOPBACK_SEL'] = (d['RX_PMA_LOOPBACK'] | d['RX_PCS_LOOPBACK'] << 1
                         | d['TX_PMA_LOOPBACK'] << 2 | d['TX_PCS_LOOPBACK'] << 4)
    d['any_loopback'] = d['LOOPBACK_SEL'] != 0
    d['reg_0x2A'] = '0x%04X' % w2a
    d['reg_0x40'] = '0x%04X' % w40
    return d


def loopback_line(d):
    return ('LOOPBACK_SEL=%d (far:RX_PMA=%d RX_PCS=%d near:TX_PMA=%d TX_PCS=%d RX_OVR=%d TX_OVR=%d; 0x2A=%s 0x40=%s)%s'
            % (d['LOOPBACK_SEL'], d['RX_PMA_LOOPBACK'], d['RX_PCS_LOOPBACK'], d['TX_PMA_LOOPBACK'],
               d['TX_PCS_LOOPBACK'], d['RX_LOOPBACK_OVR'], d['TX_LOOPBACK_OVR'], d['reg_0x2A'],
               d['reg_0x40'], '  !! LOOPBACK ACTIVE' if d['any_loopback'] else ''))
