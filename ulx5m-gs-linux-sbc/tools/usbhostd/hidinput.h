/* hidinput.h (TASK-5051): USB HID boot reports -> Linux input events (for /dev/uinput). Pure, host-testable.
 * Key codes are the values of <linux/input-event-codes.h> (KEY_A = 30 ...), indexed by HID usage (keyboard page).
 * SPDX-License-Identifier: BSD-2-Clause */
#ifndef HIDINPUT_H
#define HIDINPUT_H
#include <stdint.h>

#define EV_SYN 0x00
#define EV_KEY 0x01
#define EV_REL 0x02
#define EV_REP 0x14
#define REL_X 0x00
#define REL_Y 0x01
#define REL_WHEEL 0x08
#define BTN_LEFT 0x110
#define BTN_RIGHT 0x111
#define BTN_MIDDLE 0x112

/* event types of the uinput device; EV_REP turns on the input core's soft repeat (250 ms, 33/s), without it a held
 * key types once (measured on the board, TASK-5075) */
static const uint16_t hid_ui_evbits[] = { EV_KEY, EV_REL, EV_REP };

/* HID usage 0x00..0x65 -> Linux key code (0 = none) */
static const uint8_t hid_to_key[0x66] = {
	  0,   0,   0,   0,  30,  48,  46,  32,  18,  33,  34,  35,  23,  36,  37,  38,   /* a..l */
	 50,  49,  24,  25,  16,  19,  31,  20,  22,  47,  17,  45,  21,  44,   2,   3,   /* m..z 1 2 */
	  4,   5,   6,   7,   8,   9,  10,  11,  28,   1,  14,  15,  57,  12,  13,  26,   /* 3..0 Enter Esc BS Tab Space - = [ */
	 27,  43,  43,  39,  40,  41,  51,  52,  53,  58,  59,  60,  61,  62,  63,  64,   /* ] \ # ; ' ` , . / Caps F1..F6 */
	 65,  66,  67,  68,  87,  88,  99,  70, 119, 110, 102, 104, 111, 107, 109, 106,   /* F7..F12 PrtSc ScrLk Pause Ins Home PgUp Del End PgDn Right */
	105, 108, 103,  69,  98,  55,  74,  78,  96,  79,  80,  81,  75,  76,  77,  71,   /* Left Down Up NumLk KP/ KP* KP- KP+ KPEnter KP1..KP7 */
	 72,  73,  82,  83,  86, 127,                                                     /* KP8 KP9 KP0 KP. 102nd Compose */
};
/* modifier bits 0..7: LCtrl LShift LAlt LMeta RCtrl RShift RAlt RMeta */
static const uint8_t hid_mod_key[8] = { 29, 42, 56, 125, 97, 54, 100, 126 };

struct hid_ev { uint16_t type, code; int32_t value; };

static int hid_has(const uint8_t *r, uint8_t k)
{
	for (int i = 2; i < 8; i++)
		if (r[i] == k)
			return 1;
	return 0;
}

/* Key press/release events between two boot keyboard reports, then EV_SYN. Returns the number of events. */
static int hid_kbd_events(const uint8_t *prev, const uint8_t *cur, struct hid_ev *ev, int max)
{
	int n = 0;
	if (cur[2] == 0x01)                     /* ErrorRollOver */
		return 0;
	for (int b = 0; b < 8 && n < max - 1; b++)
		if (((prev[0] ^ cur[0]) >> b) & 1)
			ev[n++] = (struct hid_ev){ EV_KEY, hid_mod_key[b], (cur[0] >> b) & 1 };
	for (int i = 2; i < 8 && n < max - 1; i++)  /* released */
		if (prev[i] >= 4 && prev[i] < 0x66 && hid_to_key[prev[i]] && !hid_has(cur, prev[i]))
			ev[n++] = (struct hid_ev){ EV_KEY, hid_to_key[prev[i]], 0 };
	for (int i = 2; i < 8 && n < max - 1; i++)  /* pressed */
		if (cur[i] >= 4 && cur[i] < 0x66 && hid_to_key[cur[i]] && !hid_has(prev, cur[i]))
			ev[n++] = (struct hid_ev){ EV_KEY, hid_to_key[cur[i]], 1 };
	if (n)
		ev[n++] = (struct hid_ev){ EV_SYN, 0, 0 };
	return n;
}

/* Number of key-down events (modifiers included) in ev[0..n-1]: the board test counts every press (usbhostd -v). */
static int hid_key_downs(const struct hid_ev *ev, int n)
{
	int k = 0;
	for (int i = 0; i < n; i++)
		k += ev[i].type == EV_KEY && ev[i].value == 1 && ev[i].code < BTN_LEFT;
	return k;
}

/* Boot mouse report (buttons, dx, dy[, wheel]) -> events. `prev_btn` holds the last button state. */
static int hid_mouse_events(uint8_t *prev_btn, const uint8_t *r, int len, struct hid_ev *ev)
{
	static const uint16_t btn[3] = { BTN_LEFT, BTN_RIGHT, BTN_MIDDLE };
	int n = 0;
	for (int b = 0; b < 3; b++)
		if (((*prev_btn ^ r[0]) >> b) & 1)
			ev[n++] = (struct hid_ev){ EV_KEY, btn[b], (r[0] >> b) & 1 };
	*prev_btn = r[0];
	if (len > 1 && r[1]) ev[n++] = (struct hid_ev){ EV_REL, REL_X, (int8_t)r[1] };
	if (len > 2 && r[2]) ev[n++] = (struct hid_ev){ EV_REL, REL_Y, (int8_t)r[2] };
	if (len > 3 && r[3]) ev[n++] = (struct hid_ev){ EV_REL, REL_WHEEL, (int8_t)r[3] };
	if (n)
		ev[n++] = (struct hid_ev){ EV_SYN, 0, 0 };
	return n;
}
#endif
