/* test_openflags.c (TASK-5051): newlib open() flags -> Linux generic (rv32) flags, as done by _open in sys_linux.c.
 *   cc -Wall -o test_openflags test_openflags.c && ./test_openflags
 * Board bug: newlib O_NONBLOCK 0x4000 is Linux O_DIRECT, so open("/dev/uinput", O_WRONLY|O_NONBLOCK) returned EINVAL. */
#include <stdio.h>
#include "openflags.h"
static int fails;
#define CHECK(c, ...) do { printf("%s ", (c) ? "PASS" : "FAIL"); printf(__VA_ARGS__); printf("\n"); fails += !(c); } while (0)
int main(void)
{
	/* newlib values: O_RDONLY 0, O_WRONLY 1, O_RDWR 2, O_APPEND 0x8, O_CREAT 0x200, O_TRUNC 0x400, O_EXCL 0x800,
	 * O_SYNC 0x2000, O_NONBLOCK 0x4000, O_NOCTTY 0x8000, O_CLOEXEC 0x40000 */
	CHECK(lx_open_flags(0x0001 | 0x4000) == (01 | 04000), "O_WRONLY|O_NONBLOCK -> 0x%x (not O_DIRECT)", lx_open_flags(0x4001));
	CHECK(lx_open_flags(0x0002 | 0x2000) == (02 | 04010000), "O_RDWR|O_SYNC -> 0x%x", lx_open_flags(0x2002));
	CHECK(lx_open_flags(0x0001 | 0x0200 | 0x0400) == (01 | 0100 | 01000), "O_WRONLY|O_CREAT|O_TRUNC -> 0x%x",
	      lx_open_flags(0x0601));
	CHECK(lx_open_flags(0x0008 | 0x0800 | 0x8000 | 0x40000) == (02000 | 0200 | 0400 | 02000000),
	      "O_APPEND|O_EXCL|O_NOCTTY|O_CLOEXEC -> 0x%x", lx_open_flags(0x48808));
	CHECK(lx_open_flags(0) == 0, "O_RDONLY -> 0");
	printf("%s: %d failure(s)\n", fails ? "FAIL" : "OK", fails);
	return fails != 0;
}
