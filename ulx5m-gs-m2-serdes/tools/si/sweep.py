import numpy as np, json
from cascade import *
f=np.arange(1,4001)*1e7
chains={
 'GS-only (JLC default)': die()+gs('jlc3313','tx')+die(),
 'M2-only as built': die()+m2('rx')+die(),
 'chain nominal, as built GS->M2': die()+gs('jlc3313','tx')+middle()+m2('rx')+die(),
 'chain worst, as built GS->M2': die()+gs('jlc3313','tx')+middle(bb_mm=60,ffc_mm=100,ad_mm=50,second_adapter=True)+m2('rx')+die(),
 'chain nominal, GS .kicad stackup': die()+gs('kicad','tx')+middle()+m2('rx')+die(),
}
rates=[2.5,3.125,4,5,6.25,8,10,12.5]
res={}
for n,els in chains.items():
    S21,_=sparams(chain(f,els)); row={}
    for r in rates:
        e=eye(f,S21,r*1e9); row[r]=e['EH_dfe3']
    res[n]=row; print(f"{n:40s}"+' '.join(f"{r:>5}G:{row[r]:.2f}" for r in rates))
json.dump(res,open('rate_sweep.json','w'),indent=1)
