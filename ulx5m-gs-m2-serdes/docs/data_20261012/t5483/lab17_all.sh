#!/bin/bash
# 2.5 G search then 5 G (P2 bits) search, same points; baseline at start and end of each (drift check).
H=/home/pi/ulx5m-serdes/t5483; P="base| post0|TX_SEL_POST=0 post10|TX_SEL_POST=10 post15|TX_SEL_POST=15 pre0|TX_SEL_PRE=0 amp24|TX_AMP=24 pk16|RX_AFE_PEAK=16 pk8|RX_AFE_PEAK=8 pk31|RX_AFE_PEAK=31 g1|RX_AFE_GAIN=1 g2|RX_AFE_GAIN=2 ckp126|RX_CDR_CKP=126 ckp30|RX_CDR_CKP=30 ckp248|RX_CDR_CKP=248 th16|RX_CDR_TRANS_TH=16 vcm4|RX_AFE_VCMSEL=4,RX_RTERM_VCMSEL=4 base2|"
bash $H/lab17.sh s2g5 gs_2g5.bit m2_2g5.bit 200 $P
bash $H/lab17.sh s5g gs_5g.bit m2_5g.bit 1000 $P
echo "LAB17 ALL DONE $(date +%T)"
