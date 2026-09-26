/* usbh.c (TASK-5051): USB 1.1 host stack on the usb_pnru CSR block, see usbh.h.
 * Written for this project after the structure of PNRU's ucmem firmware (gitlab.com/pnru/usb_host: root port,
 * enum, hub, hid), but blocking and polled from a Linux process instead of a task table on a microcontroller.
 * SPDX-License-Identifier: BSD-2-Clause */
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include "usbh.h"

#define NOW()      h->now_ms(h->ctx)
#define SLEEP(ms)  h->sleep_ms(h->ctx, (ms))

static void say(struct usbh *h, const char *fmt, ...)
{
	char buf[128];
	va_list ap;
	if (!h->log)
		return;
	va_start(ap, fmt);
	vsnprintf(buf, sizeof buf, fmt, ap);
	va_end(ap);
	h->log(h->ctx, buf);
}

static uint32_t ctrl_for(int speed)
{
	int x = speed == SPEED_LS ? 2 : speed == SPEED_LS_HUB ? 3 : 1;
	return CTL_XCVR(x) | CTL_TERMSEL | CTL_DP_PULLD | CTL_DN_PULLD | CTL_SOF_EN;
}

/* Speed of the root port: an LS device directly on the port puts the whole port in LS mode (keep-alives),
 * otherwise FS; LS devices behind a hub use PRE (xcvrsel 3), which also keeps FS SOFs going to the hub. */
static int port_speed(struct usbh *h, struct usbh_dev *d)
{
	(void)h;
	return d->speed;
}

/* One transaction. Returns the number of bytes received (IN), 0 (OUT/SETUP acknowledged) or USBH_*. */
int usbh_txn(struct usbh *h, struct usbh_dev *d, uint8_t pid, uint8_t ep, int data1, const uint8_t *out, int len,
             uint8_t *in, int maxlen)
{
	uint32_t s, t0, tok;
	int i, n, resp;

	USBH_WR(h, R_CTRL, ctrl_for(port_speed(h, d)) | CTL_TX_FLSH);
	for (i = 0; i < len; i++)
		USBH_WR(h, R_TX_DATA, out[i]);
	USBH_WR(h, R_TX_LEN, pid == PID_IN ? 0 : len);
	tok = TKN_START | TKN_HS | ((uint32_t)pid << 16) | ((uint32_t)(d->addr & 0x7f) << 9) | ((uint32_t)(ep & 0xf) << 5);
	if (data1)
		tok |= TKN_DATA1;
	if (pid == PID_IN)
		tok |= TKN_IN;
	USBH_WR(h, R_TOKEN, tok);
	t0 = NOW();
	for (;;) {
		s = USBH_RD(h, R_RX_STAT);
		if (!(s & RX_QUEUED) && (s & RX_IDLE))
			break;
		if (NOW() - t0 > 20)
			return USBH_HW;         /* the engine never finished: clock or gateware problem */
	}
	h->n_txn++;
	if (s & RX_TIMEOUT) {
		h->n_timeout++;
		return USBH_TIMEOUT;
	}
	resp = (s >> 16) & 0xff;
	if (resp == PID_NAK) {
		h->n_nak++;
		return USBH_NAK;
	}
	if (resp == PID_STALL)
		return USBH_STALL;
	if (pid != PID_IN)
		return resp == PID_ACK ? USBH_OK : USBH_ERR;
	if (resp != PID_DATA0 && resp != PID_DATA1)
		return USBH_ERR;
	if (s & RX_CRCERR) {
		h->n_crc++;
		return USBH_CRC;
	}
	if ((resp == PID_DATA1) != (data1 != 0))
		return USBH_TOGGLE;             /* repeated packet (our ACK was lost): the SIE ACKed it, drop the data */
	n = s & 0xff;
	if (n > maxlen)
		n = maxlen;
	for (i = 0; i < n; i++)
		in[i] = USBH_RD(h, R_RX_DATA);
	return n;
}

