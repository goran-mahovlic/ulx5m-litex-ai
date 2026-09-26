"""Unit tests for DirtyJTAG probe selection (no hardware, runs in the container).
Two DirtyJTAG probes share 1209:c0ca; the tool must pick the one named by
FPGA_JTAG_BUSDEV ("<bus>:<addr>") and must refuse to guess when >1 probe exists."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from probe_select import select_probe, ProbeSelectError


class Dev:
    def __init__(self, bus, address):
        self.bus, self.address = bus, address
    def __repr__(self):
        return 'Dev(%d:%d)' % (self.bus, self.address)


GS, M2 = Dev(1, 16), Dev(1, 17)


class SelectProbe(unittest.TestCase):
    def test_picks_device_named_by_busdev(self):
        self.assertIs(select_probe([GS, M2], '1:17'), M2)
        self.assertIs(select_probe([GS, M2], '1:16'), GS)

    def test_order_does_not_matter(self):
        self.assertIs(select_probe([M2, GS], '1:16'), GS)

    def test_accepts_zero_padded_busdev(self):
        self.assertIs(select_probe([GS, M2], '001:017'), M2)

    def test_refuses_to_guess_with_two_probes_and_no_busdev(self):
        with self.assertRaises(ProbeSelectError) as cm:
            select_probe([GS, M2], None)
        self.assertIn('fpga-jtag', str(cm.exception))

    def test_single_probe_without_busdev_is_allowed(self):
        self.assertIs(select_probe([GS], None), GS)

    def test_busdev_not_present_fails(self):
        with self.assertRaises(ProbeSelectError):
            select_probe([GS, M2], '1:99')

    def test_malformed_busdev_fails(self):
        for bad in ('17', '1-17', 'a:b', ''):
            with self.assertRaises(ProbeSelectError):
                select_probe([GS, M2], bad)

    def test_no_probe_fails(self):
        with self.assertRaises(ProbeSelectError):
            select_probe([], '1:16')


if __name__ == '__main__':
    unittest.main()
