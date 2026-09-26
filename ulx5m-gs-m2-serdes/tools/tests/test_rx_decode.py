"""Decode of CC_SERDES RX_DATA[79:0] (8b10b on: 8 slots x 10 bit, bit8 = K flag).
Vectors are real reads from 26.09.2026 (serdes_dut_CFGRST.bit on gs and m2)."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from rx_decode import slots, classify

POL1 = 0x1284A129BC1284A1284A     # RX_POLARITY=1: exactly what serdes_lb.v sends (K28.5 + D10.2 0x4A)
POL0 = 0x2D4B52D5BC2D4B52D4B5     # RX_POLARITY=0: K28.5 + 0xB5 = bitwise-inverted D10.2 (D21.5)
IDLE = 0xFFFFFFFFFFFFFFFFFFFF     # far TX in electrical idle


class Decode(unittest.TestCase):
    def test_slots_lsb_first(self):
        self.assertEqual(slots(0x1284A1284A1284A128BC), [0xBC] + [0x4A] * 7)

    def test_pol1_is_the_sent_pattern(self):
        s = slots(POL1)
        self.assertEqual(s.count(0x1BC), 1)
        self.assertEqual(s.count(0x04A), 7)
        self.assertEqual(classify(POL1), 'DATA_OK')

    def test_pol0_is_inverted_pattern(self):
        self.assertEqual(classify(POL0), 'DATA_INVERTED')

    def test_idle_and_zero(self):
        self.assertEqual(classify(IDLE), 'IDLE_FF')
        self.assertEqual(classify(0), 'ZERO')

    def test_garbage(self):
        self.assertEqual(classify(0x2A4CB034433C03E21478), 'OTHER')


if __name__ == '__main__':
    unittest.main()
