/* host unit test for hidkey.h (TASK-5047): gcc -O2 -o /tmp/x test_hidkey.c && ./x */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include "hidkey.h"

static int fails;
static void expect(const char *name, const uint8_t *prev, const uint8_t *cur, const char *want, int wlen)
{
	char out[64];
	int n = hid_new_keys(prev, cur, out, sizeof out);
	if (n != wlen || memcmp(out, want, wlen)) {
		printf("FAIL %s: got %d bytes [", name, n);
		for (int i = 0; i < n; i++) printf(" %02x", (unsigned char)out[i]);
		printf(" ]\n");
		fails++;
	} else printf("ok   %s\n", name);
}

int main(void)
{
	uint8_t z[8] = {0};
	uint8_t a[8] = {0, 0, 0x04};                 /* 'a' */
	uint8_t A[8] = {0x02, 0, 0x04};              /* left shift + a */
	uint8_t ab[8] = {0, 0, 0x04, 0x05};          /* a held, b pressed */
	uint8_t ent[8] = {0, 0, 0x28};
	uint8_t cc[8] = {0x01, 0, 0x06};             /* ctrl-c */
	uint8_t up[8] = {0, 0, 0x52};
	uint8_t one[8] = {0x20, 0, 0x1e};            /* right shift + 1 = ! */
	uint8_t bs[8] = {0, 0, 0x2a};
	uint8_t roll[8] = {0, 0, 1, 1, 1, 1, 1, 1};  /* ErrorRollOver: ignore */
	uint8_t sp[8] = {0, 0, 0x2c, 0x37};          /* space + '.' */
	expect("a",          z, a, "a", 1);
	expect("held a",     a, a, "", 0);
	expect("shift a",    z, A, "A", 1);
	expect("a held + b", a, ab, "b", 1);
	expect("enter",      z, ent, "\r", 1);
	expect("ctrl-c",     z, cc, "\003", 1);
	expect("up arrow",   z, up, "\033[A", 3);
	expect("shift 1",    z, one, "!", 1);
	expect("backspace",  z, bs, "\177", 1);
	expect("rollover",   z, roll, "", 0);
	expect("space dot",  z, sp, " .", 2);
	printf(fails ? "FAIL %d\n" : "PASS\n", fails);
	return fails != 0;
}