static int retryable(int r)
{
	return r == USBH_NAK || r == USBH_TIMEOUT || r == USBH_CRC || r == USBH_TOGGLE;
}

/* Control transfer on EP0. Returns the number of data bytes (IN) or 0, or USBH_*. */
int usbh_control(struct usbh *h, struct usbh_dev *d, uint8_t type, uint8_t req, uint16_t val, uint16_t idx,
                 uint16_t len, uint8_t *data)
{
	uint8_t su[8] = { type, req, val & 0xff, val >> 8, idx & 0xff, idx >> 8, len & 0xff, len >> 8 }, zlp[1];
	int r = USBH_ERR, tries, toggle = 1, done = 0, in = type & 0x80;
	uint32_t t0;

	for (tries = 0; tries < 4; tries++) {
		r = usbh_txn(h, d, PID_SETUP, 0, 0, su, 8, 0, 0);
		if (r == USBH_OK)
			break;
	}
	if (r != USBH_OK)
		return r;
	t0 = NOW();
	while (done < len) {
		int chunk = len - done < d->ep0_size ? len - done : d->ep0_size;
		r = in ? usbh_txn(h, d, PID_IN, 0, toggle, 0, 0, data + done, chunk)
		       : usbh_txn(h, d, PID_OUT, 0, toggle, data + done, chunk, 0, 0);
		if (retryable(r) && NOW() - t0 < 500)
			continue;
		if (r < 0)
			return r;
		toggle ^= 1;
		done += in ? r : chunk;
		if (in && r < chunk)
			break;                  /* short packet: end of the data stage */
	}
	t0 = NOW();
	for (;;) {                              /* status stage: opposite direction, DATA1, zero length */
		r = in ? usbh_txn(h, d, PID_OUT, 0, 1, 0, 0, 0, 0) : usbh_txn(h, d, PID_IN, 0, 1, 0, 0, zlp, 0);
		if (r >= 0)
			break;
		if (!retryable(r) || NOW() - t0 >= 500)
			return r;
	}
	return in ? done : 0;
}

/* Devices ------------------------------------------------------------------------------------------------ */

static struct usbh_dev *dev_new(struct usbh *h, int speed, int parent, int port)
{
	for (int i = 0; i < USBH_MAX_DEV; i++) {
		struct usbh_dev *d = &h->dev[i];
		if (!d->used) {
			memset(d, 0, sizeof *d);
			d->used = 1;
			d->speed = speed;
			d->parent = parent;
			d->port = port;
			d->ep0_size = 8;
			return d;
		}
	}
	say(h, "usbh: out of device slots");
	return 0;
}

static int dev_index(struct usbh *h, struct usbh_dev *d)
{
	return (int)(d - h->dev);
}

static void dev_free(struct usbh *h, struct usbh_dev *d)
{
	if (d->cls == 9)
		for (int p = 1; p <= d->nports && p < 8; p++)
			if (d->child[p])
				dev_free(h, &h->dev[d->child[p] - 1]);
	say(h, "usbh: device %d gone", d->addr);
	d->used = 0;
}

static int hub_init(struct usbh *h, struct usbh_dev *d);

static int hid_set_boot(struct usbh *h, struct usbh_dev *d, int iface)
{
	/* SET_PROTOCOL(boot) and SET_IDLE(0); a device may STALL either (optional requests): ignore */
	usbh_control(h, d, 0x21, 0x0b, 0, iface, 0, 0);
	usbh_control(h, d, 0x21, 0x0a, 0, iface, 0, 0);
	return 0;
}

