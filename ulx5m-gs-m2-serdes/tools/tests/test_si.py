import os, sys, json, math, subprocess, tempfile, unittest
SI = os.path.join(os.path.dirname(__file__), '..', 'si')
sys.path.insert(0, SI)
try:
    import numpy  # noqa: F401  (fd2d/cascade need numpy+scipy; si_extract is stdlib only)
    HAVE_NP = True
except ImportError:
    HAVE_NP = False

BOARD = '''(kicad_pcb (version 20241229)
\t(net 0 "")
\t(net 1 "A_P")
\t(net 2 "A_N")
\t(net 3 "GND")
\t(segment (start 0 0) (end 10 0) (width 0.127) (layer "F.Cu") (net 1))
\t(segment (start 0 0.3) (end 10 0.3) (width 0.127) (layer "F.Cu") (net 2))
\t(arc (start 10 0) (mid 11 1) (end 12 0) (width 0.127) (layer "F.Cu") (net 1))
\t(via (at 10 0.3) (size 0.35) (drill 0.2) (layers "F.Cu" "B.Cu") (net 2))
\t(zone (net 3) (layer "In1.Cu") (filled_polygon (layer "In1.Cu") (pts (xy -1 -1) (xy 5 -1) (xy 5 2) (xy -1 2))))
)
'''


class SiExtract(unittest.TestCase):
    def run_extract(self):
        with tempfile.NamedTemporaryFile('w', suffix='.kicad_pcb', delete=False) as f:
            f.write(BOARD)
        out = subprocess.run([sys.executable, os.path.join(SI, 'si_extract.py'), f.name, json.dumps({'A': ['A_P', 'A_N']})],
                             capture_output=True, text=True, check=True).stdout
        os.unlink(f.name)
        return json.loads(out)['A']

    def test_length_arc_via_gap(self):
        r = self.run_extract()
        # 10 mm straight + half circle of radius 1 mm (pi mm)
        self.assertAlmostEqual(r['nets']['A_P']['total'], 10 + math.pi, places=1)
        self.assertEqual(len(r['nets']['A_N']['vias']), 1)
        # edge gap = 0.3 - 0.127
        self.assertAlmostEqual(r['pn_gap']['F.Cu']['gap_median'], 0.173, places=3)

    def test_reference_plane_coverage(self):
        # plane fill covers x in [-1, 5] only -> ~5 of 10 mm straight N trace has In1 GND underneath
        ref = self.run_extract()['nets']['A_N']['ref_plane_mm']
        self.assertAlmostEqual(ref['F.Cu->In1.Cu:GND'], 5.0, delta=0.2)
        self.assertAlmostEqual(ref['F.Cu->In1.Cu:NONE'], 5.0, delta=0.2)


@unittest.skipUnless(HAVE_NP, 'numpy/scipy not installed')
class FieldSolver(unittest.TestCase):
    def test_microstrip_vs_hammerstad(self):
        import fd2d
        g = fd2d.microstrip(0.304, 0, 0.16, 4.4, 0.0, t=0.005, mask=None, margin=1.5, air=2.0, single=True)
        z = fd2d.pair(g, dx=0.005, single=True)['Z0']
        self.assertLess(abs(z - 50.4) / 50.4, 0.03)   # Hammerstad-Jensen 50.4 ohm

    def test_stripline_vs_cohn(self):
        import fd2d
        g = fd2d.stripline(0.15, 0, 0.25, 0.25, 4.0, 0.0, t=0.005, margin=1.5, single=True)
        z = fd2d.pair(g, dx=0.005, single=True)['Z0']
        self.assertLess(abs(z - 64.4) / 64.4, 0.04)   # Cohn, zero thickness 64.4 ohm


@unittest.skipUnless(HAVE_NP, 'numpy/scipy not installed')
class Cascade(unittest.TestCase):
    def test_matched_lossless_line_is_transparent(self):
        import numpy as np, cascade as C
        f = np.arange(1, 401) * 1e7
        s21, s11 = C.sparams(C.chain(f, [('L', 100.0, 3.0, 50.0, 0.0, 0.0)]))
        self.assertLess(np.max(np.abs(s11)), 1e-9)
        self.assertLess(np.max(np.abs(np.abs(s21) - 1)), 1e-9)

    def test_mismatch_reflection(self):
        import numpy as np, cascade as C
        f = np.array([1e9])
        # quarter-wave-free check: a very short 50 ohm line has |S11| -> 0, a long one peaks at (100^2-50^2)/(100^2+50^2)
        L = 299792458.0 / (4 * 1e9) * 1e3   # quarter wave in mm at eeff=1
        s21, s11 = C.sparams(C.chain(f, [('L', 50.0, 1.0, L, 0.0, 0.0)]))
        self.assertAlmostEqual(float(abs(s11[0])), (100**2 - 50**2) / (100**2 + 50**2), places=6)


if __name__ == '__main__':
    unittest.main()
