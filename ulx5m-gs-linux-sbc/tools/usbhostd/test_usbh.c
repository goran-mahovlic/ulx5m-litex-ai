/* test_usbh.c (TASK-5051): host test of usbh.c against a transaction-level model of the usb_pnru CSR block and
 * of the USB devices: a FS hub (USB2514B descriptors, 4 ports) and a LS boot keyboard.
 *   cc -O1 -Wall -o test_usbh test_usbh.c && ./test_usbh
 * Checks: enumeration through the hub, PRE mode (xcvrsel 3) for the LS keyboard behind the hub and FS mode for the
 * hub, LS mode (xcvrsel 2) for a keyboard directly on the root port (USB-C J5), typed text, unplug + replug.
 * SPDX-License-Identifier: BSD-2-Clause */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct usbh;
static uint32_t m_rd(struct usbh *h, int i);
static void m_wr(struct usbh *h, int i, uint32_t v);
#define USBH_RD(h, i)    m_rd(h, i)
#define USBH_WR(h, i, v) m_wr(h, i, v)
#include "usbh.c"
#include "hidkey.h"
#include "hidinput.h"

static int fails;
#define CHECK(c, ...) do { if (c) printf("PASS "); else { printf("FAIL "); fails++; } printf(__VA_ARGS__); printf("\n"); } while (0)

/* Model: devices -------------------------------------------------------------------------------------- */

enum { T_HUB, T_KBD };
struct mdev {
	int type, speed, present;       /* speed: SPEED_FS / SPEED_LS */
	int addr, new_addr, config;
	uint8_t setup[8];
	uint8_t in[256]; int in_len, in_pos, in_stage, status_pending;
	int ep0_toggle, ep1_toggle;
	/* hub */
	uint32_t port[5];               /* wPortStatus | wPortChange << 16 */
	struct mdev *child[5];
	/* keyboard: scripted reports */
	const uint8_t (*script)[8]; int nscript, pos; uint32_t start_ms;
	int wrong_mode;                 /* transactions seen with the wrong xcvrsel */
	const uint8_t *devd, *cfg;      /* keyboard: descriptors (0 = LS boot keyboard) */
	int cfg_len, mouse_sent, hidpp_sent;
};

static const uint8_t hub_dev_desc[18] = {18, 1, 0x00, 0x02, 9, 0, 1, 64, 0x24, 0x04, 0x14, 0x25, 0xb3, 0x0b, 0, 0, 0, 1};
static const uint8_t hub_cfg[25] = {9, 2, 25, 0, 1, 1, 0, 0xe0, 1,  9, 4, 0, 0, 1, 9, 0, 0, 0,
                                    7, 5, 0x81, 3, 1, 0, 12};
static const uint8_t hub_desc[9] = {9, 0x29, 4, 0x09, 0, 50, 1, 0, 0xff};
static const uint8_t kbd_dev_desc[18] = {18, 1, 0x10, 0x01, 0, 0, 0, 8, 0x6d, 0x04, 0x1c, 0xc3, 0, 0x01, 1, 2, 0, 1};
static const uint8_t kbd_cfg[34] = {9, 2, 34, 0, 1, 1, 0, 0xa0, 50,  9, 4, 0, 0, 1, 3, 1, 1, 0,
                                    9, 0x21, 0x10, 0x01, 0, 1, 0x22, 63, 0,  7, 5, 0x81, 3, 8, 0, 10};
/* 2.4 GHz keyboard+mouse receiver (dongle): FS, composite - interface 0 boot keyboard EP1, interface 1 boot
 * mouse EP2 (TASK-5051 instruction #83: Goran's wireless set on the USB-C of the Waveshare CM5-IO-BASE-A).
 * Descriptors as read on the board (Logitech 046d:c534, USB_HUB_PNRU.md 7.1.2); the last two bytes of the device
 * descriptor (iSerialNumber, bNumConfigurations) were not in the trace. Interface 1 has a 177-byte report
 * descriptor and a 20-byte EP2: besides the boot mouse it carries 20-byte vendor (HID++ long) reports. */
