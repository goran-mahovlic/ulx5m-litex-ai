"""CDR_CKI top parameter -> CC_SERDES RX_CDR_CKI (TASK-5087).

Local X2 on M2 = two refclks = a real ppm offset between the boards; with RX_CDR_CKI = 0 (DS1001 table 2.48 default)
the CDR frequency integrator is off. The build must be able to set it per board, and CDR_CKI = 0 must stay the default
so every older bit keeps its bits. Checked by yosys elaboration (no place & route), skipped without yosys.
"""
import json, os, shutil, subprocess, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BER = os.path.join(HERE, '..', '..', 'gateware', 'ber')
OSS = os.environ.get('OSS_CAD_SUITE', os.path.expanduser('~/app/raid/tools/oss-cad-suite-20260923'))
YOSYS = shutil.which('yosys') or os.path.join(OSS, 'bin', 'yosys')
CELLS = os.path.join(os.path.dirname(os.path.dirname(YOSYS)), 'share', 'yosys', 'gatemate', 'cells_bb.v')


def serdes_params(top, chparams):
    """Elaborate top_<top> with chparam and return the CC_SERDES cell parameters (ints)."""
    with tempfile.TemporaryDirectory(dir=os.path.expanduser('~/.tmp')) as d:   # /tmp is a small tmpfs here
        out = os.path.join(d, 'x.json')
        cp = ' '.join('-set %s %s' % kv for kv in chparams.items())
        script = ('read_verilog -lib %s; read_verilog -I. ber_link.v ber_top.v; %s hierarchy -top top_%s; '
                  'proc; flatten; write_json %s' % (CELLS, ('chparam %s top_%s;' % (cp, top)) if cp else '', top, out))
        subprocess.run([YOSYS, '-q', '-p', script], cwd=BER, check=True, capture_output=True)
        mod = json.load(open(out))['modules']['top_%s' % top]
    cells = [c for c in mod['cells'].values() if c['type'] == 'CC_SERDES']
    assert len(cells) == 1, cells
    return {k: int(v, 2) if set(v) <= {'0', '1'} else v for k, v in cells[0]['parameters'].items()}


@unittest.skipUnless(os.path.exists(YOSYS) and os.path.exists(CELLS), 'yosys / gatemate cells_bb.v not found')
class CdrCki(unittest.TestCase):
    def test_default_is_zero_on_both_boards(self):
        # shared refclk (today): integrator off, as in every bit before TASK-5087
        for top in ('gs', 'm2'):
            self.assertEqual(serdes_params(top, {})['RX_CDR_CKI'], 0, top)

    def test_cki_reaches_the_serdes(self):
        for top in ('gs', 'm2'):
            p = serdes_params(top, {'CDR_CKI': 2, 'PROFILE': 1})
            self.assertEqual(p['RX_CDR_CKI'], 2, top)
            self.assertEqual(p['RX_CDR_CKP'], 0x3E, top)      # PROFILE 1 CDR set unchanged

    def test_other_cdr_fields_unchanged(self):
        # CKI alone must not move the frequency accumulator override or the lock config
        a, b = serdes_params('m2', {'PROFILE': 1}), serdes_params('m2', {'PROFILE': 1, 'CDR_CKI': 4})
        for k in ('RX_CDR_FREQ_ACC', 'RX_CDR_SET_ACC_CONFIG', 'RX_CDR_LOCK_CFG', 'RX_CDR_TRANS_TH', 'RX_CDR_FORCE_LOCK'):
            self.assertEqual(a[k], b[k], k)


if __name__ == '__main__':
    unittest.main()
