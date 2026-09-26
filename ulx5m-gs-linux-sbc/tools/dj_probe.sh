# Sourced by the Pi scripts. The Pi has two DirtyJTAG probes with the same VID:PID (ULX5M-GS "gs" and ULX5M-M2 "m2"),
# and openFPGALoader -c dirtyJtag opens the first one it finds (it ignores --busdev-num). So loading goes through the
# Pi's `fpga-jtag` wrapper, which picks the probe by serial number, and the console is the probe's by-id serial port,
# never /dev/ttyACMn (the numbers follow the plug-in order). Board: DJ_BOARD (default gs).
DJ_BOARD=${DJ_BOARD:-gs}
DJ_UART=$(fpga-jtag uart "$DJ_BOARD" 2>/dev/null)
[ -n "$DJ_UART" ] && [ -e "$DJ_UART" ] || { echo "fpga-jtag: no console for $DJ_BOARD"; exit 2; }
dj_load() { sudo -n /usr/local/bin/fpga-jtag "$DJ_BOARD" "$1" -r 2>&1 | grep -E "^Done|rror" | tail -1; }
