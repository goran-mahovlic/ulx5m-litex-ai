#!/bin/sh
# stop the ureader loop and its cat (matched via /proc cmdline, never our own shell)
for p in $(pgrep -u fpga-klaudio -x sh); do grep -q ureader /proc/$p/cmdline 2>/dev/null && kill $p; done
sleep 0.3
for p in $(pgrep -u fpga-klaudio -x cat); do kill $p; done
