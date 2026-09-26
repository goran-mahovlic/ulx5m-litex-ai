#!/bin/bash
# TASK-5040: print the BIOS commands that paint 8 horizontal colour bands (white, yellow, cyan, green, magenta,
# red, blue, black; 30 lines each) into the 320x240 rgb565 framebuffer at FB (default 0x43f00000).
# The last command writes 8 KiB elsewhere so the 4 KiB write-back D$ flushes the final band to SDRAM.
# Use: bash tools/linux/../sd/bios_cmds.sh <bit> $(bash tools/dvi/testimg_cmds.sh | tr '\n' '|')  - see README
FB=${FB:-0x43f00000}
i=0
for c in ffff ffe0 07ff 07e0 f81f f800 001f 0000; do
  printf 'mem_write 0x%x 0x%s%s 4800 4\n' $((FB + i*19200)) $c $c
  i=$((i+1))
done
printf 'mem_write 0x%x 0 2048 4\n' $((FB - 0x100000))
