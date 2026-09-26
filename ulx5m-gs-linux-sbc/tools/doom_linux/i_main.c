/* i_main.c - DOOM for Linux on the ULX5M-GS (TASK-5040). Usage: doom [-iwad-dir DIR] [-timedemo demo1]
 * The WAD (doom1.wad) is opened relative to the working directory: default /usr/share/doom, else DIR. */
#include <unistd.h>
#include "doomdef.h"
#include "m_argv.h"
#include "d_main.h"

int chdir(const char *p);

int main(int argc, char **argv)
{
	myargc = argc;
	myargv = argv;
	int p = M_CheckParm("-iwad-dir");
	if (chdir(p && p < argc - 1 ? argv[p + 1] : "/usr/share/doom") < 0)
		chdir("/tmp");
	D_DoomMain();
	return 0;
}
