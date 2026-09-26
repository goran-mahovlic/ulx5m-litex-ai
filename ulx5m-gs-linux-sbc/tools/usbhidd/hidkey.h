/* hidkey.h (TASK-5047): USB HID boot keyboard report (8 bytes: modifiers, reserved, 6 key codes) -> bytes for a
 * Linux tty (US layout). Only keys that are new in `cur` (not in `prev`) produce output. Pure, host-testable. */
#ifndef HIDKEY_H
#define HIDKEY_H
#include <stdint.h>

/* key codes 0x04..0x38: unshifted / shifted */
static const char hid_plain[] = "abcdefghijklmnopqrstuvwxyz1234567890\r\033\177\t -=[]\\#;'`,./";
static const char hid_shift[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ!@#$%^&*()\r\033\177\t _+{}|~:\"~<>?";

static int hid_key_bytes(uint8_t mod, uint8_t k, char *o)
{
	int shift = (mod & 0x22) != 0, ctrl = (mod & 0x11) != 0;
	if (k >= 0x04 && k <= 0x38) {
		char c = (shift ? hid_shift : hid_plain)[k - 0x04];
		if (ctrl && ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')))
			c &= 0x1f;
		o[0] = c;
		return 1;
	}
	if (k >= 0x4f && k <= 0x52) {           /* right, left, down, up */
		o[0] = '\033'; o[1] = '['; o[2] = "CDBA"[k - 0x4f];
		return 3;
	}
	return 0;
}

static int hid_in(const uint8_t *r, uint8_t k)
{
	for (int i = 2; i < 8; i++)
		if (r[i] == k)
			return 1;
	return 0;
}

/* returns the number of bytes written to out (<= outlen) */
static int hid_new_keys(const uint8_t *prev, const uint8_t *cur, char *out, int outlen)
{
	int n = 0;
	if (cur[2] == 0x01)                     /* ErrorRollOver: too many keys, report is not valid */
		return 0;
	for (int i = 2; i < 8; i++) {
		uint8_t k = cur[i];
		if (k < 0x04 || hid_in(prev, k) || n + 3 > outlen)
			continue;
		n += hid_key_bytes(cur[0], k, out + n);
	}
	return n;
}
#endif
