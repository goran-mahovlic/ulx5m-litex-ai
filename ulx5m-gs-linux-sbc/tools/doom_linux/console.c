/* console.c - DOOM console on Linux stdout (TASK-5040); interface of smunaut's riscv/console.c */
#include <stdarg.h>
#include <string.h>
#include <unistd.h>
#include "mini-printf.h"

void console_init(void) { }
void console_putchar(char c) { write(1, &c, 1); }
char console_getchar(void) { char c = 0; read(0, &c, 1); return c; }
int console_getchar_nowait(void) { return -1; }	/* no input yet (demo loop / timedemo) */
void console_puts(const char *p) { write(1, p, strlen(p)); }
int console_printf(const char *fmt, ...)
{
	static char buf[128];
	va_list va;
	va_start(va, fmt);
	int l = mini_vsnprintf(buf, sizeof buf, fmt, va);
	va_end(va);
	console_puts(buf);
	return l;
}
