"""Classify a CC_SERDES RX_DATA[79:0] read (8b10b on: 8 slots x 10 bit, LSB first, bit8 = K flag).

serdes_lb.v (serdes_dut) transmits K28.5 (0x1BC) + 7x D10.2 (0x04A). With the P/N polarity of
the GS<->M2 lane swapped (measured 26.09.2026) the receiver sees D21.5 (0xB5) = ~0x4A."""

K28_5 = 0x1BC
D10_2 = 0x04A          # serdes_lb.v payload byte
D21_5 = 0x0B5          # D10.2 received with inverted polarity


def slots(rx80, n=8, width=10):
    return [(rx80 >> (width * i)) & ((1 << width) - 1) for i in range(n)]


def classify(rx80):
    if rx80 == 0:
        return 'ZERO'
    if rx80 == (1 << 80) - 1:
        return 'IDLE_FF'
    s = slots(rx80)
    if s.count(K28_5) == 1:
        if s.count(D10_2) == 7:
            return 'DATA_OK'
        if s.count(D21_5) == 7:
            return 'DATA_INVERTED'
    return 'OTHER'
