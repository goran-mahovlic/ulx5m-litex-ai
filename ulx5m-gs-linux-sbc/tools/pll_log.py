import sys, time
sys.path.insert(0, "/tmp"); sys.path.insert(0, "/home/pi")
import jtag_mailbox as jm
import pll_serial_rx as pr
eng, t = jm.load_tool(); st = sys.modules["serdestool"]
T = float(sys.argv[1]) if len(sys.argv) > 1 else 10
t0 = time.time(); out = []
try:
    while time.time() - t0 < T:
        a = pr.status(t, st, 0); b = pr.status(t, st, 1)
        out.append((time.time() - t0, a, b))
finally:
    jm.usb.util.release_interface(eng.dev, 0)
for ts, a, b in out:
    print("%6.3f P0 st%d ft%03X f%X | P1 st%d ft%03X f%X" % (ts, (a>>12)&3, (a>>2)&0x3FF, a&3, (b>>12)&3, (b>>2)&0x3FF, b&3))
