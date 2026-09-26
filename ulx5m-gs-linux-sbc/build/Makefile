# ============================================================================
# LiteX Ethernet (GateMate CCGM1A1 / ULX5M-GS) - build + flashing helpers
# ----------------------------------------------------------------------------
# The bitstream is produced by LiteX (gateware/target_eth.py runs the full open
# toolchain: Yosys -> nextpnr-himbaechel -> gmpack). These targets build it and
# then load/flash the resulting .bit.
#
# Run from THIS build/ directory:
#   make bit     # (re)build via LiteX, then stage the .bit/.txt here
#   make stage   # copy the latest LiteX .bit/.txt from eth/gateware/ here
#   make jtag    # load into FPGA SRAM over JTAG (volatile; lost on power-cycle)
#   make flash   # write to SPI flash@0 over JTAG (-f; persistent)
#   make dfu     # flash over USB-C via the DFU bootloader (dfu-util; see caveat)
#   make detect  # probe the JTAG chain
#   make         # this target list
# ============================================================================

BOARD     := ulx5m-gs
# NAME = LiteX output basename (build/eth/gateware/<NAME>.bit).
NAME      := intergalaktik_ulx5m_gs
SRC       := eth/gateware/$(NAME)
BIT       := $(NAME).bit
TXT       := $(NAME).txt

# The ULX5M-GS on-board programmer is an FT232 (use -c ft232, NOT -b gatemate_evb_jtag).
# oss-cad-suite is not on PATH by default, so source ../env.sh for openFPGALoader/gmpack.
ENV       := ../env.sh
OFL       ?= openFPGALoader
OFL_BOARD := -c ft232
DFU_UTIL  ?= dfu-util
DFU_ALT   ?= 2
LITEX     := python3 ../gateware/target_eth.py --build

.PHONY: all help bit stage jtag flash dfu dfu-list detect clean

all help:
	@echo "LiteX Ethernet flashing helpers (board: $(BOARD), programmer: $(OFL_BOARD)):"
	@echo "  make bit    - LiteX build (Yosys->nextpnr->gmpack) then stage $(BIT) here"
	@echo "  make stage  - copy the latest LiteX .bit/.txt from $(SRC).* into this dir"
	@echo "  make jtag   - load $(BIT) into SRAM over JTAG (volatile, non-destructive)"
	@echo "  make flash  - write $(BIT) to SPI flash@0 over JTAG (-f, persistent)"
	@echo "  make dfu    - flash $(BIT) over USB-C (dfu-util -a $(DFU_ALT)); NON-resident, see note"
	@echo "  make dfu-list / make detect - list DFU devices / probe JTAG chain"
	@echo "  default design: IP 10.10.10.50, UDP echo on port 7000"

# Full rebuild from source via LiteX, then stage the fresh artifacts here.
bit:
	@bash -c 'source $(ENV) >/dev/null 2>&1; $(LITEX)'
	@$(MAKE) --no-print-directory stage

# Copy the LiteX-produced bitstream (+ nextpnr .txt) into this dir under $(BIT)/$(TXT).
stage:
	@test -f $(SRC).bit || { echo "ERROR: $(SRC).bit not found - run 'make bit' first."; exit 1; }
	@cp -f $(SRC).bit $(BIT)
	@cp -f $(SRC).txt $(TXT) 2>/dev/null || true
	@echo "==> staged $(BIT) ($$(du -h $(BIT) | cut -f1))"

# Auto-stage if the local copy is missing.
$(BIT):
	@$(MAKE) --no-print-directory stage

# Volatile SRAM load - non-destructive, lost on power-cycle. Best for first bring-up.
jtag: $(BIT)
	@echo "Loading $(BIT) into SRAM over JTAG ($(OFL_BOARD)) - volatile"
	@bash -c 'source $(ENV) >/dev/null 2>&1; $(OFL) $(OFL_BOARD) --index-chain 0 $(BIT)'

# Persistent install to SPI flash@0 (survives power-cycle). Set DIP to flash/SPI, power-cycle.
flash: $(BIT)
	@echo "Writing $(BIT) to SPI flash@0 ($(OFL_BOARD)) - persistent"
	@bash -c 'source $(ENV) >/dev/null 2>&1; $(OFL) $(OFL_BOARD) --index-chain 0 -f $(BIT)'

# USB-C DFU. WARNING: this is a NON-resident image - DFU-flashing it to flash@0 overwrites
# and removes any resident bootloader (recover over JTAG). Prefer 'make jtag'/'make flash'.
dfu: $(BIT)
	@command -v $(DFU_UTIL) >/dev/null 2>&1 || { echo "ERROR: $(DFU_UTIL) not found."; exit 1; }
	@echo "Flashing $(BIT) over USB-C ($(DFU_UTIL) -a $(DFU_ALT) = flash@0) - NON-resident image"
	@$(DFU_UTIL) -a $(DFU_ALT) -D $(BIT)
	@echo "==> done. Press the board RESET button to boot."

dfu-list:
	@$(DFU_UTIL) -l

detect:
	@bash -c 'source $(ENV) >/dev/null 2>&1; $(OFL) $(OFL_BOARD) --detect'

clean:
	@rm -f $(BIT) $(TXT)
	@echo "removed staged $(BIT) $(TXT) (LiteX build/eth/ untouched)"