static int enumerate(struct usbh *h, struct usbh_dev *d)
{
	uint8_t buf[256];
	int r, total, cfg, i, cur_cls = 0, cur_sub = 0, cur_proto = 0, cur_if = 0, addr;

	d->addr = 0;
	d->ep0_size = 8;
	r = usbh_control(h, d, 0x80, 6, 0x0100, 0, 8, buf);            /* first 8 bytes: bMaxPacketSize0 */
	if (r < 8) {
		say(h, "usbh: no device descriptor (%d)", r);
		return -1;
	}
	d->ep0_size = buf[7] >= 8 && buf[7] <= 64 ? buf[7] : 8;
	addr = h->next_addr;
	h->next_addr = h->next_addr >= 127 ? 1 : h->next_addr + 1;
	if ((r = usbh_control(h, d, 0x00, 5, addr, 0, 0, 0)) < 0) {
		say(h, "usbh: SET_ADDRESS failed (%d)", r);
		return -1;
	}
	d->addr = addr;
	SLEEP(10);
	if ((r = usbh_control(h, d, 0x80, 6, 0x0100, 0, 18, buf)) < 18) {
		say(h, "usbh: device descriptor (%d)", r);
		return -1;
	}
	say(h, "usbh: addr %d %s VID %04x PID %04x class %d ep0 %d", addr,
	    d->speed == SPEED_FS ? "FS" : d->speed == SPEED_LS ? "LS" : "LS(hub)",
	    buf[8] | buf[9] << 8, buf[10] | buf[11] << 8, buf[4], d->ep0_size);
	if ((r = usbh_control(h, d, 0x80, 6, 0x0200, 0, 9, buf)) < 9)
		return -1;
	total = buf[2] | buf[3] << 8;
	cfg = buf[5];
	if (total > (int)sizeof buf)
		total = sizeof buf;
	if ((r = usbh_control(h, d, 0x80, 6, 0x0200, 0, total, buf)) < 9)
		return -1;
	total = r;
	for (i = 0; i + 2 <= total && buf[i] >= 2; i += buf[i]) {
		uint8_t *p = buf + i;
		if (p[1] == 4 && p[0] >= 9) {                           /* interface */
			cur_if = p[2]; cur_cls = p[5]; cur_sub = p[6]; cur_proto = p[7];
			if (!d->cls && (cur_cls == 3 || cur_cls == 9))
				d->cls = cur_cls;
		} else if (p[1] == 5 && p[0] >= 7 && (p[2] & 0x80) && (p[3] & 3) == 3) {  /* interrupt IN */
			if (cur_cls == 3 && cur_sub == 1 && cur_proto == 1 && !d->kbd_ep) {
				d->kbd_ep = p[2] & 0xf; d->kbd_iface = cur_if;
			}
			if (cur_cls == 3 && cur_sub == 1 && cur_proto == 2 && !d->mse_ep) {
				d->mse_ep = p[2] & 0xf; d->mse_iface = cur_if;
			}
		}
	}
	if ((r = usbh_control(h, d, 0x00, 9, cfg, 0, 0, 0)) < 0) {
		say(h, "usbh: SET_CONFIGURATION failed (%d)", r);
		return -1;
	}
	if (d->cls == 9)
		return hub_init(h, d);
	if (d->kbd_ep) {
		hid_set_boot(h, d, d->kbd_iface);
		say(h, "usbh: boot keyboard, EP%d", d->kbd_ep);
	}
	if (d->mse_ep) {
		hid_set_boot(h, d, d->mse_iface);
		say(h, "usbh: boot mouse, EP%d", d->mse_ep);
	}
	if (!d->kbd_ep && !d->mse_ep)
		say(h, "usbh: no driver for device %d (class %d)", addr, d->cls);
	return 0;
}

/* Hub ------------------------------------------------------------------------------------------------------ */

#define HUB_PORT_POWER   8
#define HUB_PORT_RESET   4
#define HUB_C_CONNECTION 16
#define HUB_C_RESET      20
#define PS_CONNECTED     0x0001
#define PS_ENABLED       0x0002
#define PS_LOW_SPEED     0x0200
#define PS_C_CONNECTION  0x00010000u
#define PS_C_RESET       0x00100000u

