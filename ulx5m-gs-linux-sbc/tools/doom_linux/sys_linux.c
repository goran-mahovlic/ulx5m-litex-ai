/*
 * sys_linux.c - newlib backend for DOOM as a static Linux rv32 (ilp32, soft-float) ELF without a Linux libc
 * (TASK-5040, ULX5M-GS VexRiscv-SMP, kernel 5.14). Same idea as banner/linux-rv32/rt.c: raw ecall syscalls.
 * rv32 Linux has only the generic syscall table + 64-bit time: openat, llseek, brk, clock_gettime64, exit_group.
 * GPL v2+ (as the DOOM port it belongs to).
 */
#include <errno.h>
#include <stdint.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>


#define SYS_getcwd        17
#define SYS_fcntl64       25
#define SYS_ioctl         29
#define SYS_chdir         49
#define SYS_openat        56
#define SYS_close         57
#define SYS_llseek        62
#define SYS_read          63
#define SYS_write         64
#define SYS_exit_group    94
#define SYS_brk          214
#define SYS_mmap2        222
#define SYS_clock_gettime64 403
#define AT_FDCWD        (-100)

long sys6(long n, long a, long b, long c, long d, long e, long f)
{
	register long a0 asm("a0") = a, a1 asm("a1") = b, a2 asm("a2") = c, a3 asm("a3") = d;
	register long a4 asm("a4") = e, a5 asm("a5") = f, a7 asm("a7") = n;
	asm volatile ("ecall" : "+r"(a0) : "r"(a1), "r"(a2), "r"(a3), "r"(a4), "r"(a5), "r"(a7) : "memory");
	return a0;
}
#define sys3(n, a, b, c) sys6(n, (long)(a), (long)(b), (long)(c), 0, 0, 0)

static int ret(long r) { if (r < 0 && r > -4096) { errno = -r; return -1; } return r; }

int _open(const char *path, int flags, int mode) { return ret(sys6(SYS_openat, AT_FDCWD, (long)path, flags, mode, 0, 0)); }
int _close(int fd) { return ret(sys3(SYS_close, fd, 0, 0)); }
int _read(int fd, void *buf, size_t n) { return ret(sys3(SYS_read, fd, buf, n)); }
int _write(int fd, const void *buf, size_t n) { return ret(sys3(SYS_write, fd, buf, n)); }
int _isatty(int fd) { return fd < 3; }
int _kill(int pid, int sig) { errno = EINVAL; return -1; }
int _getpid(void) { return 1; }
void _exit(int code) { sys3(SYS_exit_group, code, 0, 0); for (;;); }
int chdir(const char *p) { return ret(sys3(SYS_chdir, p, 0, 0)); }

off_t _lseek(int fd, off_t off, int whence)
{
	int64_t res;
	long r = sys6(SYS_llseek, fd, (long)((int64_t)off >> 32), (long)off, (long)&res, whence, 0);
	return r < 0 ? ret(r) : (off_t)res;
}

int _fstat(int fd, struct stat *st)
{
	memset(st, 0, sizeof(*st));
	st->st_mode = fd < 3 ? S_IFCHR : S_IFREG;
	return 0;
}

void *mmap_fd(int fd, size_t len)	/* MAP_SHARED, PROT_READ|PROT_WRITE, offset 0 */
{
	long r = sys6(SYS_mmap2, 0, len, 3, 1, fd, 0);
	return (r < 0 && r > -4096) ? NULL : (void *)r;
}

static char *cur_brk;
void *_sbrk(ptrdiff_t inc)
{
	if (!cur_brk)
		cur_brk = (char *)sys3(SYS_brk, 0, 0, 0);
	char *old = cur_brk, *want = cur_brk + inc;
	char *got = (char *)sys3(SYS_brk, want, 0, 0);
	if (got != want) { errno = ENOMEM; return (void *)-1; }
	cur_brk = got;
	return old;
}

/* milliseconds since the first call (CLOCK_MONOTONIC) */
uint32_t sys_ms(void)
{
	struct { int64_t sec; long nsec; long pad; } ts;
	static int64_t t0 = -1;
	sys3(SYS_clock_gettime64, 1, &ts, 0);
	int64_t ms = ts.sec * 1000 + ts.nsec / 1000000;
	if (t0 < 0) t0 = ms;
	return (uint32_t)(ms - t0);
}

int main(int argc, char **argv);
void _start_c(long *sp)
{
	int argc = (int)sp[0];
	char **argv = (char **)(sp + 1);
	extern char __bss_start[], _end[];
	memset(__bss_start, 0, _end - __bss_start);	/* kernel zero-fills, belt and braces */
	_exit(main(argc, argv));
}
asm(".globl _start\n_start:\n  .option push\n  .option norelax\n  la gp, __global_pointer$\n  .option pop\n"
    "  mv a0, sp\n  andi sp, sp, -16\n  call _start_c\n");
