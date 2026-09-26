#!/usr/bin/env python3
"""
DirtyJtagEngine -- a pyftdi.jtag.JtagEngine-compatible transport for the
Cologne Chip serdestool.py, driving a DirtyJTAG probe (VID 0x1209 / PID 0xC0CA)
over pyusb.

Implements the 6 methods that serdestool's JtagTool uses:
    configure(url)  -- no-op (device already opened in __init__)
    reset()         -- TAP -> Test-Logic-Reset
    write_ir(BitSequence)
    write_dr(BitSequence)
    read_dr(length) -> BitSequence
    go_idle()       -- TAP -> Run-Test/Idle

Bit ordering matches pyftdi: JTAG shifts LSB-first. int(BitSequence) is the value;
the first bit shifted out of / into the register is bit 0 (LSB).
"""

import sys
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import usb.core
import usb.util
from pyftdi.bits import BitSequence

DIRTYJTAG_VID = 0x1209
DIRTYJTAG_PID = 0xC0CA

CMD_STOP   = 0x00
CMD_INFO   = 0x01
CMD_FREQ   = 0x02
CMD_XFER   = 0x03
CMD_SETSIG = 0x04
CMD_GETSIG = 0x05
CMD_CLK    = 0x06

SIG_TCK  = 1 << 1
SIG_TDI  = 1 << 2
SIG_TDO  = 1 << 3
SIG_TMS  = 1 << 4
SIG_TRST = 1 << 5
SIG_SRST = 1 << 6

WRITE_EP = 0x01
READ_EP  = 0x82
TIMEOUT  = 1000


