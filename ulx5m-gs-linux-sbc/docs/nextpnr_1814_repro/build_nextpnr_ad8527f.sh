#!/bin/bash
# Local build script used in TASK-5091 (paths are from the build machine; adapt them). Builds nextpnr-himbaechel (gatemate) at YosysHQ main ad8527f8 (#1817).
# nextpnr-himbaechel (gatemate) at YosysHQ main ad8527f8 (#1817 IOBUF arcs), TASK-5090
set -euo pipefail
export PATH=/home/klaudio/app/raid/tools/nextpnr-pr1810/venv/bin:$PATH TMPDIR=/home/klaudio/app/raid/tools/nextpnr-main-ad8527f/tmp
git -C /home/klaudio/app/raid/tools/nextpnr-gatemate-setuphold/src fetch -q origin
[ -d /home/klaudio/app/raid/tools/nextpnr-main-ad8527f/src ] || { git -C /home/klaudio/app/raid/tools/nextpnr-gatemate-setuphold/src worktree add --detach /home/klaudio/app/raid/tools/nextpnr-main-ad8527f/src ad8527f8; git -C /home/klaudio/app/raid/tools/nextpnr-main-ad8527f/src submodule update --init --recursive; }
cmake -S /home/klaudio/app/raid/tools/nextpnr-main-ad8527f/src -B /home/klaudio/app/raid/tools/nextpnr-main-ad8527f/src/build -G Ninja -DARCH=himbaechel -DHIMBAECHEL_UARCH=gatemate   -DEXTERNAL_CHIPDB=ON -DEXTERNAL_CHIPDB_ROOT=/home/klaudio/app/raid/tools/nextpnr-main-ad8527f/share/nextpnr -DHIMBAECHEL_GATEMATE_DEVICES= -DHIMBAECHEL_PEPPERCORN_PATH=/nonexistent   -DBUILD_GUI=OFF -DBUILD_PYTHON=OFF -DCMAKE_BUILD_TYPE=Release -DBoost_USE_STATIC_LIBS=ON -DBOOST_ROOT=/home/klaudio/app/raid/tools/nextpnr-pr1810/deps/boost -DEigen3_DIR=/home/klaudio/app/raid/tools/nextpnr-pr1810/deps/eigen/share/eigen3/cmake
ninja -C /home/klaudio/app/raid/tools/nextpnr-main-ad8527f/src/build -j 8 nextpnr-himbaechel
mkdir -p /home/klaudio/app/raid/tools/nextpnr-main-ad8527f/bin /home/klaudio/app/raid/tools/nextpnr-main-ad8527f/share/nextpnr/himbaechel
install -m755 /home/klaudio/app/raid/tools/nextpnr-main-ad8527f/src/build/nextpnr-himbaechel /home/klaudio/app/raid/tools/nextpnr-main-ad8527f/bin/
echo BUILD_OK
