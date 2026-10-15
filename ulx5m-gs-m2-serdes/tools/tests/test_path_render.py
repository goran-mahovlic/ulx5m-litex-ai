"""TASK-5524: path_render.py (PIL PCB path renderer) and the facts the M2->GS pictures state."""
import math, os, sys, json, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'si'))
import path_render as pr

M2 = os.path.expanduser('~/app/raid/FAST-TRACK-SIM/boards/ulx5m-m2/ulx5m-m2.kicad_pcb')
GS = os.path.expanduser('~/app/ulx5m-gs-hw/hardware/ulx5m-gs.kicad_pcb')


class Geometry(unittest.TestCase):
    def test_arc_quarter_circle_length(self):
        pts = pr.arc_points((1, 0), (math.sqrt(.5), math.sqrt(.5)), (0, 1), n=64)
        ln = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
        self.assertAlmostEqual(ln, math.pi / 2, places=3)

    def test_pad_poly_rotated_90(self):
        poly = pr.pad_poly(dict(w=2.0, h=1.0, rot=90, c=(0, 0)))
        xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
        self.assertAlmostEqual(max(xs) - min(xs), 1.0); self.assertAlmostEqual(max(ys) - min(ys), 2.0)

    def test_wrap_keeps_all_words(self):
        f = pr.ImageFont.truetype(pr.FONT, 20)
        out = pr.wrap(['a ' * 200], f, 300)
        self.assertGreater(len(out), 1)
        self.assertEqual(sum(l.split().count('a') for l in out), 200)
        self.assertTrue(all(f.getlength(l) <= 300 for l in out))


@unittest.skipUnless(os.path.exists(M2) and os.path.exists(GS), 'board files missing')
class BoardFacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m2 = pr.Board(M2); cls.gs = pr.Board(GS)

    def test_m2_ac_caps_are_0201_220n_fitted(self):
        for r in ('C143', 'C144'):
            fp = self.m2.fps[r]
            self.assertTrue(fp['lib'].endswith('C_0201_0603Metric')); self.assertEqual(fp['value'], '220nF')
            self.assertFalse(fp['dnp'])

    def test_m2_tx_pins_match_m2_standard_polarity(self):
        # M.2 M-key: 41 PERn0, 43 PERp0 (host RX = module TX) -> M2 TX_P must land on 43 via C144
        pads = {p['name']: p['net'] for p in self.m2.fps['J10']['pads']}
        self.assertEqual(pads['43'], '/M.2 M Key/PET0P'); self.assertEqual(pads['41'], '/M.2 M Key/PET0N')
        self.assertEqual(pads['49'], '/M.2 M Key/PCIe_RX_P'); self.assertEqual(pads['47'], '/M.2 M Key/PCIe_RX_N')
        c144 = {p['name']: p['net'] for p in self.m2.fps['C144']['pads'] if p['name']}
        self.assertEqual(c144, {'1': '/M.2 M Key/PET0P', '2': '/M.2 M Key/PCIe_TX_P'})

    def test_gs_rx_has_no_series_cap(self):
        refs = {r for r, fp in self.gs.fps.items() for p in fp['pads'] if p['net'] == '/cm4-hsio/PCIe_RX_P'}
        self.assertEqual(refs, {'J1', 'U4', 'R107'})
        self.assertTrue(self.gs.fps['R107']['dnp'])

    def test_m2_tx_vias_two_per_net(self):
        for n in ('/M.2 M Key/PCIe_TX_P', '/M.2 M Key/PCIe_TX_N'):
            self.assertEqual(sum(1 for v in self.m2.vias if v[0] == n), 2)


if __name__ == '__main__':
    unittest.main()
