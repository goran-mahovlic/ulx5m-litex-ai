// TASK-5033 (instruction #33): bare-metal Ethernet speed test for the ULX5M-GS netboot SoC (CPU port 192.168.10.213).
// Loaded by the BIOS netboot from TFTP (boot.json -> speedtest.bin at main_ram). Driven over UDP by the Pi
// (tools/speedtest/eth_speedtest.py); every result is also printed on the BIOS serial (GPIO4/5).
//   port 5000  control (ASCII): "RX" start sink | "RXEND" -> "RXSTAT <pkts> <bytes> <ticks>"
//                               "TX <size> <count>" -> blast to the sender, then "TXDONE <pkts> <bytes> <ticks>"
//   port 5001  sink (counted between RX and RXEND)
//   port 5002  echo (payload sent back to the sender port)
// Time base: timer0 as a free-running down counter at CONFIG_CLOCK_FREQUENCY (no uptime CSR in this SoC).
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>

#include <irq.h>
#include <libbase/uart.h>
#include <libliteeth/udp.h>
#include <generated/csr.h>
#include <generated/soc.h>

#define MY_IP   IPTOINT(LOCALIP1, LOCALIP2, LOCALIP3, LOCALIP4)
#define P_CTRL  5000
#define P_SINK  5001
#define P_ECHO  5002

static const uint8_t my_mac[6] = {MACADDR1, MACADDR2, MACADDR3, MACADDR4, MACADDR5, MACADDR6};

static void tick_init(void)
{
	timer0_en_write(0);
	timer0_reload_write(0xffffffff);
	timer0_load_write(0xffffffff);
	timer0_en_write(1);
}

static uint32_t ticks(void)             // elapsed-style: grows with time
{
	timer0_update_value_write(1);
	return 0xffffffff - timer0_value_read();
}

// kbit/s with one decimal of Mb/s, integer only (no float in this CPU)
static void print_rate(const char *what, uint32_t pkts, uint32_t bytes, uint32_t dt)
{
	uint64_t us = (uint64_t)dt * 1000000ULL / CONFIG_CLOCK_FREQUENCY;
	uint64_t kbps = us ? (uint64_t)bytes * 8000ULL / us : 0;
	printf("%s: %lu pkts, %lu B, %lu us -> %lu.%02lu Mb/s\n", what, (unsigned long)pkts, (unsigned long)bytes,
	       (unsigned long)us, (unsigned long)(kbps / 1000), (unsigned long)((kbps % 1000) / 10));
}

// state shared between the UDP callback and the main loop (replies are sent from the main loop)
static volatile int      sinking;
static uint32_t          sink_pkts, sink_bytes, sink_t0, sink_t1;
static volatile int      pend_ctrl;      // 1 = RXSTAT reply, 2 = TX blast
static uint32_t          peer_ip;
static uint16_t          peer_port;
static uint32_t          tx_size, tx_count;
static volatile uint32_t echo_len;
static uint16_t          echo_port;
static uint32_t          echo_ip;
static uint8_t           echo_buf[1472];

static void rx(uint32_t src_ip, uint16_t src_port, uint16_t dst_port, void *data, uint32_t length)
{
	if (dst_port == P_SINK) {
		if (sinking) {
			uint32_t t = ticks();
			if (sink_pkts == 0)
				sink_t0 = t;
			sink_t1 = t;
			sink_pkts++;
			sink_bytes += length;
		}
	} else if (dst_port == P_ECHO) {
		if (length > sizeof(echo_buf))
			length = sizeof(echo_buf);
		memcpy(echo_buf, data, length);
		echo_ip = src_ip; echo_port = src_port; echo_len = length;
	} else if (dst_port == P_CTRL) {
		char cmd[32];
		uint32_t n = length < sizeof(cmd) - 1 ? length : sizeof(cmd) - 1;
		memcpy(cmd, data, n); cmd[n] = 0;
		peer_ip = src_ip; peer_port = src_port;
		if (strncmp(cmd, "RXEND", 5) == 0) {
			sinking = 0; pend_ctrl = 1;
		} else if (strncmp(cmd, "RX", 2) == 0) {
			sink_pkts = sink_bytes = sink_t0 = sink_t1 = 0; sinking = 1;
		} else if (strncmp(cmd, "TX ", 3) == 0) {
			char *e;
			tx_size  = strtoul(cmd + 3, &e, 10);
			tx_count = strtoul(e, NULL, 10);
			if (tx_size > 1472) tx_size = 1472;
			if (tx_size < 4)    tx_size = 4;
			pend_ctrl = 2;
		}
	}
}

