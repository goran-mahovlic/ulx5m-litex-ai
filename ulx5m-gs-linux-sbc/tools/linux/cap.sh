#!/bin/bash
# cap.sh <out> <secs> (runs on the Pi, TASK-5051): after lxrun.sh is done, record the board console for <secs>
# without typing (the SoC's console drops typed characters under load; init scripts print the results).
. "$(dirname "$(readlink -f "$0")")/dj_probe.sh" 2>/dev/null || . "$(dirname "$(readlink -f "$0")")/../dj_probe.sh"
while pgrep -f "bash lxrun\.sh" >/dev/null; do sleep 3; done
stty -F $DJ_UART 115200 raw -echo
timeout $2 cat $DJ_UART > $1
