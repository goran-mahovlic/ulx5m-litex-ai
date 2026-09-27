#!/usr/bin/env python3
"""Differential channel cascade (odd-mode ABCD) GS -> baseboard -> FFC -> adapter -> M2, and peak-distortion eye estimate.
Line params (Zdiff, eeff, cond/diel loss @2.5 GHz in dB/mm) come from fd2d.py runs (matrix.log / run_pads.py).
Elements marked U are UNVERIFIED typical values (no drawing/measurement available)."""
import numpy as np, math, json, sys
C0=299792458.0
def kr(f,rq=1.0e-6):
    d=1/np.sqrt(np.pi*f*4e-7*np.pi*5.8e7); return 1+2/np.pi*np.arctan(1.4*(rq/d)**2)
def line(f,Z,eeff,Lmm,c25,d25):
    f=np.maximum(f,1e6)
    ac=c25*np.sqrt(f/2.5e9)*kr(f)/kr(2.5e9); ad=d25*f/2.5e9            # dB/mm
    a=(ac+ad)/8.686*1e3; b=2*np.pi*f*np.sqrt(eeff)/C0; g=(a+1j*b)*Lmm*1e-3
    ch,sh=np.cosh(g),np.sinh(g); return np.array([[ch,Z*sh],[sh/Z,ch]])
def shuntC(f,C): Y=1j*2*np.pi*f*C; o=np.ones_like(f); return np.array([[o,0*o],[Y,o]])
def seriesL(f,L): Zs=1j*2*np.pi*f*L; o=np.ones_like(f); return np.array([[o,Zs],[0*o,o]])
def mm(A,B): return np.einsum('ijf,jkf->ikf',A,B)
def chain(f,els):
    M=None
    for e in els:
        k=e[0]
        if k=='L': T=line(f,*e[1:])
        elif k=='C': T=shuntC(f,e[1])
        elif k=='S': T=seriesL(f,e[1])
        M=T if M is None else mm(M,T)
    return M
def sparams(M,Z0=100.0):
    A,B,C,D=M[0,0],M[0,1],M[1,0],M[1,1]; den=A+B/Z0+C*Z0+D
    return 2/den,(A+B/Z0-C*Z0-D)/den
# ---- building blocks (diff values) ----
CDIE=0.25e-12   # U: 0.5 pF per pin -> 0.25 pF differential
def die(): return [('C',CDIE)]
def gs(stack, direction):
    # stack: 'jlc3313' (JLC default 6L), 'kicad' (0.274 mm generic from the .kicad_pcb), 'fix' (proposed)
    P={'jlc3313':dict(F=(97.0,2.85,0.00864,0.00549),B=(103.0,2.90,0.00823,0.00574),neck=(77.1,2.81,0.0105,0.0055),pad=(44.5,3.32,0.0080,0.0066),via=(59,4.2)),
       'kicad':  dict(F=(118.5,2.86,0.00680,0.00537),B=(131.8,2.87,0.00592,0.00554),neck=(100,2.85,0.0075,0.0054),pad=(82.1,3.16,0.0050,0.0051),via=(59,4.2)),
       'fix':    dict(F=(100.0,2.85,0.0085,0.0055),B=(100.0,2.90,0.0085,0.0057),neck=(92,2.85,0.0095,0.0055),pad=(85,3.2,0.0060,0.0060),via=(85,4.2))}[stack]
    F,B,N,Pd,V=P['F'],P['B'],P['neck'],P['pad'],P['via']
    via=('L',V[0],V[1],1.6,0.0,0.0)
    if direction=='tx':   # U4 U13/V13 -> 15.3 mm F.Cu (R110 DNP pads + C134/C135) -> 9.6 mm F.Cu -> via -> 0.9 mm B.Cu -> J1
        return [('L',*N[:2],1.0,*N[2:]),('L',*F[:2],13.3,*F[2:]),('L',*Pd[:2],0.6,*Pd[2:]),('L',*F[:2],0.5,*F[2:]),
                ('L',*Pd[:2],0.5,*Pd[2:]),('S',0.6e-9),('L',*Pd[:2],0.5,*Pd[2:]),('L',*F[:2],9.6,*F[2:]),via,('L',*B[:2],0.9,*B[2:])]
    else:                 # J1 -> 7.0 mm B.Cu -> via -> 20.2 mm F.Cu (R107 DNP pads near U4) -> U4 U11/V11
        return [('L',*B[:2],7.0,*B[2:]),via,('L',*F[:2],18.2,*F[2:]),('L',*Pd[:2],0.6,*Pd[2:]),('L',*N[:2],1.0,*N[2:])]
def m2(direction, fix=False):
    Ln=(88.3,2.93,0.00943,0.00602) if not fix else (100.0,2.9,0.0098,0.0060)
    Pd=(43.1,3.21,0.0095,0.0067) if not fix else (85,3.2,0.0070,0.0065)
    via=('L',73 if not fix else 90,4.0,0.8,0.0,0.0); edge=('L',80,2.5,1.3,0.0,0.0)  # U: M.2 gold finger over plane void
    if direction=='rx':   # J10 -> F.Cu 10.3 -> via -> B.Cu 54 -> via -> (R107 pads) -> U4
        return [edge,('L',*Ln[:2],9.0,*Ln[2:]),via,('L',*Ln[:2],54.0,*Ln[2:]),via,('L',*Pd[:2],0.6,*Pd[2:]),('L',*Ln[:2],1.0,*Ln[2:])]
    else:                 # U4 -> B.Cu 50 (2 vias) -> F.Cu 10 -> C143/C144 0201 -> 3.3 mm -> J10
        return [('L',*Ln[:2],1.0,*Ln[2:]),('L',*Pd[:2],0.6,*Pd[2:]),via,('L',*Ln[:2],50.3,*Ln[2:]),via,('L',*Ln[:2],9.0,*Ln[2:]),
                ('L',*Pd[:2],0.4,*Pd[2:]),('S',0.4e-9),('L',*Pd[:2],0.4,*Pd[2:]),('L',*Ln[:2],3.3,*Ln[2:]),edge]
