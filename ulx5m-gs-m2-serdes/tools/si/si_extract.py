#!/usr/bin/env python3
"""SerDes path SI extractor for KiCad 7-10 .kicad_pcb (stdlib only).
Per net: segments (layer, width, length), vias (size/drill/layers), pads of attached parts,
P/N edge gap per layer, and reference-plane coverage (filled zones on adjacent planes) sampled along the trace."""
import re, sys, math, json, collections
TOK = re.compile(r'\s+|\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')
def parse(s):
    st=[[]]
    for m in TOK.finditer(s):
        t=m.group(0)
        if t[0].isspace(): continue
        if t=='(': st.append([])
        elif t==')': x=st.pop(); st[-1].append(x)
        else: st[-1].append(t[1:-1] if t[0]=='"' else t)
    return st[0][0]
def kids(n,k): return [c for c in n if isinstance(c,list) and c and c[0]==k]
def kid(n,k):
    r=kids(n,k); return r[0] if r else None
def netof(n):
    k=kid(n,'net')
    if not k: return None
    return k[2] if len(k)>2 else (NETS.get(k[1],k[1]))
path=sys.argv[1]; pairs=json.loads(sys.argv[2])  # {"label":["P","N"]}
root=parse(open(path).read())
NETS={c[1]:c[2] for c in kids(root,'net') if len(c)>2}
LAYERS={c[1]:c[0] for c in kid(root,'layers')[1:]} if False else None
ALL={n for pr in pairs.values() for n in pr}
segs=collections.defaultdict(list); vias=collections.defaultdict(list); pads=collections.defaultdict(list)
def arclen(a,m,b):
    # circle through 3 points
    ax,ay=a;bx,by=m;cx,cy=b; d=2*(ax*(by-cy)+bx*(cy-ay)+cx*(ay-by))
    if abs(d)<1e-12: return math.dist(a,b)
    ux=((ax*ax+ay*ay)*(by-cy)+(bx*bx+by*by)*(cy-ay)+(cx*cx+cy*cy)*(ay-by))/d
    uy=((ax*ax+ay*ay)*(cx-bx)+(bx*bx+by*by)*(ax-cx)+(cx*cx+cy*cy)*(bx-ax))/d
    r=math.dist((ux,uy),a); ch1=math.dist(a,m); ch2=math.dist(m,b)
    return r*(2*math.asin(min(1,ch1/(2*r)))+2*math.asin(min(1,ch2/(2*r))))
for s in kids(root,'segment')+kids(root,'arc'):
    n=netof(s)
    if n in ALL:
        a=tuple(map(float,kid(s,'start')[1:3])); b=tuple(map(float,kid(s,'end')[1:3]))
        if s[0]=='arc':
            m=tuple(map(float,kid(s,'mid')[1:3])); ln=arclen(a,m,b)
            # split arc into 2 chords via mid for sampling
            for p,q in ((a,m),(m,b)):
                segs[n].append(dict(a=p,b=q,w=float(kid(s,'width')[1]),L=kid(s,'layer')[1],len=ln*math.dist(p,q)/(math.dist(a,m)+math.dist(m,b))))
            continue
        segs[n].append(dict(a=a,b=b,w=float(kid(s,'width')[1]),L=kid(s,'layer')[1],len=math.dist(a,b)))
for v in kids(root,'via'):
    n=netof(v)
    if n in ALL:
        vias[n].append(dict(at=tuple(map(float,kid(v,'at')[1:3])),size=float(kid(v,'size')[1]),drill=float(kid(v,'drill')[1]),layers=kid(v,'layers')[1:]))
for fp in kids(root,'footprint'):
    ref=[p[2] for p in kids(fp,'property') if p[1]=='Reference']
    ref=ref[0] if ref else '?'; lib=fp[1]; fl=kid(fp,'layer')[1]
    at=kid(fp,'at'); fx,fy=float(at[1]),float(at[2]); rot=float(at[3]) if len(at)>3 else 0
    for p in kids(fp,'pad'):
        n=netof(p)
        if n in ALL:
            sz=kid(p,'size'); pa=kid(p,'at'); r=math.radians(-rot); px,py=float(pa[1]),float(pa[2])
            pads[n].append(dict(ref=ref,pad=p[1],lib=lib,side=fl,type=p[2],shape=p[3],size=(float(sz[1]),float(sz[2])),at=(round(fx+px*math.cos(r)-py*math.sin(r),3),round(fy+px*math.sin(r)+py*math.cos(r),3))))
