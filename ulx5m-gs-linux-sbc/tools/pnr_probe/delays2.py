import json
res={'io_sinks':[], 'clocks':[], 'io_src':[]}
for name, net in ctx.nets:
    drv=net.driver
    dcell = drv.cell.name if drv.cell else ''
    users=list(net.users)
    ds=[]
    for u in users:
        try: dn=ctx.getDelayNS(ctx.getNetinfoRouteDelay(net,u))
        except Exception: dn=-1
        ds.append((dn,u.cell.name,u.port))
        if 'iosel' in u.cell.name and u.cell.name.endswith('$iosel'):
            res['io_sinks'].append([name,dcell,drv.port,u.cell.name.split('.')[-1],u.port,round(dn,3)])
    if dcell.endswith('$iosel'):
        res['io_src'].append([name,dcell.split('.')[-1],drv.port,len(ds),round(min(d[0] for d in ds),3) if ds else None,round(max(d[0] for d in ds),3) if ds else None])
    if len(users)>20 and ('clk' in name.lower() or 'clock' in name.lower() or 'CLK' in drv.port or 'GLB' in drv.port):
        res['clocks'].append([name,dcell,drv.port,len(ds),round(min(d[0] for d in ds),3),round(max(d[0] for d in ds),3)])
json.dump(res,open(OUT,'w'),indent=0)
