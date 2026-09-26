# DOOM (smunaut/doom_riscv 02b0d80 engine + this Linux platform layer) as a static rv32im/ilp32 Linux ELF,
# built with the bare-metal xPack riscv-none-elf-gcc + newlib and raw syscalls (sys_linux.c). TASK-5040.
#   make DOOMSRC=~/.tmp/doom_riscv/src    ->  doom (install as /usr/bin/doom, WAD in /usr/share/doom/doom1.wad)
CROSS   ?= riscv-none-elf-
DOOMSRC ?= $(HOME)/.tmp/doom_riscv/src
CC = $(CROSS)gcc
CFLAGS = -w -O2 -march=rv32im -mabi=ilp32 -ffreestanding -fomit-frame-pointer -std=gnu99 \
         -DNORMALUNIX -I$(DOOMSRC) -I. -include stdint.h
LDFLAGS = -static -nostartfiles -Wl,--gc-sections -Wl,-z,max-page-size=4096 -Wl,-Ttext-segment=0x10000 \
          --specs=nano.specs

include $(DOOMSRC)/sources.mk
SOURCES_doom := $(filter-out d_main.c s_sound.c g_game.c,$(SOURCES_doom))
ARCH = g_game.c d_main.c i_main.c i_net.c i_sound.c i_system.c i_video.c s_sound.c console.c mini-printf.c sys_linux.c

doom: $(addprefix $(DOOMSRC)/,$(SOURCES_doom)) $(ARCH)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $^ -lc -lgcc
	$(CROSS)size $@

csrpeek: csrpeek.c sys_linux.c
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $^ -lc -lgcc

usbhidd: ../usbhidd/usbhidd.c sys_linux.c ../usbhidd/hidkey.h
	$(CC) $(CFLAGS) $(LDFLAGS) -I../usbhidd -o $@ ../usbhidd/usbhidd.c sys_linux.c -lc -lgcc

clean:
	rm -f doom csrpeek usbhidd
.PHONY: clean
