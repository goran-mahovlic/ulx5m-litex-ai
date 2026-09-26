out=open(OUTFILE,'w')
def dly(net,u):
    try: return ctx.getDelayNS(ctx.getNetinfoRouteDelay(net,u))
    except Exception as e: return -1
def walk(cellname, depth, acc):
    c=ctx.cells[cellname]
    for pn,p in c.ports:
        if str(p.type)!='PortType.PORT_IN' and 'IN' not in str(p.type): continue
        net=p.net
        if net is None: continue
        for u in net.users:
            if u.cell.name==cellname and u.port==pn:
                d=dly(net,u)
                drv=net.driver
                out.write("  "*depth+"%s.%s <- net %s (%.3f ns) <- %s.%s [%s]\n"%(cellname[-50:],pn,net.name[-60:],d,drv.cell.name[-50:] if drv.cell else None,drv.port, drv.cell.bel if drv.cell else ''))
                if drv.cell and depth<4 and 'GLBOUT' not in drv.cell.type and 'PLL' not in drv.cell.type:
                    walk(drv.cell.name, depth+1, acc+d)
for name,c in ctx.cells:
    if name.endswith('$iosel') and any(k in name for k in TARGETS):
        out.write("== %s bel=%s\n"%(name,c.bel))
        walk(name,0,0.0)
out.close()
