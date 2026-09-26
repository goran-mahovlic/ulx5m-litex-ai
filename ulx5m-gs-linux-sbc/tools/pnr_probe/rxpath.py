import json
res={'rx':[], 'tx':[]}
def d(net,u):
    try: return round(ctx.getDelayNS(ctx.getNetinfoRouteDelay(net,u)),3)
    except Exception: return -1
for name, net in ctx.nets:
    drv=net.driver
    dc=drv.cell.name if drv.cell else ''
    if name in ('eth_rx_clk',) or 'eth_clocks_rx' in dc:
        ds=[(d(net,u),u.cell.name[-60:],u.port) for u in net.users]
        res['rx'].append([name, dc[-50:], drv.port, len(ds), min(x[0] for x in ds) if ds else None, max(x[0] for x in ds) if ds else None, sorted(ds)[-5:]])
    if dc.endswith('$iosel') and ('rx_' in dc):
        ds=[(d(net,u),u.cell.name[-60:],u.port) for u in net.users]
        res['rx'].append([name[-60:], dc.split('.')[-1], drv.port, len(ds), min(x[0] for x in ds), max(x[0] for x in ds), []])
    for u in net.users:
        if u.cell.name.endswith('$iosel') and ('rx_' in u.cell.name or 'clocks_rx' in u.cell.name) and u.port.startswith('CLOCK'):
            res['rx'].append(['CLK->'+u.cell.name.split('.')[-1]+'.'+u.port, dc[-50:], drv.port, 1, d(net,u), d(net,u), []])
json.dump(res, open(OUT,'w'), indent=0)
