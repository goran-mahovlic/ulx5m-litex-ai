// Test top for the PNRU reference (usb11/phy.v + usb11/regs.v, fetched by sim/tb_usb_pnru.py), TASK-5051.
// USB lines: host tristate + device model (dev_oe/dev_dp/dev_dn from cocotb) + pull-up of the attached
// device (dev_pull: 0 none, 1 FS = D+, 2 LS = D-) + the host's weak pull-downs.
`timescale 1ns/1ps
`default_nettype none
module tb_ref_top (
    input  wire        clk,
    input  wire        rst,
    input  wire        m_sel,
    input  wire [3:0]  m_addr,
    input  wire [31:0] m_data_i,
    output wire [31:0] m_data_o,
    input  wire        m_rd,
    input  wire        m_wr,
    input  wire        dev_oe,
    input  wire        dev_dp,
    input  wire        dev_dn,
    input  wire [1:0]  dev_pull,
    output wire        line_dp,
    output wire        line_dn,
    output wire        host_oe
);
    wire usb_dp, usb_dn;
    assign usb_dp = dev_oe ? dev_dp : 1'bz;
    assign usb_dn = dev_oe ? dev_dn : 1'bz;
    // Icarus drops the strength of `assign (pull1, highz0) net = <expression>`: go through plain wires.
    wire pull_dp = (dev_pull == 2'd1);
    wire pull_dn = (dev_pull == 2'd2);
    assign (pull1, highz0) usb_dp = pull_dp;
    assign (pull1, highz0) usb_dn = pull_dn;
    assign (highz1, weak0) usb_dp = 1'b0;
    assign (highz1, weak0) usb_dn = 1'b0;
    assign line_dp = usb_dp;
    assign line_dn = usb_dn;

    wire       utmi_txvalid, utmi_txready, utmi_rxvalid, utmi_rxactive, utmi_rxerror;
    wire       utmi_termselect, utmi_dppulldown, utmi_dmpulldown;
    wire [1:0] utmi_linestate, utmi_op_mode, utmi_xcvrselect;
    wire [7:0] utmi_data_out, utmi_data_in;
    wire       pu_dp, pu_dn;
    wire [7:0] led;

    PHY phy (
        .clk_i(clk), .rst_i(rst),
        .utmi_data_out_i(utmi_data_out), .utmi_txvalid_i(utmi_txvalid), .utmi_txready_o(utmi_txready),
        .utmi_data_in_o(utmi_data_in), .utmi_rxvalid_o(utmi_rxvalid), .utmi_rxactive_o(utmi_rxactive),
        .utmi_rxerror_o(utmi_rxerror), .utmi_linestate_o(utmi_linestate),
        .utmi_op_mode_i(utmi_op_mode), .utmi_xcvrselect_i(utmi_xcvrselect), .utmi_termselect_i(utmi_termselect),
        .utmi_dppulldown_i(utmi_dppulldown), .utmi_dmpulldown_i(utmi_dmpulldown),
        .usb_fpga_dif(usb_dp), .usb_fpga_dp(usb_dp), .usb_fpga_dn(usb_dn),
        .usb_fpga_pu_dp(pu_dp), .usb_fpga_pu_dn(pu_dn)
    );
    assign host_oe = !phy.rx_mode;

    REGS regs (
        .clk_i(clk), .rst_i(rst), .led_o(led),
        .m_sel(m_sel), .m_addr(m_addr), .m_data_i(m_data_i), .m_data_o(m_data_o), .m_rd(m_rd), .m_wr(m_wr),
        .m_intr_o(),
        .utmi_data_in_i(utmi_data_in), .utmi_rxvalid_i(utmi_rxvalid), .utmi_rxactive_i(utmi_rxactive),
        .utmi_rxerror_i(utmi_rxerror),
        .utmi_data_out_o(utmi_data_out), .utmi_txvalid_o(utmi_txvalid), .utmi_txready_i(utmi_txready),
        .utmi_op_mode_o(utmi_op_mode), .utmi_xcvrselect_o(utmi_xcvrselect), .utmi_termselect_o(utmi_termselect),
        .utmi_dppulldown_o(utmi_dppulldown), .utmi_dmpulldown_o(utmi_dmpulldown), .utmi_linestate_i(utmi_linestate)
    );
endmodule
