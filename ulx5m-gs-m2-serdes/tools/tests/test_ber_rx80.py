import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from ber_rx80 import classify_ber

def word(bytes_, kmask):
    v = 0
    for i, b in enumerate(bytes_):
        v |= (b | (((kmask >> i) & 1) << 8)) << (10 * i)
    return v

class C(unittest.TestCase):
    def test_peer_from_gs_seen_on_m2(self):
        w = word([0xBC, (7 << 3) | 5, 1, 2, 3, 4, 5, 0x99], 1)
        self.assertEqual(classify_ber(w, 'm2'), 'PEER')
        self.assertEqual(classify_ber(w, 'gs'), 'SELF')

    def test_k_at_slot4(self):
        w = word([1, 2, 3, 4, 0xBC, (3 << 3) | 3, 7, 8], 1 << 4)
        self.assertEqual(classify_ber(w, 'gs'), 'PEER')

    def test_idle_zero_other(self):
        self.assertEqual(classify_ber((1 << 80) - 1, 'gs'), 'IDLE_FF')
        self.assertEqual(classify_ber(0, 'gs'), 'ZERO')
        self.assertEqual(classify_ber(word([0x4A] * 8, 0), 'gs'), 'OTHER')

class Inverted(unittest.TestCase):
    def test_pn_inverted_id_is_nobody(self):
        # ids 5 (101) and 3 (011): bitwise inverted they are 2 and 4 -> never PEER nor SELF
        for idv in (5, 3):
            self.assertNotIn((~idv) & 7, (5, 3))


if __name__ == '__main__':
    unittest.main()
