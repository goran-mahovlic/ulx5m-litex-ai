/* openflags.h (TASK-5051): newlib (riscv-none-elf) open() flags -> Linux asm-generic flags. The two differ above the
 * access mode: newlib O_NONBLOCK 0x4000 is Linux O_DIRECT (a char device open then fails with EINVAL), O_SYNC 0x2000
 * is FASYNC, O_CREAT 0x200 is O_TRUNC. Host test: test_openflags.c. SPDX-License-Identifier: BSD-2-Clause */
#ifndef OPENFLAGS_H
#define OPENFLAGS_H
static int lx_open_flags(int f)
{
	static const struct { int nl, lx; } map[] = {
		{ 0x0008, 02000 },       /* O_APPEND */
		{ 0x0200, 0100 },        /* O_CREAT */
		{ 0x0400, 01000 },       /* O_TRUNC */
		{ 0x0800, 0200 },        /* O_EXCL */
		{ 0x2000, 04010000 },    /* O_SYNC */
		{ 0x4000, 04000 },       /* O_NONBLOCK */
		{ 0x8000, 0400 },        /* O_NOCTTY */
		{ 0x40000, 02000000 },   /* O_CLOEXEC */
		{ 0x200000, 0200000 },   /* O_DIRECTORY */
	};
	int r = f & 3;
	for (unsigned i = 0; i < sizeof map / sizeof map[0]; i++)
		if (f & map[i].nl)
			r |= map[i].lx;
	return r;
}
#endif
