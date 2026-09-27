import sys,json,math,collections
src=open('si_extract.py').read(); src=src[:src.index("path=sys.argv[1]")]
exec(src)
path=sys.argv[1]; pairs=json.loads(sys.argv[2])
root=parse(open(path).read()); NETS={c[1]:c[2] for c in kids(root,'net') if len(c)>2}; globals()['NETS']=NETS
fills=collections.defaultdict(list)
for z in kids(root,'zone'):
    zn=netof(z) or '?'
    for fpoly in kids(z,'filled_polygon'):
        L=kid(fpoly,'layer')[1]; pts=[(float(p[1]),float(p[2])) for p in kid(fpoly,'pts')[1:] if p[0]=='xy']
        xs=[p[0] for p in pts]; ys=[p[1] for p in pts]; fills[L].append((zn,pts,(min(xs),min(ys),max(xs),max(ys))))
def inpoly(x,y,pts):
    c=False; j=len(pts)-1
    for i in range(len(pts)):
        xi,yi=pts[i]; xj,yj=pts[j]
        if (yi>y)!=(yj>y) and x<(xj-xi)*(y-yi)/(yj-yi+1e-18)+xi: c=not c
        j=i
    return c
def gnd(L,x,y): return any(zn=='GND' and bb[0]<=x<=bb[2] and bb[1]<=y<=bb[3] and inpoly(x,y,pts) for zn,pts,bb in fills.get(L,[]))
gv=[tuple(map(float,kid(v,'at')[1:3])) for v in kids(root,'via') if netof(v)=='GND']
segs=collections.defaultdict(list); vias=collections.defaultdict(list)
for s in kids(root,'segment'):
    n=netof(s)
    if n in {x for p in pairs.values() for x in p}:
        segs[n].append((tuple(map(float,kid(s,'start')[1:3])),tuple(map(float,kid(s,'end')[1:3])),float(kid(s,'width')[1]),kid(s,'layer')[1]))
for v in kids(root,'via'):
    n=netof(v)
    if n in segs: vias[n].append(tuple(map(float,kid(v,'at')[1:3])))
for lab,(P,N) in pairs.items():
    res=collections.Counter(); tot=collections.Counter()
    for n in (P,N):
        for a,b,w,L in segs[n]:
            ln=math.dist(a,b); k=max(1,int(ln/0.1)); dx,dy=(b[0]-a[0])/ (ln or 1),(b[1]-a[1])/(ln or 1); nxv,nyv=-dy,dx
            for i in range(k):
                t=(i+0.5)/k; x=a[0]+t*(b[0]-a[0]); y=a[1]+t*(b[1]-a[1])
                for off in (0.15,0.25,0.4):
                    for sgn in (1,-1):
                        d=w/2+off
                        if gnd(L,x+sgn*d*nxv,y+sgn*d*nyv): res[(L,off)]+=ln/k/2
                tot[L]+=ln/k
    vi=[round(min((math.dist(p,g) for g in gv),default=99),2) for n in (P,N) for p in vias[n]]
    print(lab,'| len/layer',{k:round(v,1) for k,v in tot.items()},'| same-layer GND pour within edge+off (mm of trace, avg both sides):',{f"{L}@{o}":round(v,1) for (L,o),v in sorted(res.items())},'| nearest GND via to each signal via:',vi)
