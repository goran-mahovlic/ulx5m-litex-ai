#!/bin/bash
# TASK-5487 step 2: rest of the 2.5 G sweep (lab17 stopped at ckp126) + per-board TX_SEL_POST (PROFILE 1 default PRE=5 POST=5 AMP=31 CKP=62 TH=8).
H=/home/pi/ulx5m-serdes/t5483
bash $H/lab18.sh s2g5 gs_2g5.bit m2_2g5.bit 200 "base|" "ckp126|RX_CDR_CKP=126" "ckp30|RX_CDR_CKP=30" "ckp248|RX_CDR_CKP=248" "th16|RX_CDR_TRANS_TH=16" \
  "vcm4|RX_AFE_VCMSEL=4,RX_RTERM_VCMSEL=4" "post12|TX_SEL_POST=12" "m2p15|m2:TX_SEL_POST=15" "gs10m2p15|gs:TX_SEL_POST=10,m2:TX_SEL_POST=15" \
  "gs12m2p20|gs:TX_SEL_POST=12,m2:TX_SEL_POST=20" "gs10m2p12|gs:TX_SEL_POST=10,m2:TX_SEL_POST=12" "base2|"
echo "LAB18_2G5 ALL DONE $(date +%T)"