static const uint8_t dgl_dev_desc[18] = {0x12, 0x01, 0x00, 0x02, 0x00, 0x00, 0x00, 0x08, 0x6d, 0x04, 0x34, 0xc5,
                                         0x01, 0x29, 0x01, 0x02, 0x00, 0x01};
static const uint8_t dgl_cfg[59] = {
	0x09, 0x02, 0x3b, 0x00, 0x02, 0x01, 0x04, 0xa0, 0x31, 0x09, 0x04, 0x00, 0x00, 0x01, 0x03, 0x01, 0x01, 0x00,
	0x09, 0x21, 0x11, 0x01, 0x00, 0x01, 0x22, 0x3b, 0x00, 0x07, 0x05, 0x81, 0x03, 0x08, 0x00, 0x08, 0x09, 0x04,
	0x01, 0x00, 0x01, 0x03, 0x01, 0x02, 0x00, 0x09, 0x21, 0x11, 0x01, 0x00, 0x01, 0x22, 0xb1, 0x00, 0x07, 0x05,
	0x82, 0x03, 0x14, 0x00, 0x02};
/* "hi" + Enter, each key pressed and released */
static const uint8_t kbd_script[][8] = {
	{0, 0, 0x0b}, {0}, {0, 0, 0x0c}, {0}, {0, 0, 0x28}, {0},
};

static uint32_t now;                        /* model time, microseconds */
static struct mdev hub, kbd, root_kbd;
static struct mdev *root;                   /* device on the root port (hub or root_kbd) */
static int xcvr_hub, xcvr_kbd, n_kbd_txn;   /* xcvrsel seen for hub / keyboard transactions */

static void dev_reset(struct mdev *d)
{
	d->addr = d->new_addr = d->config = 0;
	d->in_len = d->in_pos = d->status_pending = 0;
	d->ep1_toggle = 0;
}

/* Find the device for `addr` and check the transceiver mode reaches it: FS device xcvr 1, LS device on the root
 * port xcvr 2, LS device behind the hub xcvr 3 (PRE). */
static struct mdev *route(int addr, int xcvr)
{
	struct mdev *d = 0;
	int behind_hub = 0;
	if (root && root->present && root->addr == addr)
		d = root;
	if (!d && root == &hub)
		for (int p = 1; p <= 4; p++)
			if (hub.child[p] && hub.child[p]->present && (hub.port[p] & PS_ENABLED) && hub.child[p]->addr == addr) {
				d = hub.child[p];
				behind_hub = 1;
			}
	if (!d)
		return 0;
	int need = d->speed == SPEED_FS ? 1 : behind_hub ? 3 : 2;
	if (xcvr != need) {
		d->wrong_mode++;
		return 0;
	}
	return d;
}

static void load_in(struct mdev *d, const void *p, int n)
{
	int want = d->setup[6] | d->setup[7] << 8;
	memcpy(d->in, p, n);
	d->in_len = n < want ? n : want;
	d->in_pos = 0;
}