# zones: filled polygons per layer and net
fills=collections.defaultdict(list)
for z in kids(root,'zone'):
    zn=netof(z) or '?'
    for fpoly in kids(z,'filled_polygon'):
        L=kid(fpoly,'layer')[1]; pts=[(float(p[1]),float(p[2])) for p in kid(fpoly,'pts')[1:] if p[0]=='xy']
        xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
        fills[L].append((zn,pts,(min(xs),min(ys),max(xs),max(ys))))
def inpoly(x,y,pts):
    c=False; j=len(pts)-1
    for i in range(len(pts)):
        xi,yi=pts[i]; xj,yj=pts[j]
        if (yi>y)!=(yj>y) and x<(xj-xi)*(y-yi)/(yj-yi+1e-18)+xi: c=not c
        j=i
    return c
def cover(L,x,y):
    out=[]
    for zn,pts,bb in fills.get(L,[]):
        if bb[0]<=x<=bb[2] and bb[1]<=y<=bb[3] and inpoly(x,y,pts): out.append(zn)
    return out
# filled_polygon with holes: KiCad encodes holes via slit polygons -> even-odd inside test handles it
REF=json.loads(sys.argv[3]) if len(sys.argv)>3 else {'F.Cu':['In1.Cu'],'B.Cu':['In4.Cu'],'In2.Cu':['In1.Cu','In3.Cu'],'In3.Cu':['In2.Cu','In4.Cu']}
def segdist(p,a,b):
    ax,ay=a;bx,by=b;px,py=p;dx,dy=bx-ax,by-ay;L2=dx*dx+dy*dy
    t=0 if L2==0 else max(0,min(1,((px-ax)*dx+(py-ay)*dy)/L2))
    return math.dist(p,(ax+t*dx,ay+t*dy))
res={}
for lab,(P,N) in pairs.items():
    r=dict(nets={})
    for n in (P,N):
        byL=collections.defaultdict(float); W=collections.defaultdict(set)
        for s in segs[n]: byL[s['L']]+=s['len']; W[s['L']].add(s['w'])
        # reference-plane sampling every 0.1 mm
        refs=collections.Counter(); gaps=[]
        for s in segs[n]:
            k=max(1,int(s['len']/0.1))
            for i in range(k):
                t=(i+0.5)/k; x=s['a'][0]+t*(s['b'][0]-s['a'][0]); y=s['a'][1]+t*(s['b'][1]-s['a'][1])
                for RL in REF.get(s['L'],[]):
                    c=cover(RL,x,y); key=f"{s['L']}->{RL}:{'/'.join(sorted(set(c))) or 'NONE'}"
                    refs[key]+=s['len']/k
                    if not c: gaps.append((RL,round(x,2),round(y,2)))
        r['nets'][n]=dict(total=round(sum(byL.values()),2),by_layer={k:round(v,2) for k,v in byL.items()},widths={k:sorted(v) for k,v in W.items()},
            vias=vias[n],pads=pads[n],ref_plane_mm={k:round(v,2) for k,v in refs.items()},ref_gap_samples=gaps[:6],n_ref_gap=len(gaps))
    # P/N edge gap per layer: for each P sample, nearest N segment on same layer (within 0.6 mm)
    gl=collections.defaultdict(list)
    for s in segs[P]:
        k=max(1,int(s['len']/0.1))
        for i in range(k):
            t=(i+0.5)/k; p=(s['a'][0]+t*(s['b'][0]-s['a'][0]), s['a'][1]+t*(s['b'][1]-s['a'][1]))
            best=None
            for q in segs[N]:
                if q['L']!=s['L']: continue
                d=segdist(p,q['a'],q['b'])-(s['w']+q['w'])/2
                best=d if best is None or d<best else best
            if best is not None and best<0.6: gl[s['L']].append((round(best,3),s['len']/k))
    r['pn_gap']={L:dict(coupled_mm=round(sum(w for _,w in v),2),gap_median=sorted(g for g,_ in v)[len(v)//2],gap_min=min(g for g,_ in v),hist=collections.Counter(round(g,2) for g,_ in v).most_common(4)) for L,v in gl.items()}
    r['skew_mm']=round(r['nets'][P]['total']-r['nets'][N]['total'],2)
    res[lab]=r
print(json.dumps(res,indent=1,default=str))
