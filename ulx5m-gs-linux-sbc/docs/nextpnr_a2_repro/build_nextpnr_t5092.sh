#!/bin/bash
# nextpnr-himbaechel (gatemate) = ad8527f8 + branch t5092-a2 (clock router without CPE bridges, D2D-aware route box/estimate + a DEBUG commit), TASK-5092. Local paths.
set -euo pipefail
export PATH=/home/klaudio/app/raid/tools/nextpnr-pr1810/venv/bin:$PATH TMPDIR=/home/klaudio/app/raid/tools/nextpnr-a2-t5092/tmp
cmake -S /home/klaudio/app/raid/tools/nextpnr-a2-t5092/src -B /home/klaudio/app/raid/tools/nextpnr-a2-t5092/src/build -G Ninja -DARCH=himbaechel -DHIMBAECHEL_UARCH=gatemate   -DEXTERNAL_CHIPDB=ON -DEXTERNAL_CHIPDB_ROOT=/home/klaudio/app/raid/tools/nextpnr-main-ad8527f/share/nextpnr -DHIMBAECHEL_GATEMATE_DEVICES= -DHIMBAECHEL_PEPPERCORN_PATH=/nonexistent   -DBUILD_GUI=OFF -DBUILD_PYTHON=OFF -DCMAKE_BUILD_TYPE=Release -DBoost_USE_STATIC_LIBS=ON -DBOOST_ROOT=/home/klaudio/app/raid/tools/nextpnr-pr1810/deps/boost -DEigen3_DIR=/home/klaudio/app/raid/tools/nextpnr-pr1810/deps/eigen/share/eigen3/cmake
ninja -C /home/klaudio/app/raid/tools/nextpnr-a2-t5092/src/build -j 24 nextpnr-himbaechel
mkdir -p /home/klaudio/app/raid/tools/nextpnr-a2-t5092/bin
install -m755 /home/klaudio/app/raid/tools/nextpnr-a2-t5092/src/build/nextpnr-himbaechel /home/klaudio/app/raid/tools/nextpnr-a2-t5092/bin/
echo BUILD_OK
