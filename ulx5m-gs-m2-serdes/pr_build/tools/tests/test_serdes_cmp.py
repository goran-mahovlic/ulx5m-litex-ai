"""serdes_cmp.py: raw CMD_SERDES block from a GateMate .bit, decoded with the prjpeppercorn SerDes field table."""
import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import serdes_cmp as sc

BER = os.path.join(HERE, '..', '..', '..', 'gateware', 'ber', 'build')
NP_GS = os.path.join(BER, 'gs_2g5p1_txneg_amp12_s7')


class Crc(unittest.TestCase):
    def test_x25_check_value(self):
        self.assertEqual(sc.crc16(b'123456789'), 0x906E)   # CRC-16/X-25 check value

    def test_block_found_only_with_valid_crc(self):
        data = bytes(range(186))
        hdr = bytes([0xD7, 186]); h = sc.crc16(hdr).to_bytes(2, 'little')
        d = sc.crc16(hdr + h + data).to_bytes(2, 'little')
        good = b'\x00' * 7 + hdr + h + data + d
        self.assertEqual(sc.serdes_blocks(good), [data])
        bad = good[:-1] + bytes([good[-1] ^ 1])
        self.assertEqual(sc.serdes_blocks(bad), [])


class Decode(unittest.TestCase):
    def test_field_table(self):
        db = sc.field_db()
        self.assertEqual(db['RX_BUF_RESET_TIME'], (0, 5))
        self.assertEqual(db['SERDES_ENABLE'], ((0x5c << 4), 1))

    @unittest.skipUnless(os.path.exists(NP_GS + '.bit'), 'nextpnr gs bit not built')
    def test_nextpnr_bit_matches_its_txt(self):
        db = sc.field_db()
        blocks = sc.serdes_blocks(open(NP_GS + '.bit', 'rb').read())
        self.assertEqual(len(blocks), 1)
        vals, unknown = sc.decode(blocks[0], db)
        self.assertEqual(vals['TX_AMP'], 12)
        txt = sc.txt_serdes(NP_GS + '.txt')
        self.assertEqual(len(txt), 215)   # REVIEW_INIT_20261016 §3: 215 fields
        self.assertEqual({k: vals[k] for k in txt}, txt)   # every .txt field equals the decoded bit
        self.assertEqual(unknown, [])

    def test_split_vh_word_counts_as_explicit(self):
        exp = sc.explicit_fields(db=sc.field_db())
        self.assertIn('RX_EN_EQA_EXT_VALUE_3', exp)
        self.assertIn('TX_AMP', exp)
        self.assertNotIn('RX_CALIB_DONE', exp)

    def test_diff(self):
        self.assertEqual(sc.diff({'A': 1, 'B': 2}, {'A': 1, 'B': 3}), [('B', 2, 3)])


if __name__ == '__main__':
    unittest.main()
