#!/usr/bin/env python3
"""uartprobe.py [secs] - raw byte count on the gs UART (DirtyJTAG E660583883501E2C if01), last 60 bytes (TASK-5483)."""
import serial, sys, time
s = serial.Serial("/dev/serial/by-id/usb-Jean_THOMAS_DirtyJTAG_E660583883501E2C-if01", 115200, timeout=0.2)
t, b = time.time(), b""
while time.time() - t < float(sys.argv[1] if len(sys.argv) > 1 else 4):
    b += s.read(512)
print("UART bytes", len(b), b[-60:])
