"""Classify a CC_SERDES RX_DATA[79:0] JTAG read for the ber_top.v design (pure, testable).
Word: slot k = K28.5, slot k+1 = {slot[4:0], id[2:0]}; id 5 = gs, 3 = m2 (not complements: a P/N-inverted id matches neither)."""
from rx_decode import slots, K28_5

BOARD_ID = {'gs': 5, 'm2': 3}


def classify_ber(rx80, me):
    """-> 'PEER' (data from the other board), 'SELF' (own id: loop), 'IDLE_FF', 'ZERO', 'OTHER'."""
    if rx80 == 0:
        return 'ZERO'
    if rx80 == (1 << 80) - 1:
        return 'IDLE_FF'
    s = slots(rx80)
    for k in range(7):
        if s[k] == K28_5 and not (s[k + 1] >> 8) & 1:
            idv = s[k + 1] & 7
            if idv == BOARD_ID[me]:
                return 'SELF'
            if idv == BOARD_ID['m2' if me == 'gs' else 'gs']:
                return 'PEER'
    return 'OTHER'
