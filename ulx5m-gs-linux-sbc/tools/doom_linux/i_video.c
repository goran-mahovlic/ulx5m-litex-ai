/*
 * i_video.c - DOOM video on the Linux simple-framebuffer /dev/fb0 of the ULX5M-GS DVI SoC (TASK-5040).
 * fb0 is 320x240 r5g6b5 (shown pixel/line-doubled at 640x480 by the gateware); DOOM's 320x200 8-bit frame is
 * converted through a 256-entry rgb565 palette into lines 20..219. Based on smunaut's riscv/i_video.c (GPL v2+).
 */
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>

#include "doomdef.h"
#include "i_system.h"
#include "v_video.h"
#include "i_video.h"

#define FB_W 320
#define FB_H 240
#define FB_Y0 ((FB_H - SCREENHEIGHT) / 2)

void *mmap_fd(int fd, size_t len);
long sys6(long n, long a, long b, long c, long d, long e, long f);
#define SYS_ioctl	29
#define KDSETMODE	0x4B3A	/* linux/kd.h */
#define KD_TEXT		0
#define KD_GRAPHICS	1

static int tty_fd = -1;

/* fbcon keeps drawing (cursor, kernel messages) into the same fb0: put the VT into graphics mode meanwhile */
static void
vt_mode(int mode)
{
	if (tty_fd < 0)
		tty_fd = open("/dev/tty0", O_RDWR);
	if (tty_fd >= 0)
		sys6(SYS_ioctl, tty_fd, KDSETMODE, mode, 0, 0, 0);
}
uint32_t sys_ms(void);

static uint16_t pal565[256];
static uint16_t *fb;		/* mmap of /dev/fb0, or NULL -> write() */
static int fb_fd = -1;
static uint16_t line[FB_W * SCREENHEIGHT];

void
I_InitGraphics(void)
{
	usegamma = 1;
	vt_mode(KD_GRAPHICS);
	fb_fd = open("/dev/fb0", O_RDWR);
	if (fb_fd < 0)
		I_Error("I_InitGraphics: cannot open /dev/fb0");
	fb = mmap_fd(fb_fd, FB_W * FB_H * 2);
	printf("I_InitGraphics: /dev/fb0 %s\n", fb ? "mmap" : "write()");
	memset(line, 0, sizeof line);
	if (fb)
		memset(fb, 0, FB_W * FB_H * 2);
	else
		for (int i = 0; i < FB_H * FB_W * 2 / sizeof line + 1; i++)
			write(fb_fd, line, sizeof line);
}

void I_ShutdownGraphics(void) { vt_mode(KD_TEXT); }

void
I_SetPalette(byte* palette)
{
	for (int i = 0; i < 256; i++) {
		byte r = gammatable[usegamma][*palette++];
		byte g = gammatable[usegamma][*palette++];
		byte b = gammatable[usegamma][*palette++];
		pal565[i] = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3);
	}
}

void I_UpdateNoBlit(void) { }

void
I_FinishUpdate(void)
{
	const byte *s = screens[0];
	uint32_t *d = fb ? (uint32_t *)(fb + FB_Y0 * FB_W) : (uint32_t *)line;
	for (int i = 0; i < SCREENWIDTH * SCREENHEIGHT; i += 2)
		*d++ = pal565[s[i]] | ((uint32_t)pal565[s[i + 1]] << 16);
	if (!fb) {
		lseek(fb_fd, FB_Y0 * FB_W * 2, SEEK_SET);
		write(fb_fd, line, sizeof line);
	}

	/* FPS: time of 100 frames */
	static int frame_cnt = 0;
	static uint32_t ms_prev = 0;
	if (++frame_cnt == 100) {
		uint32_t ms = sys_ms();
		printf("100 frames in %u ms = %u.%u fps\n", (unsigned)(ms - ms_prev),
		       (unsigned)(100000 / (ms - ms_prev)), (unsigned)(1000000 / (ms - ms_prev) % 10));
		ms_prev = ms;
		frame_cnt = 0;
	}
}

void I_WaitVBL(int count) { }

void
I_ReadScreen(byte* scr)
{
	memcpy(scr, screens[0], SCREENHEIGHT * SCREENWIDTH);
}
