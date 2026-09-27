import re,sys,math,collections
def netlen(path,pat):
    s=open(path).read(); ap={}; cur=None; net=None; x=y=0; L=collections.defaultdict(float); W=collections.defaultdict(set); fs=1e6
    for m in re.finditer(r'%ADD(\d+)C,([\d.]+)[^%]*%',s): ap[m.group(1)]=float(m.group(2))
    for cmd in re.finditer(r'(?:%|G04 #@! )TO\.N,([^,*]*)[^\n]*|(?:%|G04 #@! )TD[^\n]*|D(\d+)\*|X(-?\d+)Y(-?\d+)D0([123])\*',s):
        if cmd.group(1) is not None: net=cmd.group(1); continue
        if 'TD' in cmd.group(0)[:10]: net=None; continue
        if cmd.group(2): 
            if int(cmd.group(2))>=10: cur=cmd.group(2)
            continue
        nx,ny,d=int(cmd.group(3))/fs,int(cmd.group(4))/fs,cmd.group(5)
        if d=='1' and net and re.search(pat,net) and cur in ap:
            L[net]+=math.dist((x,y),(nx,ny)); W[net].add(ap[cur])
        x,y=nx,ny
    return L,W
pat=sys.argv[1]
for f in sys.argv[2:]:
    L,W=netlen(f,pat)
    for n in sorted(L): print(f"{f.split('/')[-1][:40]:40s} {n:28s} {L[n]:7.2f} mm w={sorted(W[n])}")