/* SETUP received: prepare the data stage. Returns 0 = ok, -1 = STALL. */
static int do_setup(struct mdev *d)
{
	uint8_t t = d->setup[0], r = d->setup[1];
	int val = d->setup[2] | d->setup[3] << 8, idx = d->setup[4];
	d->in_len = d->in_pos = 0;
	if (t == 0x80 && r == 6) {
		if (val == 0x0100)
			load_in(d, d->type == T_HUB ? hub_dev_desc : d->devd ? d->devd : kbd_dev_desc, 18);
		else if (val == 0x0200)
			d->type == T_HUB ? load_in(d, hub_cfg, sizeof hub_cfg) : d->cfg ? load_in(d, d->cfg, d->cfg_len)
			                 : load_in(d, kbd_cfg, sizeof kbd_cfg);
		else
			return -1;
		return 0;
	}
	if (t == 0x00 && r == 5) { d->new_addr = val; return 0; }
	if (t == 0x00 && r == 9) { d->config = val; d->ep1_toggle = 0; return 0; }
	if (d->type == T_HUB) {
		if (t == 0xa0 && r == 6 && val == 0x2900) { load_in(d, hub_desc, 9); return 0; }
		if (t == 0x23 && r == 3 && val == HUB_PORT_POWER) { hub.port[idx] |= 0x100; return 0; }
		if (t == 0x23 && r == 3 && val == HUB_PORT_RESET) {
			if (hub.child[idx] && hub.child[idx]->present) {
				dev_reset(hub.child[idx]);
				hub.port[idx] |= PS_ENABLED | PS_C_RESET;
				hub.child[idx]->start_ms = now/1000;
			}
			return 0;
		}
		if (t == 0x23 && r == 1) { hub.port[idx] &= ~(1u << val); return 0; }
		if (t == 0xa3 && r == 0) {
			uint8_t b[4] = { hub.port[idx], hub.port[idx] >> 8, hub.port[idx] >> 16, hub.port[idx] >> 24 };
			load_in(d, b, 4);
			return 0;
		}
		return -1;
	}
	if (t == 0x21 && (r == 0x0b || r == 0x0a)) return 0;      /* SET_PROTOCOL, SET_IDLE */
	return -1;
}

/* Execute one transaction. Returns the response PID (0 = time-out) and fills rx. */
static int transact(int xcvr, int pid, int addr, int ep, int data1, const uint8_t *tx, int txlen, uint8_t *rx,
                    int *rxlen)
{
	struct mdev *d = route(addr, xcvr);
	(void)txlen;
	*rxlen = 0;
	now += 200;                                         /* ~0.2 ms per transaction */
	if (!d)
		return 0;
	if (d == &kbd || d == &root_kbd) { xcvr_kbd = xcvr; n_kbd_txn++; } else xcvr_hub = xcvr;
	if (ep == 0) {
		int in_dir = d->setup[0] & 0x80;
		if (pid == PID_SETUP) {
			memcpy(d->setup, tx, 8);
			if (do_setup(d) < 0) { d->status_pending = -1; return PID_ACK; }  /* STALL in the next stage */
			d->status_pending = 1;
			d->ep0_toggle = 1;
			return PID_ACK;
		}
		if (d->status_pending < 0)
			return PID_STALL;
		if (pid == PID_IN && in_dir && d->in_pos < d->in_len) {     /* data stage */
			int n = d->in_len - d->in_pos, mx = d->type == T_HUB ? 64 : 8;
			if (n > mx) n = mx;
			memcpy(rx, d->in + d->in_pos, n);
			*rxlen = n;
			d->in_pos += n;
			int pidr = d->ep0_toggle ? PID_DATA1 : PID_DATA0;
			d->ep0_toggle ^= 1;
			return pidr;
		}
		if (pid == PID_IN && !in_dir) {                         /* status stage of an OUT request */
			if (d->new_addr) { d->addr = d->new_addr; d->new_addr = 0; }
			*rxlen = 0;
			return PID_DATA1;
		}
		if (pid == PID_OUT && in_dir)                           /* status stage of an IN request */
			return PID_ACK;
		if (pid == PID_OUT)
			return PID_ACK;
		*rxlen = 0;
		return PID_DATA1;                                       /* IN past the end: ZLP */
	}
	if (pid == PID_IN && ep == 1 && d->config && (d == &kbd || d == &root_kbd)) {
		/* one report every 30 ms after 300 ms */
		uint32_t t = now/1000 - d->start_ms;
		if (d->pos < d->nscript && t > 300 + 30u*d->pos) {
			memcpy(rx, d->script[d->pos], 8);
			*rxlen = 8;
			int pidr = d->ep1_toggle ? PID_DATA1 : PID_DATA0;
			if ((data1 != 0) == (d->ep1_toggle != 0)) d->pos++;   /* host ACKs a fresh packet */
			d->ep1_toggle ^= 1;
			return pidr;
		}
		return PID_NAK;
	}
	if (pid == PID_IN && ep == 2 && d->config && d->cfg) {
		/* mouse: one report (left button, dx -2, dy 3) after the keyboard script */
		if (d->mouse_sent || d->pos < d->nscript)
			return PID_NAK;
		if (!d->hidpp_sent) {
			/* a 20-byte vendor report first (HID++ long, report ID 0x11): not a boot mouse report */
			memset(rx, 0, 20);
			rx[0] = 0x11; rx[1] = 0xff; rx[2] = 0x81; rx[3] = 0x02;
			*rxlen = 20;
			d->hidpp_sent = 1;
			return PID_DATA0;
		}
		static const uint8_t m[4] = {0x01, 0xfe, 3, 0};
		memcpy(rx, m, 4);
		*rxlen = 4;
		d->mouse_sent = 1;
		return PID_DATA1;
	}
	if (pid == PID_IN && d == &hub)
		return PID_NAK;
	return PID_STALL;
}

