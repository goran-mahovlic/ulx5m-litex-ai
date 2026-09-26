#!/usr/bin/env bash
# tools/soc_build.sh <name> <target_soc.py args...>  -> build/s_<name>/ (full build: synthesis, P&R, bitstream),
# log ~/.tmp/t5032/soc_<name>.log. Environment: tools/sbc_env.sh (local paths).
cd "$(dirname "$0")/.."
source tools/sbc_env.sh
n=$1; shift
mkdir -p ~/.tmp/t5032
python3 gateware/target_soc.py --build --output-dir build/s_$n "$@" > ~/.tmp/t5032/soc_$n.log 2>&1
rc=$?
echo "$n exit=$rc $(date +%T)" >> ~/.tmp/t5032/soc_done.txt
exit $rc