static int hub_status(struct usbh *h, struct usbh_dev *d, int port, uint32_t *st)
{
	uint8_t b[4];
	int r = usbh_control(h, d, 0xa3, 0, 0, port, 4, b);
	if (r < 4)
		return r < 0 ? r : USBH_ERR;
	*st = b[0] | b[1] << 8 | (uint32_t)b[2] << 16 | (uint32_t)b[3] << 24;
	return 0;
}

static int hub_init(struct usbh *h, struct usbh_dev *d)
{
	uint8_t b[9];
	int r = usbh_control(h, d, 0xa0, 6, 0x2900, 0, 9, b);
	if (r < 7) {
		say(h, "usbh: hub descriptor (%d)", r);
		return -1;
	}
	d->nports = b[2] > 7 ? 7 : b[2];
	d->pwr_ms = b[5];
	for (int p = 1; p <= d->nports; p++)
		usbh_control(h, d, 0x23, 3, HUB_PORT_POWER, p, 0, 0);
	SLEEP(2*d->pwr_ms + 100);
	say(h, "usbh: hub with %d ports", d->nports);
	d->next_ms = NOW();
	return 0;
}

static void hub_port_attach(struct usbh *h, struct usbh_dev *hub, int p)
{
	uint32_t st = 0, t0;
	struct usbh_dev *c;

	SLEEP(100);                                                      /* connect debounce */
	usbh_control(h, hub, 0x23, 3, HUB_PORT_RESET, p, 0, 0);
	t0 = NOW();
	do {
		SLEEP(10);
		if (hub_status(h, hub, p, &st) < 0)
			return;
	} while (!(st & PS_C_RESET) && NOW() - t0 < 500);
	usbh_control(h, hub, 0x23, 1, HUB_C_RESET, p, 0, 0);
	if (!(st & PS_ENABLED)) {
		say(h, "usbh: hub port %d not enabled after reset (%08x)", p, (unsigned)st);
		return;
	}
	SLEEP(10);                                                       /* reset recovery */
	c = dev_new(h, (st & PS_LOW_SPEED) ? SPEED_LS_HUB : SPEED_FS, dev_index(h, hub) + 1, p);
	if (!c)
		return;
	say(h, "usbh: hub port %d: %s device", p, (st & PS_LOW_SPEED) ? "LS" : "FS");
	if (enumerate(h, c) < 0) {
		c->used = 0;
		hub->next_ms = NOW() + 1000;
		return;
	}
	hub->child[p] = dev_index(h, c) + 1;
}

static void hub_poll(struct usbh *h, struct usbh_dev *d)
{
	for (int p = 1; p <= d->nports; p++) {
		uint32_t st;
		if (hub_status(h, d, p, &st) < 0)
			continue;
		if (st & PS_C_CONNECTION)
			usbh_control(h, d, 0x23, 1, HUB_C_CONNECTION, p, 0, 0);
		if (d->child[p] && !(st & PS_CONNECTED)) {
			dev_free(h, &h->dev[d->child[p] - 1]);
			d->child[p] = 0;
		} else if (!d->child[p] && (st & PS_CONNECTED)) {
			hub_port_attach(h, d, p);
			if (!d->child[p]) {             /* failed: retry this port later */
				if ((int32_t)(d->next_ms - NOW()) < 0)
					d->next_ms = NOW() + 500;
				return;
			}
		}
	}
	d->next_ms = NOW() + 100;
}

/* HID ------------------------------------------------------------------------------------------------------ */