/* Model: CSR block --------------------------------------------------------------------------------------- */

static uint32_t m_ctrl, m_txlen, m_rxstat;
static uint8_t m_tx[64], m_rx[64];
static int m_ntx, m_nrx, m_prx;

static uint32_t m_rd(struct usbh *h, int i)
{
	(void)h;
	now += 1;
	switch (i) {
	case R_STAT: {
		int reset = ((m_ctrl >> 1) & 3) == 2 && ((m_ctrl >> 3) & 3) == 0;
		if (reset || !root || !root->present) return 0;
		return root->speed == SPEED_FS ? STAT_DP : STAT_DN;
	}
	case R_RX_STAT: return m_rxstat;
	case R_RX_DATA: return m_prx < m_nrx ? m_rx[m_prx++] : 0;
	case R_CTRL: return m_ctrl;
	}
	return 0;
}

static void m_wr(struct usbh *h, int i, uint32_t v)
{
	(void)h;
	switch (i) {
	case R_CTRL:
		if (((v >> 1) & 3) == 2 && ((v >> 3) & 3) == 0 && root) {   /* bus reset */
			dev_reset(root);
			root->start_ms = now/1000;
		}
		m_ctrl = v & 0xff;
		if (v & CTL_TX_FLSH) m_ntx = 0;
		break;
	case R_TX_DATA: if (m_ntx < 64) m_tx[m_ntx++] = v; break;
	case R_TX_LEN: m_txlen = v; break;
	case R_TOKEN:
		if (v & TKN_START) {
			int rxlen = 0, xcvr = (m_ctrl >> 3) & 3;
			int pid = transact(xcvr, (v >> 16) & 0xff, (v >> 9) & 0x7f, (v >> 5) & 0xf, (v & TKN_DATA1) != 0,
			                   m_tx, m_txlen, m_rx, &rxlen);
			m_nrx = rxlen; m_prx = 0;
			m_rxstat = RX_IDLE | ((uint32_t)pid << 16) | rxlen | (pid ? 0 : RX_TIMEOUT);
		}
		break;
	}
}

/* OS layer ------------------------------------------------------------------------------------------------ */

static char typed[64];
static int ntyped, verbose, n_mouse, mouse_dx, mouse_dy;
static uint8_t prev_rep[8];

static uint32_t t_now(void *c) { (void)c; return now/1000; }
static void t_sleep(void *c, uint32_t ms) { (void)c; now += ms*1000; }
static void t_log(void *c, const char *m) { (void)c; if (verbose) printf("  %s\n", m); }
static void t_kbd(void *c, const uint8_t r[8])
{
	(void)c;
	char o[24];
	int n = hid_new_keys(prev_rep, r, o, sizeof o);
	for (int i = 0; i < n && ntyped < 63; i++) typed[ntyped++] = o[i];
	typed[ntyped] = 0;
	memcpy(prev_rep, r, 8);
}

static void t_mouse(void *c, const uint8_t *r, int len)
{
	(void)c; (void)len;
	n_mouse++; mouse_dx = (int8_t)r[1]; mouse_dy = (int8_t)r[2];
}

