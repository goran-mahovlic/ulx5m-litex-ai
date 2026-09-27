import json,sys
from fd2d import pair,microstrip,stripline
def ms(w,s,h,er,tand,t=0.035,mask=(0.015,3.8)):
    m=max(0.6,6*h); return microstrip(w,s,h,er,tand,t=t,mask=mask,margin=m,air=max(0.5,6*h))
def sl(w,s,hb,ha,erb,tb,era,ta,t=0.0152):
    m=max(0.6,4*max(hb,ha)); return stripline(w,s,hb,ha,erb,tb,t=t,margin=m,er_above=era,tand_above=ta)
def dx_for(h): return min(0.005,max(0.0025,h/25))
cases=[
 # label, geom, dx
 ("GS KiCad-file stackup | outer F/B.Cu | w0.127 s0.145 (v005 F.Cu)", ms(0.127,0.145,0.274,4.5,0.02), 0.005),
 ("GS KiCad-file stackup | outer | w0.127 s0.21 (v005 B.Cu)",        ms(0.127,0.21,0.274,4.5,0.02), 0.005),
 ("GS KiCad-file stackup | outer | w0.127 s0.24 (v003 F.Cu)",        ms(0.127,0.24,0.274,4.5,0.02), 0.005),
 ("GS KiCad-file stackup | outer | w0.203 s0.17 refclk SER_CLK",      ms(0.2032,0.17,0.274,4.5,0.02), 0.005),
 ("GS KiCad-file stackup | In2 stripline | w0.127 s0.23 SER_CK",     sl(0.127,0.23,0.274,0.274,4.5,0.02,4.5,0.02), 0.005),
 ("JLC06161H-3313 | outer (3313 0.0994 Dk4.1) | w0.127 s0.145 (v005 F.Cu)", ms(0.127,0.145,0.0994,4.1,0.02), 0.0025),
 ("JLC06161H-3313 | outer | w0.127 s0.21 (v005 B.Cu)",               ms(0.127,0.21,0.0994,4.1,0.02), 0.0025),
 ("JLC06161H-3313 | outer | w0.127 s0.24 (v003 F.Cu)",               ms(0.127,0.24,0.0994,4.1,0.02), 0.0025),
 ("JLC06161H-3313 | outer | w0.203 s0.17 refclk",                   ms(0.2032,0.17,0.0994,4.1,0.02), 0.0025),
 ("JLC06161H-3313 | In2 (In3 0.1088 2116 Dk4.16 below, In1 0.55 core above) | w0.127 s0.23 SER_CK", sl(0.127,0.23,0.1088,0.55,4.16,0.018,4.3,0.018), 0.0025),
 ("JLC06161H-1080 | outer (1080 0.0764 Dk3.91) | w0.127 s0.145 (v005 F.Cu)", ms(0.127,0.145,0.0764,3.91,0.02), 0.0025),
 ("JLC06161H-1080 | outer | w0.127 s0.21 (v005 B.Cu)",               ms(0.127,0.21,0.0764,3.91,0.02), 0.0025),
 ("JLC06161H-1080 | outer | w0.127 s0.24 (v003 F.Cu)",               ms(0.127,0.24,0.0764,3.91,0.02), 0.0025),
 ("JLC06161H-1080 | In2 (In3 0.2104 7628 Dk4.4 below, In1 0.55 above) | w0.127 s0.23 SER_CK", sl(0.127,0.23,0.2104,0.55,4.4,0.02,4.41,0.02), 0.0025),
 ("M2 as built JLC04081H-1080 | outer (0.0764 Dk3.91) | w0.147 s0.253", ms(0.147,0.253,0.0764,3.91,0.02), 0.0025),
 ("M2 as built | outer | w0.13 s0.27 (BGA neck)",                    ms(0.13,0.27,0.0764,3.91,0.02), 0.0025),
]
if __name__!="__main__": cases=[]
sel=sys.argv[1:]
out={}
for i,(lab,g,dx) in enumerate(cases):
    if sel and str(i) not in sel: continue
    r=pair(g,dx=dx); r={k:(round(float(v),2) if isinstance(v,float) or hasattr(v,'dtype') else v) for k,v in r.items()}
    out[lab]=r; print(i,lab,'->',json.dumps(r),flush=True)
json.dump(out,open('zmatrix_%s.json'%('_'.join(sel) or 'all'),'w'),indent=1)
