/* csrpeek ADDR [N] [INTERVAL_MS COUNT] - read N 32-bit words at physical ADDR through /dev/mem (TASK-5040:
 * FrameBuffer2x diagnostic CSRs on the Linux SoC, there is no busybox devmem). Same raw-syscall runtime as doom. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <fcntl.h>
#include <unistd.h>

long sys6(long n, long a, long b, long c, long d, long e, long f);
uint32_t sys_ms(void);

int main(int argc, char **argv)
{
	if (argc < 2) { printf("usage: csrpeek ADDR [N] [INTERVAL_MS COUNT]\n"); return 1; }
	uint32_t addr = strtoul(argv[1], 0, 0), n = argc > 2 ? strtoul(argv[2], 0, 0) : 1;
	uint32_t iv = argc > 3 ? strtoul(argv[3], 0, 0) : 0, cnt = argc > 4 ? strtoul(argv[4], 0, 0) : 1;
	int fd = open("/dev/mem", O_RDWR | O_SYNC);
	if (fd < 0) { printf("open /dev/mem failed\n"); return 1; }
	long m = sys6(222, 0, 4096, 1, 1, fd, addr >> 12);	/* mmap2: PROT_READ, MAP_SHARED, pgoff */
	if (m < 0 && m > -4096) { printf("mmap failed %ld\n", m); return 1; }
	volatile uint32_t *p = (volatile uint32_t *)(m + (addr & 0xfff));
	for (uint32_t k = 0; k < cnt; k++) {
		uint32_t t0 = sys_ms();
		printf("%u ms:", (unsigned)t0);
		for (uint32_t i = 0; i < n; i++)
			printf(" %08x", (unsigned)p[i]);
		printf("\n");
		while (iv && sys_ms() - t0 < iv) ;
	}
	return 0;
}
