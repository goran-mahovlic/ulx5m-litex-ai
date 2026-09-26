/* usbhostd [-t] [-v] [-x SECS] [CSR_BASE] [TTY] (TASK-5051): USB keyboard (and mouse) through the usb_pnru host controller
 * (gateware/usb_pnru.py) - directly on USB-C J5 or behind the USB2514B hub of the CM4 IO board - into the Linux
 * console, without a kernel USB stack. The stack (usbh.c) runs in this process on the CSRs mapped from /dev/mem;
 * with /dev/uinput (Buildroot kernel, tools/linux/buildroot) keyboard and mouse become real input devices (the
 * VT keyboard handler types into the console, evdev for applications); without it (prebuilt 5.14) key presses
 * are pushed into TTY (default /dev/tty1) with ioctl TIOCSTI, with typematic repeat (500 ms, 30/s), and mouse
 * reports are logged. Same raw-syscall runtime as usbhidd/doom (tools/doom_linux/sys_linux.c).
 * SPDX-License-Identifier: BSD-2-Clause */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include "usbh.h"
#include "hidkey.h"
#include "hidinput.h"

long sys6(long n, long a, long b, long c, long d, long e, long f);
uint32_t sys_ms(void);
#define SYS_ioctl 29
#define SYS_clock_nanosleep_time64 407
#define SYS_ppoll_time64 414
#define TIOCSTI 0x5412
#define SYS_write 64
/* <linux/uinput.h> (not in newlib): ioctl numbers for 'U' */
#define UI_DEV_CREATE  0x5501
#define UI_DEV_SETUP   0x405c5503      /* _IOW('U', 3, struct uinput_setup), 92 bytes */
#define UI_SET_EVBIT   0x40045564
#define UI_SET_KEYBIT  0x40045565
#define UI_SET_RELBIT  0x40045566

static void sleep_ms(int ms)
{
	static int use_ppoll;
	struct { int64_t sec; int64_t nsec; } ts = { ms / 1000, (int64_t)(ms % 1000) * 1000000 };
	if (!use_ppoll) {
		long r = sys6(SYS_clock_nanosleep_time64, 1, 0, (long)&ts, 0, 0, 0);
		if (r == 0 || r == -4)
			return;
		use_ppoll = 1;
	}
	sys6(SYS_ppoll_time64, 0, 0, (long)&ts, 0, 0, 0);
}

struct ctx {
	int tty, ui;                    /* ui: /dev/uinput fd, -1 = TIOCSTI mode */
	int verbose;                    /* -v: log every keyboard/mouse report */
	uint8_t btn;
	uint8_t prev[8];
	char rep[4];
	int nrep;
	uint32_t t_rep;
};

static void push(int tty, const char *s, int n)
{
	for (int i = 0; i < n; i++)
		sys6(SYS_ioctl, tty, TIOCSTI, (long)&s[i], 0, 0, 0);
}

static uint32_t c_now(void *c) { (void)c; return sys_ms(); }
static void c_sleep(void *c, uint32_t ms) { (void)c; sleep_ms(ms); }
static void c_log(void *c, const char *m) { (void)c; printf("%s\n", m); fflush(stdout); }

/* rv32 kernel struct input_event: 32-bit sec/usec (ignored for uinput writes), type, code, value */
static void ui_emit(int ui, const struct hid_ev *ev, int n)
{
	for (int i = 0; i < n; i++) {
		uint32_t e[4] = { 0, 0, ev[i].type | (uint32_t)ev[i].code << 16, (uint32_t)ev[i].value };
		sys6(SYS_write, ui, (long)e, sizeof e, 0, 0, 0);
	}
}

static int ui_open(void)
{
	int ui = open("/dev/uinput", O_WRONLY | O_NONBLOCK);
	if (ui < 0)
		return -1;
	sys6(SYS_ioctl, ui, UI_SET_EVBIT, EV_KEY, 0, 0, 0);
	sys6(SYS_ioctl, ui, UI_SET_EVBIT, EV_REL, 0, 0, 0);
	for (int k = 1; k < 0x80; k++)
		sys6(SYS_ioctl, ui, UI_SET_KEYBIT, k, 0, 0, 0);
	for (int k = 0; k < 8; k++)
		sys6(SYS_ioctl, ui, UI_SET_KEYBIT, hid_mod_key[k], 0, 0, 0);
	for (int k = BTN_LEFT; k <= BTN_MIDDLE; k++)
		sys6(SYS_ioctl, ui, UI_SET_KEYBIT, k, 0, 0, 0);
	sys6(SYS_ioctl, ui, UI_SET_RELBIT, REL_X, 0, 0, 0);
	sys6(SYS_ioctl, ui, UI_SET_RELBIT, REL_Y, 0, 0, 0);
	sys6(SYS_ioctl, ui, UI_SET_RELBIT, REL_WHEEL, 0, 0, 0);
	struct { uint16_t bustype, vendor, product, version; char name[80]; uint32_t ff_effects_max; } su;
	memset(&su, 0, sizeof su);
	su.bustype = 0x03;                                        /* BUS_USB */
	strcpy(su.name, "usb_pnru boot keyboard/mouse");
	if (sys6(SYS_ioctl, ui, UI_DEV_SETUP, (long)&su, 0, 0, 0) < 0 || sys6(SYS_ioctl, ui, UI_DEV_CREATE, 0, 0, 0, 0) < 0) {
		close(ui);
		return -1;
	}
	return ui;
}

