"""Loopback bits of CC_SERDES from regfile words 0x2A (RX) and 0x40 (TX).
Bit positions from serdestool.py regmap (RX_PMA_LOOPBACK 0x2A[0], RX_PCS_LOOPBACK 0x2A[1],
RX_LOOPBACK_OVR 0x2A[8], TX_PMA_LOOPBACK 0x40[1:0], TX_PCS_LOOPBACK 0x40[2], TX_LOOPBACK_OVR 0x40[10])."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from loopback import decode_loopback, loopback_line


class Loopback(unittest.TestCase):
    def test_all_zero_is_normal(self):
        d = decode_loopback(0x000C, 0x0018)          # only DATAPATH_SEL=3 set
        self.assertEqual(d['LOOPBACK_SEL'], 0)
        self.assertFalse(d['any_loopback'])
        self.assertEqual(d['RX_PMA_LOOPBACK'], 0)
        self.assertEqual(d['TX_PMA_LOOPBACK'], 0)

    def test_rx_pma_bit(self):
        d = decode_loopback(0x0001, 0)
        self.assertEqual(d['RX_PMA_LOOPBACK'], 1)
        self.assertTrue(d['any_loopback'])

    def test_tx_fields_and_ovr(self):
        d = decode_loopback(0x0100, 0x0406)          # RX_OVR, TX_PMA=2, TX_PCS=1, TX_OVR
        self.assertEqual(d['RX_LOOPBACK_OVR'], 1)
        self.assertEqual(d['TX_LOOPBACK_OVR'], 1)
        self.assertEqual(d['TX_PMA_LOOPBACK'], 2)
        self.assertEqual(d['TX_PCS_LOOPBACK'], 1)
        self.assertTrue(d['any_loopback'])

    def test_line_says_zero(self):
        self.assertIn('LOOPBACK_SEL=0', loopback_line(decode_loopback(0x000C, 0x0018)))
        self.assertIn('LOOPBACK_SEL=', loopback_line(decode_loopback(0x0001, 0)))
        self.assertNotIn('LOOPBACK_SEL=0 ', loopback_line(decode_loopback(0x0001, 0)) + ' ')


if __name__ == '__main__':
    unittest.main()
