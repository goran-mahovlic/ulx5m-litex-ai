#!/bin/bash
# TASK-5093: run on the Pi (user fpga-klaudio, ~/t5092) AFTER a power cycle of gs. Only unmodified gmpack --reset streams.
# 1) top_1a.bit must give "E00000000 K0000000B" (board recovered). 2) top_x.bit = repro (expect EFFFFFFFF K0000000C).
# 3) k_pos.bit (H2 position): K nibbles g7..g0; g0,g1 = die 1A controls (expect B), g2 1B Y~137, g3 Y~153, g4 Y~203,
#    g5 Y~253, g6 X~143 Y~203, g7 X~7 Y~203. B = FF works; anything else = FF on that spot does not update.
# 4) k_h4.bit (H4): per group nibble {1, zero:FF D=tgl EN=tgl toggled, one:FF async SET=tgl seen 1, t:latch G=1 (folded
#    to a wire by the tools = LUT/D2D control)}; g0,g1 on 1A expect F.
cd ~/t5092
for b in top_1a.bit top_x.bit k_pos.bit k_h4.bit; do echo "== $b"; bash uart_rst.sh $b 3 | tail -2; done