static void hid_poll(struct usbh *h, struct usbh_dev *d)
{
	uint8_t b[8];
	int r;
	if (d->kbd_ep) {
		r = usbh_txn(h, d, PID_IN, d->kbd_ep, d->kbd_toggle, 0, 0, b, 8);
		if (r >= 0) {
			d->kbd_toggle ^= 1;
			if (r >= 3) {
				memset(b + r, 0, 8 - r);
				if (h->on_kbd)
					h->on_kbd(h->ctx, b);
				memcpy(d->kbd_last, b, 8);
			}
		} else if (r == USBH_STALL) {
			say(h, "usbh: keyboard EP stalled");
			d->kbd_ep = 0;
		}
	}
	if (d->mse_ep) {
		r = usbh_txn(h, d, PID_IN, d->mse_ep, d->mse_toggle, 0, 0, b, 8);
		if (r >= 0) {
			d->mse_toggle ^= 1;
			if (r >= 3 && h->on_mouse)
				h->on_mouse(h->ctx, b, r);
		} else if (r == USBH_STALL) {
			say(h, "usbh: mouse EP stalled");
			d->mse_ep = 0;
		}
	}
	d->next_ms = NOW() + 10;
}

/* Root port ------------------------------------------------------------------------------------------------ */

static uint32_t root_idle_ctrl(void)
{
	return CTL_XCVR(1) | CTL_TERMSEL | CTL_DP_PULLD | CTL_DN_PULLD;        /* no SOF, receive */
}

static void root_poll(struct usbh *h)
{
	uint32_t s = USBH_RD(h, R_STAT) & 3, now = NOW();
	struct usbh_dev *d;
	static int se0;

	if (!h->root_dev) {
		if (s != h->root_last) {
			h->root_last = s;
			h->root_seen_ms = now;
			return;
		}
		if ((s != STAT_DP && s != STAT_DN) || (int32_t)(now - h->root_seen_ms) < 100)
			return;                         /* nothing attached, or not stable for 100 ms yet */
		int speed = s == STAT_DP ? SPEED_FS : SPEED_LS;
		say(h, "usbh: root port: %s device", speed == SPEED_FS ? "FS" : "LS");
		USBH_WR(h, R_CTRL, CTL_OPMODE2 | CTL_DP_PULLD | CTL_DN_PULLD);        /* bus reset (SE0) */
		SLEEP(50);
		USBH_WR(h, R_CTRL, ctrl_for(speed));                                  /* SOF / keep-alive on */
		SLEEP(20);
		d = dev_new(h, speed, 0, 0);
		if (!d)
			return;
		h->root_speed = speed;
		if (enumerate(h, d) < 0) {
			d->used = 0;
			h->root_speed = SPEED_NONE;
			USBH_WR(h, R_CTRL, root_idle_ctrl());
			h->root_seen_ms = now + 2000;   /* retry in 2 s */
			return;
		}
		h->root_dev = dev_index(h, d) + 1;
		se0 = 0;
		return;
	}
	/* disconnect: SE0 on three polls in a row (an SOF/EOP is only 2 bit times of SE0) */
	se0 = s == 0 ? se0 + 1 : 0;
	if (se0 >= 3) {
		say(h, "usbh: root port: disconnect");
		dev_free(h, &h->dev[h->root_dev - 1]);
		h->root_dev = 0;
		h->root_speed = SPEED_NONE;
		h->root_last = 0;
		USBH_WR(h, R_CTRL, root_idle_ctrl());
		se0 = 0;
	}
}

void usbh_init(struct usbh *h)
{
	memset(h->dev, 0, sizeof h->dev);
	h->root_dev = 0;
	h->root_speed = SPEED_NONE;
	h->root_last = 0xff;
	h->next_addr = 1;
	USBH_WR(h, R_CTRL, root_idle_ctrl());
}

void usbh_poll(struct usbh *h)
{
	root_poll(h);
	for (int i = 0; i < USBH_MAX_DEV; i++) {
		struct usbh_dev *d = &h->dev[i];
		if (!d->used || !d->addr || (int32_t)(NOW() - d->next_ms) < 0)
			continue;
		if (d->cls == 9)
			hub_poll(h, d);
		else if (d->kbd_ep || d->mse_ep)
			hid_poll(h, d);
	}
}
