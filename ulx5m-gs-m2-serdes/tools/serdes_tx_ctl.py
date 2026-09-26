#!/usr/bin/env python3
"""WRITES the TX side (and RX polarity) of ONE board over JTAG regfile (used to prove where RX data comes from).

    fpga-jtag m2 run python3 serdes_tx_ctl.py idle on|off     # TX_ELEC_IDLE_OVR/TX_ELEC_IDLE (0x41[1:0])
    fpga-jtag m2 run python3 serdes_tx_ctl.py pattern <80-bit hex>|off   # TX_DATA_OVR (0x41[8], data 0x42)
    fpga-jtag gs run python3 serdes_tx_ctl.py rxpol 0|1|off   # RX_POLARITY_OVR/RX_POLARITY (0x2B[13:12])
    fpga-jtag m2 run python3 serdes_tx_ctl.py txprbs 1..7|off  # TX_PRBS_OVR/SEL (0x40[8:5]); 4 = PRBS-31
    fpga-jtag gs run python3 serdes_tx_ctl.py rxprbs 1..4|off|clr  # RX_PRBS_OVR/SEL (0x2A[7:4]); clr = RX_PRBS_CNT_RESET
    fpga-jtag m2 run python3 serdes_tx_ctl.py wr <addr> <data> <mask>  # raw masked regfile write (hex)

Pattern slots are 10 bits each (LSB first); with 8b10b on, bit 8 = K flag (0x1BC = K28.5).
'off' clears the override so the fabric TX_DATA_I drives the lane again. Needs SERDES_TESTMODE=1."""
import sys

from serdes_jtag import Serdes


def main(argv):
    if argv[1:2] == ['wr'] and len(argv) == 5:
        argv = argv[:2] + [' '.join(argv[2:])]
    if len(argv) != 3 or argv[1] not in ('idle', 'pattern', 'rxpol', 'txprbs', 'rxprbs', 'wr'):
        print(__doc__)
        return 2
    sd = Serdes()
    if sd.field('SERDES_TESTMODE') != 1:
        print('board=%s: SERDES_TESTMODE=0, regfile writes are ignored - load a TESTMODE bitstream' % sd.board)
        sd.close()
        return 1
    s = sd.s
    if argv[1] == 'idle':
        on = argv[2] == 'on'
        s.wr_regfile(addr=0x41, data=0x0003 if on else 0x0000, mask=0x0003)
    elif argv[1] == 'rxpol':
        val = {'0': 0x1000, '1': 0x3000, 'off': 0x0000}[argv[2]]
        s.wr_regfile(addr=0x2B, data=val, mask=0x3000)
    elif argv[1] == 'wr':
        addr, data, mask = (int(x, 16) for x in argv[2].split())
        s.wr_regfile(addr=addr, data=data, mask=mask)
    elif argv[1] == 'txprbs':
        sel = 0 if argv[2] == 'off' else int(argv[2])
        s.wr_regfile(addr=0x40, data=(0x20 | sel << 6) if sel else 0, mask=0x01E0)
    elif argv[1] == 'rxprbs':
        if argv[2] == 'clr':
            s.wr_regfile(addr=0x2A, data=0x0200, mask=0x0200)
        else:
            sel = 0 if argv[2] == 'off' else int(argv[2])
            s.wr_regfile(addr=0x2A, data=(0x10 | sel << 5) if sel else 0, mask=0x00F0)
    elif argv[2] == 'off':
        s.wr_regfile(addr=0x41, data=0x0000, mask=0x1F00)       # TX_DATA_OVR=0, CNT=0
    else:
        s.wr_regfile_tx_data(data=int(argv[2], 16))              # TX_DATA_OVR=1, 5 words, VALID
    print('board=%s busdev=%s %s %s -> reg0x2A=0x%04X reg0x2B=0x%04X reg0x40=0x%04X reg0x41=0x%04X' % (
        sd.board, sd.busdev, argv[1], argv[2], sd.word(0x2A), sd.word(0x2B), sd.word(0x40), sd.word(0x41)))
    sd.close()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
