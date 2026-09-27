/* reptest [EVDEV] [HOLD_MS] (TASK-5075): autorepeat check on the board without the USB side.
 * 1) EVIOCGREP on EVDEV (default /dev/input/event0 = usbhostd's device): delay/period of the input core's soft repeat
 *    (0/0 or an error = no EV_REP, a held key types once).
 * 2) a second uinput device with the same event types as usbhostd (hid_ui_evbits) holds KEY_A for HOLD_MS (default
 *    2000) - with a working repeat the active VT shows about 1 + (HOLD_MS - 250) / 33 'a' characters.
 * SPDX-License-Identifier: BSD-2-Clause */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include "hidinput.h"

long sys6(long n, long a, long b, long c, long d, long e, long f);
uint32_t sys_ms(void);
#define SYS_ioctl 29
#define SYS_write 64
#define SYS_clock_nanosleep_time64 407
#define EVIOCGREP      0x80084503
#define UI_DEV_CREATE  0x5501
#define UI_DEV_DESTROY 0x5502
#define UI_DEV_SETUP   0x405c5503
#define UI_SET_EVBIT   0x40045564
#define UI_SET_KEYBIT  0x40045565
#define KEY_A 30

static void sleep_ms(int ms)
{
	struct { int64_t sec; int64_t nsec; } ts = { ms / 1000, (int64_t)(ms % 1000) * 1000000 };
	sys6(SYS_clock_nanosleep_time64, 1, 0, (long)&ts, 0, 0, 0);
}

static void emit(int ui, int type, int code, int value)
{
	uint32_t e[4] = { 0, 0, (uint32_t)type | (uint32_t)code << 16, (uint32_t)value };
	sys6(SYS_write, ui, (long)e, sizeof e, 0, 0, 0);
}

int main(int argc, char **argv)
{
	const char *dev = argc > 1 ? argv[1] : "/dev/input/event0";
	int hold = argc > 2 ? atoi(argv[2]) : 2000;
	unsigned rep[2] = { 0, 0 };
	int fd = open(dev, O_RDONLY);
	long r = fd < 0 ? fd : sys6(SYS_ioctl, fd, EVIOCGREP, (long)rep, 0, 0, 0);
	printf("reptest: %s EVIOCGREP rc %ld delay %u ms period %u ms\n", dev, r, rep[0], rep[1]);
	if (fd >= 0)
		close(fd);
	int ui = open("/dev/uinput", O_WRONLY | O_NONBLOCK);
	if (ui < 0) {
		printf("reptest: no /dev/uinput\n");
		return 1;
	}
	for (unsigned i = 0; i < sizeof hid_ui_evbits / sizeof hid_ui_evbits[0]; i++)
		sys6(SYS_ioctl, ui, UI_SET_EVBIT, hid_ui_evbits[i], 0, 0, 0);
	sys6(SYS_ioctl, ui, UI_SET_KEYBIT, KEY_A, 0, 0, 0);
	struct { uint16_t bustype, vendor, product, version; char name[80]; uint32_t ff_effects_max; } su;
	memset(&su, 0, sizeof su);
	su.bustype = 0x06;                                        /* BUS_VIRTUAL */
	strcpy(su.name, "reptest");
	if (sys6(SYS_ioctl, ui, UI_DEV_SETUP, (long)&su, 0, 0, 0) < 0 || sys6(SYS_ioctl, ui, UI_DEV_CREATE, 0, 0, 0, 0) < 0) {
		printf("reptest: uinput setup failed\n");
		return 1;
	}
	sleep_ms(1500);                                           /* let the kbd handler attach */
	uint32_t t0 = sys_ms();
	emit(ui, EV_KEY, KEY_A, 1); emit(ui, EV_SYN, 0, 0);
	sleep_ms(hold);
	emit(ui, EV_KEY, KEY_A, 0); emit(ui, EV_SYN, 0, 0);
	printf("reptest: KEY_A held %u ms (expect ~%d characters)\n", (unsigned)(sys_ms() - t0), 1 + (hold - 250) / 33);
	sleep_ms(500);
	sys6(SYS_ioctl, ui, UI_DEV_DESTROY, 0, 0, 0, 0);
	return 0;
}
