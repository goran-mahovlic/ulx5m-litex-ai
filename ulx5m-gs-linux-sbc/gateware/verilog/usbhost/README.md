# Emard USB 1.1 HID host (TASK-5047)

Source: `emard/ulx3s-misc` `examples/usb/usbhost` (usbh_host_hid.v, usbh_sie.v, usbh_crc5.v, usbh_crc16.v,
usbh_setup_rom.mem; Ultra-Embedded SIE, GPL) and `examples/usb/usb11_phy_vhdl` (OpenCores USB 1.1 PHY, VHDL).

`usb_phy_ghdl.v` is the VHDL PHY converted once to Verilog so the LiteX GateMate flow (yosys, no VHDL) can read it:

    ghdl --synth --std=08 -fsynopsys --out=verilog usb_rx_phy.vhd usb_tx_phy.vhd usb_phy.vhd -e usb_phy

(oss-cad-suite-20260923; generics = defaults: 6 MHz clock, 1.5 Mbit/s low speed.)
Wrapper and CSR interface: `gateware/usb_hid.py`.
