#!/bin/sh
# TASK-4999: permanent reader of the DirtyJTAG UART (keeps the RP2040 buffer drained)
stty -F /dev/ttyACM0 115200 raw -echo
while true; do cat /dev/ttyACM0 >> /tmp/uart_log.bin; sleep 0.2; done
