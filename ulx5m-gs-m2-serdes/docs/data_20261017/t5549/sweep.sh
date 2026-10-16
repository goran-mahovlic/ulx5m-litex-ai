#!/bin/bash
cd ~/app/raid/projekti/ulx5m-litex-ai/ulx5m-gs-m2-serdes/gateware/ber
P="N1 1 N2 5 N3 5 OUTDIV 2 PROFILE 1 TX_NEG 1 OV_TX_AMP 12"
j(){ c=$1; b=$2; s=$3; S=$( [ $c = n ] && echo ~/app/raid/tools/oss-cad-suite-20261016 || echo ~/app/raid/tools/oss-cad-suite-20260923 ); L=$( [ $b = gs ] && echo ber_link_gs.v || echo ber_link.v ); OSS_CAD_SUITE=$S LINK=$L FREQ=40 ./build_ber.sh $b sw_$c 1$s $P 2>/dev/null | grep bit; }
export -f j
for c in n o; do for b in gs m2; do for s in 1 2 3 4 5; do echo $c $b $s; done; done; done | xargs -P 10 -L1 bash -c 'j $0 $1 $2' > ~/app/tmp/zadaci/TASK-5549_preuzeti-najnoviji-open-source/sweep.out
echo SWEEP_DONE >> ~/app/tmp/zadaci/TASK-5549_preuzeti-najnoviji-open-source/sweep.out
