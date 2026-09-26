#!/bin/bash
# TASK-5007: poll JTAG every 30 s for 3 h; run the full sequence once when the GateMate IDCODE
# is seen on TWO consecutive polls (a USB re-plug gives other errors -> must not trigger).
ok=0
for i in $(seq 1 360); do
  out=$(sudo -n /usr/local/bin/openFPGALoader -c dirtyJtag --detect 2>&1)
  if echo "$out" | grep -qi "idcode"; then ok=$((ok+1)); else ok=0; fi
  echo "poll $i $(date +%T) ok=$ok: $(echo "$out" | grep -iE 'idcode|fail|error|model' | head -2 | tr '\n' ' ')" > /tmp/t5007_watch.state
  if [ $ok -ge 2 ]; then
    echo "JTAG alive $(date +%T)" >> /tmp/t5007_watch.state
    sleep 10
    /tmp/t5007_run_all.sh > /tmp/t5007_run.log 2>&1; echo "done $(date +%T) exit=$?" >> /tmp/t5007_watch.state; exit 0
  fi
  sleep 30
done