def middle(bb_mm=40, ffc_mm=50, ad_mm=30, ffc_Z=90, second_adapter=False, fix=False):
    df40=('L',85,3.0,2.0,0.002,0.001)         # U: Hirose DF40 mated pair
    zif=('L',75 if not fix else 85,3.0,2.0,0.002,0.001)  # U: 0.5 mm FFC ZIF connector
    m2c=('L',85,3.0,3.0,0.002,0.001)           # U: M.2 M-key socket
    bb=('L',95,2.9,bb_mm,0.0085,0.0057)        # U: Waveshare trace, 4L JLC-like
    ffc=('L',ffc_Z,2.6,ffc_mm,0.0030,0.0030)   # U: FFC (RPi spec 90 ohm +-10 %, <= 50 mm)
    ad=('L',95,2.9,ad_mm,0.0085,0.0057)        # U: FFC->M.2 adapter trace
    viaA=('L',65,4.2,1.6,0,0)
    els=[df40,bb,zif,ffc,zif,ad,viaA,m2c]
    if second_adapter: els=els[:-1]+[('L',85,3.0,3.0,0.002,0.001),('L',95,2.9,40,0.0085,0.0057),viaA,m2c]
    return els
def eye(f,S21,rate,ffe_post_db=0.0,dfe_taps=3):
    UI=1/rate; N=len(f); df=f[1]-f[0]
    # TX pulse: 1 UI rect with 0.3 UI 20-80 Gaussian edge filter, FFE post-cursor (de-emphasis) optional
    H=S21*np.exp(-(2*np.pi*f*0.3*UI/2.563)**2/2)
    h=np.fft.irfft(np.concatenate([H,[0]]))*(2*N)*df  # impulse (per s)
    dt=1/(2*N*df); t=np.arange(len(h))*dt; nui=int(round(UI/dt))
    step=np.cumsum(h)*dt; pulse=step-np.concatenate([np.zeros(nui),step[:-nui]])
    if ffe_post_db:
        k=10**(-ffe_post_db/20); c1=-(1-k)/2; c0=1-abs(c1)
        pulse=c0*pulse+c1*np.concatenate([np.zeros(nui),pulse[:-nui]])
    i0=int(np.argmax(pulse)); h0=pulse[i0]
    cur=lambda k: pulse[i0+k*nui] if 0<=i0+k*nui<len(pulse) else 0.0
    pre=sum(abs(cur(-k)) for k in range(1,4)); post=[cur(k) for k in range(1,60)]
    isi_raw=pre+sum(abs(x) for x in post); isi_dfe=pre+sum(abs(x) for x in post[dfe_taps:])
    return dict(h0=round(h0,3),h1=round(post[0],3),EH_raw=round(h0-isi_raw,3),EH_dfe3=round(h0-isi_dfe,3))
def report(name,els):
    f=np.arange(1,4001)*1e7
    S21,S11=sparams(chain(f,els))
    at=lambda F: -20*np.log10(abs(S21[np.argmin(abs(f-F))]))
    rl=-20*np.log10(np.max(abs(S11[(f>=0.1e9)&(f<=2.5e9)])))
    r=dict(IL_1g25=round(at(1.25e9),2),IL_2g5=round(at(2.5e9),2),IL_3g125=round(at(3.125e9),2),RLmin_0_2g5=round(rl,1))
    r['eye_2g5']=eye(f,S21,2.5e9); r['eye_5g']=eye(f,S21,5e9); r['eye_5g_ffe3.5']=eye(f,S21,5e9,3.5); r['eye_6g25']=eye(f,S21,6.25e9)
    print(name,json.dumps(r)); return r
if __name__=='__main__':
    out={}
    for st in ('jlc3313','kicad'):
        out[f'GS-only {st} TX']=report(f'GS-only {st} TX',die()+gs(st,'tx')+die())
    out['M2-only as built RX']=report('M2-only as built RX',die()+m2('rx')+die())
    for st,lab in (('jlc3313','GS v005 JLC-default stackup'),('kicad','GS v005 if built to .kicad_pcb stackup'),('fix','GS fixed')):
        for mid,ml in ((dict(),'nominal (bb40,FFC50,ad30)'),(dict(bb_mm=60,ffc_mm=100,ad_mm=50,second_adapter=True),'worst (bb60,FFC100,2 adapters)')):
            fx=(st=='fix')
            n=f'{lab} + {ml} + M2 {"fixed" if fx else "as built"}: GS->M2'
            out[n]=report(n,die()+gs(st,'tx')+middle(fix=fx,**mid)+m2('rx',fix=fx)+die())
            n=f'{lab} + {ml} + M2 {"fixed" if fx else "as built"}: M2->GS'
            out[n]=report(n,die()+m2('tx',fix=fx)+list(reversed(middle(fix=fx,**mid)))+gs(st,'rx')+die())
    json.dump(out,open('cascade_results.json','w'),indent=1)
