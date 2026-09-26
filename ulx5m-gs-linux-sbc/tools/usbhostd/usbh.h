/* usbh.h (TASK-5051): USB 1.1 host stack for the usb_pnru CSR block (gateware/usb_pnru.py), portable C.
 * Root port, enumeration, one level of hubs (USB2514B on the CM4 IO board), HID boot keyboard and mouse.
 * Transactions are run one at a time and polled; the OS layer (usbhostd.c, or the host test) supplies the
 * register block, a millisecond clock and the HID callbacks.
 *
 * CSR block (32-bit words, csr.csv usb_pnru_*): the word offsets below are fixed by the gateware when it is
 * built with_events=False (target_soc.py); the base address comes from the device tree (usbhost@<base>).
 */
#ifndef USBH_H
#define USBH_H
#include <stdint.h>

enum { R_CTRL, R_STAT, R_FRAME, R_TX_LEN, R_TOKEN, R_RX_STAT, R_TX_DATA, R_RX_DATA, R_NREGS };

#define CTL_SOF_EN   0x0001
#define CTL_OPMODE2  0x0004
#define CTL_XCVR(x)  ((x) << 3)       /* 1 FS, 2 LS, 3 LS behind a FS hub (PRE) */
#define CTL_TERMSEL  0x0020
#define CTL_DP_PULLD 0x0040
#define CTL_DN_PULLD 0x0080
#define CTL_TX_FLSH  0x0100

#define STAT_DP      0x1
#define STAT_DN      0x2

#define TKN_START    0x80000000u
#define TKN_IN       0x40000000u
#define TKN_HS       0x20000000u
#define TKN_DATA1    0x10000000u

#define RX_QUEUED    0x80000000u
#define RX_CRCERR    0x40000000u
#define RX_TIMEOUT   0x20000000u
#define RX_IDLE      0x10000000u

#define PID_OUT   0xe1
#define PID_IN    0x69
#define PID_SETUP 0x2d
#define PID_DATA0 0xc3
#define PID_DATA1 0x4b
#define PID_ACK   0xd2
#define PID_NAK   0x5a
#define PID_STALL 0x1e

enum usbh_speed { SPEED_NONE, SPEED_FS, SPEED_LS, SPEED_LS_HUB };

/* results of a transaction / transfer (negative: error) */
enum { USBH_OK = 0, USBH_NAK = -1, USBH_STALL = -2, USBH_TIMEOUT = -3, USBH_CRC = -4, USBH_TOGGLE = -5,
       USBH_ERR = -6, USBH_HW = -7 };

#define USBH_MAX_DEV 8

struct usbh_dev {
	uint8_t  used, addr, speed, ep0_size;
	uint8_t  parent, port;          /* hub device index + 1 (0 = root port), hub port number */
	uint8_t  cls;                   /* interface class: 3 HID, 9 hub */
	/* HID boot interfaces */
	uint8_t  kbd_ep, kbd_toggle, kbd_iface, mse_ep, mse_toggle, mse_iface;
	uint8_t  kbd_last[8];
	/* hub */
	uint8_t  nports, pwr_ms;
	uint8_t  child[8];              /* device index + 1 per port (1..7) */
	uint32_t next_ms;               /* next poll time */
};

struct usbh {
	volatile uint32_t *r;           /* CSR block */
	uint32_t (*now_ms)(void *ctx);
	void     (*sleep_ms)(void *ctx, uint32_t ms);
	void     (*on_kbd)(void *ctx, const uint8_t report[8]);
	void     (*on_mouse)(void *ctx, const uint8_t *report, int len);
	void     (*log)(void *ctx, const char *msg);
	void     *ctx;
	/* state */
	uint8_t  root_speed;            /* SPEED_NONE until a device is enumerated on the root port */
	uint8_t  root_dev;              /* device index + 1 */
	uint8_t  next_addr;
	uint32_t root_seen_ms;          /* start of the current stable line state */
	uint32_t root_last;
	struct usbh_dev dev[USBH_MAX_DEV];
	/* statistics */
	uint32_t n_txn, n_nak, n_timeout, n_crc;
};

/* Register access; the host test (test_usbh.c) replaces these with its register model. */
#ifndef USBH_RD
#define USBH_RD(h, i)    ((h)->r[i])
#define USBH_WR(h, i, v) ((h)->r[i] = (v))
#endif

void usbh_init(struct usbh *h);
/* Call every 1..10 ms. Handles connect/disconnect, enumeration, hub ports and HID polling. */
void usbh_poll(struct usbh *h);

/* Lower layers, exported for tests. */
int usbh_txn(struct usbh *h, struct usbh_dev *d, uint8_t pid, uint8_t ep, int data1, const uint8_t *out, int len,
             uint8_t *in, int maxlen);
int usbh_control(struct usbh *h, struct usbh_dev *d, uint8_t type, uint8_t req, uint16_t val, uint16_t idx,
                 uint16_t len, uint8_t *data);
#endif