static void c_kbd(void *cv, const uint8_t r[8])
{
	struct ctx *c = cv;
	char out[24];
	if (c->verbose && memcmp(c->prev, r, 8)) {
		printf("kbd: %02x %02x %02x %02x %02x %02x %02x %02x\n", r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]);
		fflush(stdout);
	}
	if (c->ui >= 0) {                       /* the kernel does the typematic repeat */
		struct hid_ev ev[20];
		ui_emit(c->ui, ev, hid_kbd_events(c->prev, r, ev, 20));
		memcpy(c->prev, r, 8);
		return;
	}
	int n = hid_new_keys(c->prev, r, out, sizeof out);
	push(c->tty, out, n);
	if (n) {
		c->nrep = n <= 3 ? n : 0;
		memcpy(c->rep, out + n - c->nrep, c->nrep);
		c->t_rep = sys_ms() + 500;
	}
	if (r[2] == 0)
		c->nrep = 0;
	memcpy(c->prev, r, 8);
}

static void c_mouse(void *cv, const uint8_t *r, int len)
{
	struct ctx *c = cv;
	if (c->verbose && c->ui >= 0)
		printf("mouse: buttons %x dx %d dy %d\n", r[0], (int8_t)r[1], len > 2 ? (int8_t)r[2] : 0);
	if (c->ui >= 0) {
		struct hid_ev ev[8];
		ui_emit(c->ui, ev, hid_mouse_events(&c->btn, r, len, ev));
		return;
	}
	printf("mouse: buttons %x dx %d dy %d\n", r[0], (int8_t)r[1], len > 2 ? (int8_t)r[2] : 0);
}

int main(int argc, char **argv)
{
	int force_tty = 0, verbose = 0;
	uint32_t run_s = 0;
	for (; argc > 1 && argv[1][0] == '-'; argc--, argv++) {
		if (strcmp(argv[1], "-t") == 0)
			force_tty = 1;                  /* TIOCSTI even if /dev/uinput exists */
		else if (strcmp(argv[1], "-v") == 0)
			verbose = 1;                    /* log the HID reports */
		else if (strcmp(argv[1], "-x") == 0 && argc > 2) {
			run_s = strtoul(argv[2], 0, 0); /* exit after run_s seconds with statistics (board test) */
			argc--; argv++;
		}
	}
	uint32_t base = argc > 1 ? strtoul(argv[1], 0, 0) : 0xf0003800;
	const char *ttyname = argc > 2 ? argv[2] : "/dev/tty1";
	static struct ctx c;
	static struct usbh h;
	int fd = open("/dev/mem", O_RDWR | O_SYNC);
	if (fd < 0) { printf("usbhostd: open /dev/mem failed\n"); return 1; }
	long m = sys6(222, 0, 4096, 3, 1, fd, base >> 12);     /* mmap2 RW, MAP_SHARED */
	if (m < 0 && m > -4096) { printf("usbhostd: mmap failed %ld\n", m); return 1; }
	c.verbose = verbose;
	c.ui = force_tty ? -1 : ui_open();
	c.tty = c.ui >= 0 ? -1 : open(ttyname, O_RDWR);
	if (c.ui < 0 && c.tty < 0) { printf("usbhostd: open %s failed\n", ttyname); return 1; }
	h.r = (volatile uint32_t *)(m + (base & 0xfff));
	h.now_ms = c_now; h.sleep_ms = c_sleep; h.log = c_log; h.on_kbd = c_kbd; h.on_mouse = c_mouse; h.ctx = &c;
	printf("usbhostd: usb_pnru CSR 0x%08x -> %s\n", (unsigned)base, c.ui >= 0 ? "/dev/uinput" : ttyname);
	usbh_init(&h);
	uint32_t t_start = sys_ms(), loops = 0;
	for (;; loops++) {
		if (run_s && sys_ms() - t_start >= run_s*1000) {
			printf("usbhostd: exit after %u s: %u loops, %u transactions, %u NAK, %u time-outs, %u CRC errors\n",
			       (unsigned)run_s, (unsigned)loops, (unsigned)h.n_txn, (unsigned)h.n_nak, (unsigned)h.n_timeout,
			       (unsigned)h.n_crc);
			return 0;
		}
		usbh_poll(&h);
		if (c.nrep && (int32_t)(sys_ms() - c.t_rep) >= 0) {
			push(c.tty, c.rep, c.nrep);
			c.t_rep += 33;
		}
		sleep_ms(2);
	}
}
