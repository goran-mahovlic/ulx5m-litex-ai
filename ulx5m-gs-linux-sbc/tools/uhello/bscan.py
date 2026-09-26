import serial, time, sys
for b in [int(x) for x in sys.argv[1:]]:
    s = serial.Serial("/dev/ttyACM0", b, timeout=0.3); s.reset_input_buffer(); time.sleep(0.2); s.reset_input_buffer()
    t0 = time.time(); d = b""
    while time.time() - t0 < 2.5: d += s.read(4096)
    s.close()
    i = d.find(b"HELLO")
    print(b, len(d), d[i:i+16] if i >= 0 else d[:12].hex(), flush=True)
