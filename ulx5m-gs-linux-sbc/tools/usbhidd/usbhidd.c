/* usbhidd [CSR_BASE] [TTY] (TASK-5047): USB keyboard -> Linux console without a kernel USB stack.
 * Polls the usb_hid CSRs of the ULX5M-GS SoC (gateware/usb_hid.py, csr.csv: usb_hid_report 0xf0003800, 2 words,
 * big ordering; usb_hid_seq +8) through /dev/mem every 8 ms and pushes new key presses into TTY (default /dev/tty1)
 * with ioctl TIOCSTI (kernel 5.14: allowed for root). Typematic repeat: 500 ms delay, 30/s.
 * Same raw-syscall runtime as doom/csrpeek (tools/doom_linux/sys_linux.c). */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include "hidkey.h"

long sys6(long n, long a, long b, long c, long d, long e, long f);
uint32_t sys_ms(void);
#define SYS_ioctl 29
#define SYS_clock_nanosleep_time64 407
#define SYS_ppoll_time64 414
#define TIOCSTI 0x5412

/* never spin: if clock_nanosleep_time64 is refused (e.g. -ENOSYS), fall back to ppoll_time64 with no fds */
static void sleep_ms(int ms)
{
	static int use_ppoll;
	struct { int64_t sec; int64_t nsec; } ts = { 0, (int64_t)ms * 1000000 };
	if (!use_ppoll) {
		long r = sys6(SYS_clock_nanosleep_time64, 1, 0, (long)&ts, 0, 0, 0);
		if (r == 0 || r == -4)      /* 0 or -EINTR */
			return;
		printf("usbhidd: clock_nanosleep_time64 = %ld, using ppoll\n", r);
		use_ppoll = 1;
	}
	sys6(SYS_ppoll_time64, 0, 0, (long)&ts, 0, 0, 0);
}

static void push(int tty, const char *s, int n)
{
	for (int i = 0; i < n; i++)
		sys6(SYS_ioctl, tty, TIOCSTI, (long)&s[i], 0, 0, 0);
}

int main(int argc, char **argv)
{
	uint32_t base = argc > 1 ? strtoul(argv[1], 0, 0) : 0xf0003800;
	const char *ttyname = argc > 2 ? argv[2] : "/dev/tty1";
	int fd = open("/dev/mem", O_RDWR | O_SYNC);
	if (fd < 0) { printf("usbhidd: open /dev/mem failed\n"); return 1; }
	long m = sys6(222, 0, 4096, 3, 1, fd, base >> 12);     /* mmap2 RW, MAP_SHARED */
	if (m < 0 && m > -4096) { printf("usbhidd: mmap failed %ld\n", m); return 1; }
	volatile uint32_t *r = (volatile uint32_t *)(m + (base & 0xfff));
	int tty = open(ttyname, O_RDWR);
	if (tty < 0) { printf("usbhidd: open %s failed\n", ttyname); return 1; }
	printf("usbhidd: CSR 0x%08x -> %s\n", (unsigned)base, ttyname);

	r[4] = 1; sleep_ms(20); r[4] = 0;                       /* ctrl: USB bus reset -> device re-enumerates */
	uint8_t prev[8] = {0}, cur[8];
	uint32_t seq = r[2] & 0xffff, t_rep = 0;
	char out[24], rep[4]; int nrep = 0;
	for (;;) {
		sleep_ms(8);
		uint32_t s1 = r[2] & 0xffff;
		if (s1 != seq) {
			uint32_t hi = r[0], lo = r[1];
			if ((r[2] & 0xffff) != s1)
				continue;                               /* torn read, next poll */
			seq = s1;
			for (int i = 0; i < 4; i++) { cur[i] = lo >> (8*i); cur[4 + i] = hi >> (8*i); }
			int n = hid_new_keys(prev, cur, out, sizeof out);
			push(tty, out, n);
			/* repeat the last newly pressed key while it stays down */
			if (n) { nrep = n <= 3 ? n : 0; memcpy(rep, out + n - nrep, nrep); t_rep = sys_ms() + 500; }
			if (cur[2] == 0) nrep = 0;
			memcpy(prev, cur, 8);
		} else if (nrep && (int32_t)(sys_ms() - t_rep) >= 0) {
			push(tty, rep, nrep);
			t_rep += 33;
		}
	}
}
