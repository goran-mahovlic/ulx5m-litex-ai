/* usbdiag [CSR_BASE] (TASK-5051): raw register trace of one GET_DESCRIPTOR(device) on the usb_pnru root port, to
 * check the IN buffer read path on the board. Stop usbhostd first (killall usbhostd). Bus reset, SETUP to address
 * 0, then two IN transactions; after each, rx_stat and 12 reads of rx_data are printed as raw words, and the same
 * packet is read once more with rx_stat re-read between the bytes. A correct read path prints
 * 12 01 xx xx 00 00 00 08 (device descriptor, bMaxPacketSize0 8) for the first IN.
 * (This trace found the RX buffer bug of the first board build: 01 00 02 00 00 00 08 00 = every even byte lost.)
 * SPDX-License-Identifier: BSD-2-Clause */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <fcntl.h>
#include "usbh.h"

long sys6(long n, long a, long b, long c, long d, long e, long f);
uint32_t sys_ms(void);

static volatile uint32_t *r;

static void wait_ms(uint32_t ms)
{
	uint32_t t0 = sys_ms();
	while (sys_ms() - t0 < ms)
		;
}

static uint32_t txn(uint32_t tok, const uint8_t *out, int len)
{
	uint32_t s, t0;
	r[R_CTRL] = CTL_XCVR(1) | CTL_TERMSEL | CTL_DP_PULLD | CTL_DN_PULLD | CTL_SOF_EN | CTL_TX_FLSH;
	for (int i = 0; i < len; i++)
		r[R_TX_DATA] = out[i];
	r[R_TX_LEN] = len;
	r[R_TOKEN] = tok;
	t0 = sys_ms();
	do
		s = r[R_RX_STAT];
	while (((s & RX_QUEUED) || !(s & RX_IDLE)) && sys_ms() - t0 < 50);
	return s;
}

static void dump_in(const char *what)
{
	uint32_t s = r[R_RX_STAT], v[12];
	for (int i = 0; i < 12; i++)
		v[i] = r[R_RX_DATA];
	printf("%s: rx_stat %08x (len %u resp %02x%s%s)\n  rx_data x12:", what, (unsigned)s, (unsigned)(s & 0xff),
	       (unsigned)((s >> 16) & 0xff), s & RX_TIMEOUT ? " timeout" : "", s & RX_CRCERR ? " crc" : "");
	for (int i = 0; i < 12; i++)
		printf(" %08x", (unsigned)v[i]);
	printf("\n");
}

int main(int argc, char **argv)
{
	uint32_t base = argc > 1 ? strtoul(argv[1], 0, 0) : 0xf0003800, s;
	static const uint8_t getdesc[8] = {0x80, 6, 0, 1, 0, 0, 18, 0};
	int fd = open("/dev/mem", O_RDWR | O_SYNC);
	if (fd < 0) { printf("open /dev/mem failed\n"); return 1; }
	long m = sys6(222, 0, 4096, 3, 1, fd, base >> 12);
	if (m < 0 && m > -4096) { printf("mmap failed %ld\n", m); return 1; }
	r = (volatile uint32_t *)(m + (base & 0xfff));

	printf("stat %08x ctrl %08x frame %08x\n", (unsigned)r[R_STAT], (unsigned)r[R_CTRL], (unsigned)r[R_FRAME]);
	r[R_CTRL] = CTL_OPMODE2 | CTL_DP_PULLD | CTL_DN_PULLD;                 /* bus reset */
	wait_ms(50);
	r[R_CTRL] = CTL_XCVR(1) | CTL_TERMSEL | CTL_DP_PULLD | CTL_DN_PULLD | CTL_SOF_EN;
	wait_ms(30);
	s = txn(TKN_START | TKN_HS | (uint32_t)PID_SETUP << 16, getdesc, 8);
	printf("SETUP: rx_stat %08x (resp %02x)\n", (unsigned)s, (unsigned)((s >> 16) & 0xff));
	for (int k = 0; k < 2; k++) {
		int tries = 0;
		do
			s = txn(TKN_START | TKN_HS | TKN_IN | (k == 0 ? TKN_DATA1 : 0) | (uint32_t)PID_IN << 16, 0, 0);
		while (((s >> 16) & 0xff) == PID_NAK && ++tries < 50);
		dump_in(k == 0 ? "IN#1 (DATA1)" : "IN#2 (DATA0)");
	}
	/* one more IN, bytes read one at a time with a status read in between */
	s = txn(TKN_START | TKN_HS | TKN_IN | TKN_DATA1 | (uint32_t)PID_IN << 16, 0, 0);
	printf("IN#3: rx_stat %08x, rx_data with rx_stat between:", (unsigned)s);
	for (int i = 0; i < 8; i++) {
		uint32_t d = r[R_RX_DATA];
		(void)r[R_RX_STAT];
		printf(" %02x", (unsigned)(d & 0xff));
	}
	printf("\n");
	return 0;
}
