#!/usr/bin/env bash
# Environment for building/simulating the LiteX Ethernet design. `source` this first.
#
#   source ./env.sh
#
# Two things must be on the path: an oss-cad-suite install (Yosys, nextpnr-himbaechel,
# openFPGALoader, gmpack) and a LiteX checkout tree (migen + litex + liteeth + litedram +
# litex-boards). Override the two locations below via the environment if yours differ:
#
#   OSS_CAD_SUITE=/opt/oss-cad-suite  LXROOT=/opt/litex  source ./env.sh
#
# CRITICAL: the LiteX fork's migen MUST come before the oss-cad bundled migen, or the
# migen simulator's memory transform crashes (port.dat_r is None).

OSS_CAD_SUITE="${OSS_CAD_SUITE:-/home/nik/oss-cad-suite-backup}"
LXROOT="${LXROOT:-/home/nik/litex-build}"

if [ -f "$OSS_CAD_SUITE/environment" ]; then
    source "$OSS_CAD_SUITE/environment"
else
    echo "[env] WARNING: $OSS_CAD_SUITE/environment not found; set OSS_CAD_SUITE=<path> and re-source." >&2
fi

export LXROOT
export PYTHONPATH="$LXROOT/migen:$LXROOT/litex:$LXROOT/liteeth:$LXROOT/litedram:$LXROOT/litex-boards"
# optional cores (SoC target, TASK-5032 phase 2): present only in the ~/app/litex-1g-deps tree
for _c in litesdcard litespi; do [ -d "$LXROOT/$_c" ] && PYTHONPATH="$PYTHONPATH:$LXROOT/$_c"; done
# Version-matched pythondata packages (if present alongside the LiteX tree) must precede
# any pip-installed copies on the path.
for _pd in "$LXROOT"/pythondata-*; do
    [ -e "$_pd" ] && PYTHONPATH="$_pd:$PYTHONPATH"
done
export PYTHONPATH
export LITEX_ROOT="$LXROOT"
export LITEETH_TEST_ROOT="$LXROOT/liteeth"   # so sims can import `test.model`
echo "[env] python=$(python3 --version 2>&1 | awk '{print $2}') LXROOT=$LXROOT migen=$LXROOT/migen (fork)"
