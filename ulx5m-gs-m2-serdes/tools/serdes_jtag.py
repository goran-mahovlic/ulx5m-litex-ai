"""Common setup for Cologne Chip serdestool over DirtyJTAG, one board per probe.

Since 26.09.2026 each GateMate has its own DirtyJTAG (gs, m2) -> every board is the
NEAR (only) device in its chain, so serdestool runs with chain index 0 on both.
Always start tools through the wrapper so the right probe is chosen:
    fpga-jtag gs run python3 <tool>.py ...
    fpga-jtag m2 run python3 <tool>.py ...
"""
import argparse
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SERDESTOOL = os.environ.get('SERDESTOOL', os.path.join(HERE, 'serdestool.py'))
SERIAL_TO_BOARD = {'E660583883501E2C': 'gs', 'E6613008E33AA42D': 'm2'}

# Fields worth reading on every status poll (name -> regfile field in serdestool).
STATUS_FIELDS = [
    'SERDES_ENABLE', 'SERDES_TESTMODE', 'PLL_LOCKED',
    'RX_CDR_LOCKED', 'RX_EQA_LOCKED', 'RX_BYTE_IS_ALIGNED', 'RX_RESET_DONE',
    'TX_RESET_DONE', 'RX_BUF_ERR', 'TX_BUF_ERR', 'RX_8B10B_EN', 'TX_8B10B_EN',
    'RX_POLARITY', 'TX_POLARITY', 'RX_PRBS_LOCKED', 'RX_PRBS_ERR_CNT',
]


def _load_serdestool():
    spec = importlib.util.spec_from_file_location('serdestool', SERDESTOOL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['serdestool'] = mod
    spec.loader.exec_module(mod)
    return mod


def _idx0_compat(s):
    """serdestool >= 56aa48b takes the chain index first: rd_regfile(idx, addr), wr_regfile(idx, addr, data, mask).
    Our tools call rd_regfile(addr=..) / wr_regfile(addr=.., data=.., mask=..) (one board per probe -> idx 0).
    Both call styles keep working: an explicit idx (positional or keyword) goes straight through."""
    rd, wr = s.rd_regfile, s.wr_regfile

    def rd_regfile(*a, **k):
        return rd(*a, **k) if ('idx' in k or len(a) + len(k) == 2) else rd(0, *a, **k)

    def wr_regfile(*a, **k):
        return wr(*a, **k) if ('idx' in k or len(a) + len(k) == 4) else wr(0, *a, **k)
    s.rd_regfile, s.wr_regfile = rd_regfile, wr_regfile


def probe_board(dev):
    """'gs'/'m2' from the probe serial number, '?' if unknown/unreadable."""
    try:
        import usb.util
        return SERIAL_TO_BOARD.get(usb.util.get_string(dev, dev.iSerialNumber), '?')
    except Exception:
        return '?'


class Serdes:
    """serdestool.SerdesTool bound to the probe chosen by FPGA_JTAG_BUSDEV."""

    def __init__(self, freq_khz=6000):
        from dirtyjtag_engine import DirtyJtagEngine
        st = _load_serdestool()
        a = argparse.Namespace(board='auto', idx=0, freq='6M', genmod=None, listdev=False,
                               rdregrx=False, rdregrxdata=False, rdregtx=False, rdregpll=False,
                               rdstatuspll=False, gui=False, tcprbs=False, tcloopback=False,
                               tcuipattern=None, tceyemeas=False, serial=None)
        st.args = a
        st.FindAndFormatFtdiAddr = lambda i=0: 'dirtyjtag://'
        self.eng = DirtyJtagEngine(freq_khz=freq_khz)
        self.board = probe_board(self.eng.dev)
        self.busdev = self.eng.busdev
        self.st = st
        self.s = st.SerdesTool(a, self.eng, hwinit=True)   # reads IDCODE, no regfile write
        _idx0_compat(self.s)

    def field(self, name):
        f = self.s.regfile.fields[name]
        w = self.s.rd_regfile(addr=f['addr'])            # wren=0, mask=0 -> read only
        return int(w[f['lbit']:f['hbit'] + 1])

    def word(self, addr):
        return int(self.s.rd_regfile(addr=addr))

    def loopback(self):
        """All loopback bits (read-only): dict from loopback.decode_loopback."""
        from loopback import decode_loopback
        return decode_loopback(self.word(0x2A), self.word(0x40))

    def rx80(self):
        return int(self.s.rd_regfile_rx_data()[1])

    def idcode(self):
        return self.s._tool.idcode_seq()

    def header(self):
        return 'board=%s busdev=%s idcode=0x%08X' % (self.board, self.busdev, self.idcode())

    def close(self):
        import usb.util
        usb.util.release_interface(self.eng.dev, 0)
