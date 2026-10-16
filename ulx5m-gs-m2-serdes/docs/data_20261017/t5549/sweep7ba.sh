#!/bin/bash
cd ~/app/raid/projekti/ulx5m-litex-ai/ulx5m-gs-m2-serdes/gateware/ber
P="N1 1 N2 5 N3 5 OUTDIV 2 PROFILE 1 TX_NEG 1 OV_TX_AMP 12"
j(){ b=$1; s=$2; L=$( [ $b = gs ] && echo ber_link_gs.v || echo ber_link.v ); NEXTPNR=~/app/tmp/zadaci/TASK-5549_preuzeti-najnoviji-open-source/np7ba06/bin/nextpnr-himbaechel LINK=$L FREQ=40 ./build_ber.sh $b np7ba $s $P 2>/dev/null | grep bit; }
export -f j
printf "gs 7\nm2 2\ngs 11\ngs 12\ngs 13\ngs 14\ngs 15\nm2 11\nm2 12\nm2 13\nm2 14\nm2 15\n" | xargs -P 12 -L1 bash -c 'j $0 $1' > ~/app/tmp/zadaci/TASK-5549_preuzeti-najnoviji-open-source/sweep7ba.out
echo SWEEP_DONE >> ~/app/tmp/zadaci/TASK-5549_preuzeti-najnoviji-open-source/sweep7ba.out