class DirtyJtagEngine:
    """pyftdi JtagEngine work-alike over DirtyJTAG."""

    def __init__(self, frequency=6e6, freq_khz=None):
        # Two probes share 1209:c0ca (gs, m2): pick the one fpga-jtag named in
        # FPGA_JTAG_BUSDEV; refuse to guess when several are present (TASK-5052).
        from probe_select import find_probe
        self.dev = find_probe()
        self.busdev = "%d:%d" % (self.dev.bus, self.dev.address)
        # detach kernel driver if attached
        try:
            if self.dev.is_kernel_driver_active(0):
                self.dev.detach_kernel_driver(0)
        except (NotImplementedError, usb.core.USBError):
            pass
        # Only set configuration if none is active yet; setting it while an
        # interface is (auto-)claimed raises EBUSY. DirtyJTAG has 1 config.
        try:
            cfg = self.dev.get_active_configuration()
        except usb.core.USBError:
            cfg = None
        if cfg is None:
            self.dev.set_configuration()
        try:
            usb.util.claim_interface(self.dev, 0)
        except usb.core.USBError:
            # already claimed by us implicitly; proceed
            pass

        # set clock frequency (kHz)
        khz = int(freq_khz if freq_khz is not None else frequency / 1000)
        self._write([CMD_FREQ, (khz >> 8) & 0xFF, khz & 0xFF, CMD_STOP])

        # Track current TMS/TDI signal levels so CMD_CLK holds them.
        self._tms = 0
        self._tdi = 0
        # Move to a known state.
        self.reset()

    # ---------------- low-level USB ----------------
    def _write(self, data):
        return self.dev.write(WRITE_EP, bytearray(data), TIMEOUT)

    def _read(self, length):
        return self.dev.read(READ_EP, length, TIMEOUT)

    def _set_sig(self, tms=None, tdi=None):
        """Set static TMS/TDI levels (used before pulsing clocks)."""
        if tms is not None:
            self._tms = 1 if tms else 0
        if tdi is not None:
            self._tdi = 1 if tdi else 0
        mask = SIG_TMS | SIG_TDI
        vals = (SIG_TMS if self._tms else 0) | (SIG_TDI if self._tdi else 0)
        self._write([CMD_SETSIG, mask & 0xFF, vals & 0xFF, CMD_STOP])

    def _get_tdo(self):
        """Read the current TDO signal level (0/1)."""
        self._write([CMD_GETSIG, CMD_STOP])
        ret = self._read(1)
        return 1 if (int(ret[0]) & SIG_TDO) else 0

    def _clock(self, tms, tdi, n=1):
        """Pulse TCK n times while holding TMS and TDI at given levels.
        CMD_CLK: [0x06, sig_levels, n_pulses, STOP]. sig_levels carry TMS/TDI."""
        self._tms = 1 if tms else 0
        self._tdi = 1 if tdi else 0
        remaining = n
        while remaining > 0:
            burst = min(remaining, 64)
            levels = (SIG_TMS if tms else 0) | (SIG_TDI if tdi else 0)
            self._write([CMD_CLK, levels & 0xFF, burst, CMD_STOP])
            remaining -= burst

    def _clock_get(self, tms, tdi):
        """Pulse TCK once with given TMS/TDI, return TDO sampled after the clock."""
        # DirtyJTAG samples TDO on the falling edge and reflects it via GETSIG.
        levels = (SIG_TMS if tms else 0) | (SIG_TDI if tdi else 0)
        self._write([CMD_CLK, levels & 0xFF, 1, CMD_STOP])
        return self._get_tdo()

    def _xfer_bits(self, nbits, value):
        """Shift `nbits` (LSB first) out of TDI via CMD_XFER with TMS=0.
        CMD_XFER actually presents TDI on the scan chain (CMD_CLK does NOT --
        CMD_CLK only pulses TCK for TMS navigation and ignores TDI for data).
        Only used for register *write* payload where we don't need TDO.
        nbits must be <= 8 here (we chunk in the caller if larger)."""
        assert 1 <= nbits <= 8
        self._write([CMD_XFER, nbits, value & 0xFF])
        # DirtyJTAG returns the TDO for this transfer; drain it.
        try:
            self._read(1)
        except usb.core.USBError:
            pass

    # ---------------- TAP navigation ----------------
    # State machine: we track it implicitly by always returning to known states.
    # We navigate with explicit TMS sequences (LSB shifted first).

    def _tms_seq(self, bits):
        """Apply a sequence of TMS values (list of 0/1), one TCK each, TDI=0."""
        for b in bits:
            self._clock(tms=b, tdi=0, n=1)

    def reset(self):
        """5 TCK with TMS=1 -> Test-Logic-Reset."""
        self._tms_seq([1, 1, 1, 1, 1])
        self._state = 'TLR'

    def go_idle(self):
        """To Run-Test/Idle WITHOUT a TAP reset (must preserve the loaded IR
        between write_ir and the following write_dr/read_dr)."""
        self._to_rti()

    def _goto_shift_dr(self):
        """From Run-Test/Idle (or TLR) -> Shift-DR.
        Ensure we start from RTI, then: RTI-1->Select-DR, -0->Capture-DR, -0->Shift-DR."""
        self._to_rti()
        self._tms_seq([1, 0, 0])
        self._state = 'SHIFT_DR'

    def _goto_shift_ir(self):
        """From RTI -> Shift-IR: RTI-1->Select-DR, -1->Select-IR, -0->Capture-IR, -0->Shift-IR."""
        self._to_rti()
        self._tms_seq([1, 1, 0, 0])
        self._state = 'SHIFT_IR'

    def _to_rti(self):
        """Get to Run-Test/Idle WITHOUT resetting the TAP (preserve IR).
        Our shifts already end in RTI; reset() ends in TLR. Only TLR needs a
        single TMS=0. Never do a 5xTMS=1 reset here -- that would wipe the IR
        loaded by a preceding write_ir (breaks regfile addr set -> read)."""
        if self._state == 'RTI':
            return
        if self._state == 'TLR':
            self._tms_seq([0])
            self._state = 'RTI'
            return
        # From Exit1/Update or unknown non-reset state: Update-*(1) -> RTI(0).
        self._tms_seq([1, 0])
        self._state = 'RTI'

    # ---------------- register shifting ----------------
    def _shift(self, length, tdi_value=0, capture=False):
        """Shift `length` bits through the currently-selected register
        (must be in Shift-DR or Shift-IR). LSB (bit 0) is shifted first.
        The final bit is shifted with TMS=1 (Exit1), then we advance to
        Update-* and back to Run-Test/Idle.

        Returns captured TDO as an int (LSB = first bit) if capture else None.
        tdi_value: int, bit 0 shifted first.
        """
        tdo = 0
        if capture:
            # Read path: bit-by-bit CMD_CLK + GETSIG (bit-accurate TDO,
            # verified against IDCODE). TDI is 0 for reads.
            for i in range(length):
                last = (i == length - 1)
                tdi_bit = (tdi_value >> i) & 1
                tms = 1 if last else 0
                bit = self._clock_get(tms=tms, tdi=tdi_bit)
                tdo |= (bit & 1) << i
        else:
            # Write path: shift bit-by-bit via CMD_CLK (TDI presented per bit,
            # same primitive as the verified read path). Last bit TMS=1 -> Exit1.
            for i in range(length):
                last = (i == length - 1)
                tdi_bit = (tdi_value >> i) & 1
                self._clock(tms=(1 if last else 0), tdi=tdi_bit, n=1)
        # Now in Exit1-*. Advance Exit1 -1-> Update-* -0-> Run-Test/Idle.
        self._tms_seq([1, 0])
        self._state = 'RTI'
        return tdo if capture else None

    def configure(self, url=None):
        """No-op: DirtyJTAG is already open. serdestool calls this with an FTDI url."""
        return

    def write_ir(self, instruction):
        """Shift instruction into IR. instruction: BitSequence (bit 0 = LSB, shifted first)."""
        length = len(instruction)
        value = int(instruction)
        self._goto_shift_ir()
        self._shift(length, tdi_value=value, capture=False)

    def write_dr(self, data):
        """Shift data into DR. data: BitSequence (bit 0 = LSB, first)."""
        length = len(data)
        value = int(data)
        self._goto_shift_dr()
        self._shift(length, tdi_value=value, capture=False)

    def read_dr(self, length):
        """Shift `length` bits out of DR, TDI=0. Returns BitSequence, bit 0 = first shifted."""
        self._goto_shift_dr()
        val = self._shift(length, tdi_value=0, capture=True)
        return BitSequence(value=val, length=length)

    # serdestool's JtagTool never calls write_tms directly; provided for safety.
    def write_tms(self, bits):
        self._tms_seq([int(b) for b in bits])


if __name__ == '__main__':
    # Standalone IDCODE test (Milestone A), no serdestool involved.
    eng = DirtyJtagEngine(freq_khz=6000)
    eng.reset()
    idcode = eng.read_dr(32)
    print("IDCODE read_dr(32) = 0x%08X" % int(idcode))
    usb.util.release_interface(eng.dev, 0)