static void run(struct usbh *h, uint32_t ms)
{
	uint32_t end = now + ms*1000;
	while (now < end) {
		usbh_poll(h);
		now += 2000;
	}
}

static void setup_kbd(struct mdev *k, int present)
{
	memset(k, 0, sizeof *k);
	k->type = T_KBD; k->speed = SPEED_LS; k->present = present;
	k->script = kbd_script; k->nscript = sizeof kbd_script/sizeof kbd_script[0];
}

int main(int argc, char **argv)
{
	struct usbh h;
	uint32_t regs[R_NREGS];
	verbose = argc > 1 && argv[1][0] == 'v';

	/* 1: CM4 IO board - FS hub on the root port, LS keyboard on hub port 2 */
	memset(&hub, 0, sizeof hub);
	hub.type = T_HUB; hub.speed = SPEED_FS; hub.present = 1;
	setup_kbd(&kbd, 1);
	hub.child[2] = &kbd;
	hub.port[2] = PS_CONNECTED | PS_C_CONNECTION | PS_LOW_SPEED;
	root = &hub;
	memset(&h, 0, sizeof h);
	h.r = regs; h.now_ms = t_now; h.sleep_ms = t_sleep; h.log = t_log; h.on_kbd = t_kbd;
	usbh_init(&h);
	run(&h, 3000);
	CHECK(hub.addr == 1 && hub.config == 1, "hub enumerated (addr %d, config %d)", hub.addr, hub.config);
	CHECK(kbd.addr == 2 && kbd.config == 1, "LS keyboard behind the hub enumerated (addr %d, config %d)", kbd.addr, kbd.config);
	CHECK(xcvr_hub == 1 && xcvr_kbd == 3, "transceiver modes: hub %d (FS), keyboard %d (PRE)", xcvr_hub, xcvr_kbd);
	CHECK(hub.wrong_mode == 0 && kbd.wrong_mode == 0, "no transaction in a wrong mode (%d, %d)", hub.wrong_mode, kbd.wrong_mode);
	CHECK(strcmp(typed, "hi\r") == 0, "typed \"hi\\r\" through the hub (got %d bytes)", ntyped);

	/* unplug the keyboard, plug it back */
	kbd.present = 0;
	hub.port[2] = PS_C_CONNECTION | 0x100;
	run(&h, 500);
	CHECK(h.dev[1].used == 0, "keyboard removed after unplug");
	setup_kbd(&kbd, 1);
	hub.child[2] = &kbd;
	hub.port[2] = PS_CONNECTED | PS_C_CONNECTION | PS_LOW_SPEED | 0x100;
	ntyped = 0; typed[0] = 0; memset(prev_rep, 0, 8);
	run(&h, 3000);
	CHECK(kbd.addr == 3 && strcmp(typed, "hi\r") == 0, "replugged keyboard: addr %d, typed \"%s\"", kbd.addr, typed);

	/* 2: LS keyboard directly on the root port (USB-C J5) */
	setup_kbd(&root_kbd, 1);
	root = &root_kbd;
	xcvr_kbd = 0; n_kbd_txn = 0;
	memset(&h, 0, sizeof h);
	h.r = regs; h.now_ms = t_now; h.sleep_ms = t_sleep; h.log = t_log; h.on_kbd = t_kbd;
	ntyped = 0; typed[0] = 0; memset(prev_rep, 0, 8);
	usbh_init(&h);
	run(&h, 3000);
	CHECK(root_kbd.addr == 1 && xcvr_kbd == 2 && root_kbd.wrong_mode == 0,
	      "LS keyboard on the root port: addr %d, xcvrsel %d (LS)", root_kbd.addr, xcvr_kbd);
	CHECK(strcmp(typed, "hi\r") == 0, "typed \"hi\\r\" directly (got \"%s\")", typed);
	root_kbd.present = 0;
	run(&h, 100);
	CHECK(h.root_dev == 0, "root port disconnect detected");

	/* 3: FS composite receiver (keyboard + mouse) directly on the root port (USB-C of the Waveshare board) */
	setup_kbd(&root_kbd, 1);
	root_kbd.speed = SPEED_FS; root_kbd.devd = dgl_dev_desc; root_kbd.cfg = dgl_cfg; root_kbd.cfg_len = sizeof dgl_cfg;
	root = &root_kbd;
	xcvr_kbd = 0;
	memset(&h, 0, sizeof h);
	h.r = regs; h.now_ms = t_now; h.sleep_ms = t_sleep; h.log = t_log; h.on_kbd = t_kbd; h.on_mouse = t_mouse;
	ntyped = 0; typed[0] = 0; memset(prev_rep, 0, 8);
	usbh_init(&h);
	run(&h, 3000);
	CHECK(root_kbd.addr == 1 && xcvr_kbd == 1 && root_kbd.wrong_mode == 0,
	      "FS keyboard+mouse receiver on the root port: addr %d, xcvrsel %d (FS)", root_kbd.addr, xcvr_kbd);
	CHECK(h.dev[0].kbd_ep == 1 && h.dev[0].mse_ep == 2, "receiver: keyboard EP%d, mouse EP%d", h.dev[0].kbd_ep, h.dev[0].mse_ep);
	CHECK(strcmp(typed, "hi\r") == 0, "receiver typed \"hi\\r\" (got \"%s\")", typed);
	CHECK(n_mouse == 1 && mouse_dx == -2 && mouse_dy == 3,
	      "receiver: 20-byte vendor report dropped, boot mouse report delivered: %d report(s), dx %d dy %d",
	      n_mouse, mouse_dx, mouse_dy);
	CHECK(root_kbd.hidpp_sent && root_kbd.mouse_sent && h.dev[0].mse_ep == 2,
	      "receiver: mouse EP still polled after the vendor report (EP%d)", h.dev[0].mse_ep);

	/* 4: HID -> Linux input events (uinput path of usbhostd) */
	{
		struct hid_ev ev[16];
		uint8_t r0[8] = {0}, r1[8] = {0x02, 0, 0x0b}, r2[8] = {0x02, 0, 0x0b, 0x0c}, r3[8] = {0};
		int n = hid_kbd_events(r0, r1, ev, 16);   /* LShift + h */
		CHECK(n == 3 && ev[0].code == 42 && ev[0].value == 1 && ev[1].code == 35 && ev[1].value == 1 && ev[2].type == EV_SYN,
		      "uinput: shift+h -> KEY_LEFTSHIFT down, KEY_H down, SYN (%d events)", n);
		n = hid_kbd_events(r1, r2, ev, 16);
		CHECK(n == 2 && ev[0].code == 23 && ev[0].value == 1, "uinput: + i -> KEY_I down only (%d events)", n);
		n = hid_kbd_events(r2, r3, ev, 16);
		CHECK(n == 4 && ev[0].code == 42 && ev[0].value == 0 && ev[1].value == 0 && ev[2].value == 0,
		      "uinput: all released -> 3 key-up + SYN (%d events)", n);
		n = hid_kbd_events(r0, r2, ev, 16);   /* shift + h + i in one report */
		CHECK(hid_key_downs(ev, n) == 3 && hid_key_downs(ev, hid_kbd_events(r2, r3, ev, 16)) == 0,
		      "key counter: 3 key-downs in one report, 0 on release");
		uint8_t btn = 0, m[4] = {0x01, 0xfe, 3, 0};
		n = hid_mouse_events(&btn, m, 4, ev);
		CHECK(n == 4 && ev[0].code == BTN_LEFT && ev[1].code == REL_X && ev[1].value == -2 && ev[2].value == 3,
		      "uinput: mouse left + dx -2 dy 3 (%d events)", n);
	}

	printf("%s: %d failure(s), %u transactions\n", fails ? "FAIL" : "OK", fails, (unsigned)h.n_txn);
	return fails != 0;
}
