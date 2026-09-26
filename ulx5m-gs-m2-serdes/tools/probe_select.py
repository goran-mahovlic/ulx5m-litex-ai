"""Pick ONE DirtyJTAG probe when several share VID:PID 1209:c0ca.

The Pi lab (docs/FPGA_LAB_ARHITEKTURA.md) has two probes: gs and m2. `fpga-jtag <b> run <cmd>`
exports FPGA_JTAG_BUSDEV=<bus>:<addr> for the requested board; pyusb tools must honour it,
otherwise usb.core.find() returns whichever probe enumerates first (= wrong board).
Pure logic here so it is unit-testable without hardware (Python 3.7 on the Pi)."""

DIRTYJTAG_VID = 0x1209
DIRTYJTAG_PID = 0xC0CA


class ProbeSelectError(RuntimeError):
    pass


def parse_busdev(busdev):
    try:
        bus, addr = busdev.split(':')
        return int(bus, 10), int(addr, 10)
    except (AttributeError, ValueError):
        raise ProbeSelectError('FPGA_JTAG_BUSDEV=%r is not "<bus>:<addr>"' % (busdev,))


def select_probe(devices, busdev):
    """devices: objects with .bus/.address; busdev: FPGA_JTAG_BUSDEV value or None."""
    devices = list(devices)
    if not devices:
        raise ProbeSelectError('no DirtyJTAG probe (1209:c0ca) found')
    if busdev is None:
        if len(devices) == 1:
            return devices[0]
        raise ProbeSelectError(
            '%d DirtyJTAG probes present and FPGA_JTAG_BUSDEV is not set - refusing to guess. '
            'Run the tool as: fpga-jtag <gs|m2> run python3 <tool>.py' % len(devices))
    want = parse_busdev(busdev)
    for d in devices:
        if (d.bus, d.address) == want:
            return d
    raise ProbeSelectError('no DirtyJTAG probe at %s (present: %s)' % (
        busdev, ', '.join('%d:%d' % (d.bus, d.address) for d in devices)))


def find_probe():
    """pyusb lookup honouring FPGA_JTAG_BUSDEV. Imported lazily so tests need no pyusb."""
    import os
    import usb.core
    devs = usb.core.find(find_all=True, idVendor=DIRTYJTAG_VID, idProduct=DIRTYJTAG_PID)
    return select_probe(devs, os.environ.get('FPGA_JTAG_BUSDEV') or None)
