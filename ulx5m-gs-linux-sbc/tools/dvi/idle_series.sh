#!/bin/bash
# idle_series.sh <dir> <n> <gap_s>: n snapshots, report first pixel colour/unique colours, count no-signal (070707/1)
D=$1; N=${2:-30}; G=${3:-2}; mkdir -p $D; cd $D
for i in $(seq -w 1 $N); do curl -s -m 5 -o l_$i.jpg http://192.168.10.14:8090/snap.jpg; sleep $G; done
python3 - <<'PY' 2>/dev/null
from PIL import Image
import glob
out=[]; bad=0
for f in sorted(glob.glob('l_*.jpg')):
    im=Image.open(f).convert('RGB'); c=im.getpixel((320,15)); u=len(set(im.resize((32,24)).getdata()))
    if u==1 and c[0]<16: bad+=1
    out.append('%s:%02x%02x%02x/%d'%(f[2:4],c[0],c[1],c[2],u))
print(' '.join(out)); print('NO-SIGNAL frames: %d/%d'%(bad,len(out)))
PY
