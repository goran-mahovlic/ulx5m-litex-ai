#!/bin/bash
# run_rxprobe.sh [secs] (on the Pi, 30.09.2026): A2 CC_IDDR test on die 1B, both variants in one run.
# Needs: the design running on gs has selfrst (Linux T5094 bitstream or a probe itself), PHY link up.
# For each variant: "R!" (RST_N resets both dies) -> load (--index-chain 0, no -r) -> the Pi sends ARP to .213
# (frames on the RX pins) -> UART lines "C.... F.... D.... R....". IDDR broken = C/F/D stay 0000; FAB = they grow.
S=${1:-4}; D=$(dirname "$(readlink -f "$0")")
U=$(fpga-jtag uart gs) || exit 2
for v in iddr fab; do
  B=$D/A2_rxprobe_$v.bit
  echo "== $v  sha256 $(sha256sum $B | cut -c1-16)"
  stty -F $U 115200 raw -echo; timeout 1 cat $U >/dev/null
  printf 'R!' > $U; sleep 0.5
  echo "load: $(sudo -n /usr/local/bin/fpga-jtag gs "$B" --index-chain 0 2>&1 | grep -E '^Done|rror' | tail -1)"
  ping -q -c $((S * 5)) -i 0.2 192.168.10.213 >/dev/null 2>&1 &
  sleep 1; timeout $S cat $U | tr -d '\r'
  wait
done