// "<tag> <a> <b> <c>" without sprintf (not in the LiteX libc)
static char *put_u32(char *p, uint32_t v)
{
	char t[11]; int n = 0;
	do { t[n++] = '0' + v % 10; v /= 10; } while (v);
	*p++ = ' ';
	while (n) *p++ = t[--n];
	return p;
}

static void fmt3(char *out, const char *tag, uint32_t a, uint32_t b, uint32_t c)
{
	char *p = out;
	while (*tag) *p++ = *tag++;
	p = put_u32(p, a); p = put_u32(p, b); p = put_u32(p, c);
	*p = 0;
}

static void reply(const char *s)
{
	if (!udp_arp_resolve(peer_ip))
		return;
	uint32_t n = strlen(s);
	memcpy(udp_get_tx_buffer(), s, n);
	udp_send(P_CTRL, peer_port, n);
}

int main(void)
{
	// Interrupts stay off (as the BIOS leaves them at the jump): polled UART and polled ethmac.
	uart_init();
	tick_init();
	printf("\n\nULX5M-GS speedtest (TASK-5033) - CPU port %d.%d.%d.%d, UDP ctrl %d sink %d echo %d, %d MHz\n",
	       LOCALIP1, LOCALIP2, LOCALIP3, LOCALIP4, P_CTRL, P_SINK, P_ECHO, CONFIG_CLOCK_FREQUENCY / 1000000);
	udp_start(my_mac, MY_IP);
	udp_set_callback(rx);
#ifdef SPEEDTEST_DEBUG
	printf("dbg: reader ready %lu, writer pending %lu, timer en %lu\n", (unsigned long)ethmac_sram_reader_ready_read(),
	       (unsigned long)ethmac_sram_writer_ev_pending_read(), (unsigned long)timer0_en_read());
	{
		int r = udp_arp_resolve(IPTOINT(REMOTEIP1, REMOTEIP2, REMOTEIP3, REMOTEIP4));
		printf("dbg: ARP -> %d, writer pending %lu, reader ready %lu\n", r,
		       (unsigned long)ethmac_sram_writer_ev_pending_read(), (unsigned long)ethmac_sram_reader_ready_read());
	}
#endif
	printf("ready (run on the Pi: ~/FPGA/eth_speedtest.sh)\n");

	char msg[64];
	uint32_t dbg_frames = 0, dbg_cb = 0, dbg_t = ticks();
	while (1) {
#ifdef SPEEDTEST_DEBUG
		if (ethmac_sram_writer_ev_pending_read() & ETHMAC_EV_SRAM_WRITER)
			dbg_frames++;
		if (ticks() - dbg_t > 2*CONFIG_CLOCK_FREQUENCY) {
			dbg_t = ticks();
			printf("dbg: frames %lu cb %lu errors %lu slot %lu len %lu\n", (unsigned long)dbg_frames,
			       (unsigned long)dbg_cb, (unsigned long)ethmac_sram_writer_errors_read(),
			       (unsigned long)ethmac_sram_writer_slot_read(), (unsigned long)ethmac_sram_writer_length_read());
		}
		dbg_cb = sink_pkts + echo_ip;
#endif
		udp_service();
		if (echo_len) {
			uint32_t n = echo_len;
			if (udp_arp_resolve(echo_ip)) {
				memcpy(udp_get_tx_buffer(), echo_buf, n);
				udp_send(P_ECHO, echo_port, n);
			}
			echo_len = 0;
		}
		if (pend_ctrl == 1) {
			pend_ctrl = 0;
			print_rate("RX (Pi -> board)", sink_pkts, sink_bytes, sink_t1 - sink_t0);
			fmt3(msg, "RXSTAT", sink_pkts, sink_bytes, sink_t1 - sink_t0);
			reply(msg);
		} else if (pend_ctrl == 2) {
			pend_ctrl = 0;
			uint32_t i, t0, t1;
			if (!udp_arp_resolve(peer_ip))
				continue;
			t0 = ticks();
			for (i = 0; i < tx_count; i++) {
				uint8_t *p = udp_get_tx_buffer();
				p[0] = i >> 24; p[1] = i >> 16; p[2] = i >> 8; p[3] = i;   // sequence number
				udp_send(P_SINK, peer_port, tx_size);
			}
			t1 = ticks();
			print_rate("TX (board -> Pi)", tx_count, tx_count * tx_size, t1 - t0);
			fmt3(msg, "TXDONE", tx_count, tx_count * tx_size, t1 - t0);
			reply(msg);
		}
	}
	return 0;
}
