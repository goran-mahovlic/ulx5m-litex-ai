# nextpnr post-route sonde (TASK-4999)

Pokreću se kao `--post-route` skripta nextpnr-himbaechel, na ISTOM json/ccf/seed/fpga_mode kao build (provjeri `cmp` .txt).
Na početak skripte umetni izlaznu putanju (i ciljeve), npr.:

    sed "1i OUT='/tmp/rx_s8.json'" rxpath.py > /tmp/rx8.py
    nextpnr-himbaechel --json <build>.json --vopt ccf=<build>.ccf --vopt fpga_mode=2 --device CCGM1A1 \
        --router router2 --timing-allow-fail --seed 8 --freq 25 --vopt out=/tmp/x.txt --post-route /tmp/rx8.py

- `txcpath.py` (OUTFILE, TARGETS): hoda unatrag od IOSEL-a i ispisuje kašnjenje svake mreže (TXC CLK90 kroz fabric: H2).
- `rxpath.py` (OUT): rasipanje kašnjenja RX takta (`eth_rx_clk`) i RX podataka iz IOSEL-a (seed ovisnost: H13).
- `delays2.py`: sve mreže prema IOSEL-u i taktovi s > 20 odredišta.

Napomena: nextpnr GateMate prijavljuje RAMIO → IOSEL kao 0,000 ns (nije modelirano) i ne radi analizu holda.
