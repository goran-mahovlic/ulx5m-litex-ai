#!/usr/bin/env python3
#
#  eyetools -- GateMate FPGA SerDes Eye Scan Toolkit
#
#  Permission to use, copy, modify, and/or distribute this software for any
#  purpose with or without fee is hereby granted, provided that the above
#  copyright notice and this permission notice appear in all copies.
#
#  THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
#  WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
#  MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
#  ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
#  WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
#  ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
#  OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#
#  Visit https://colognechip.com for more information.
#
#  Copyright (C) 2026 Cologne Chip AG <support@colognechip.com>
#  Authors: Patrick Urban
#

import numpy as np

import matplotlib
import matplotlib.pyplot as plt

from matplotlib.colors import LogNorm

class EyeData:
    EYE_CLASSES = ('11S', '00S', '001S', '110S')

    def __init__(self, phases, thresholds, meta=None):
        self.phases = list(phases)
        self.thresholds = list(thresholds)
        self.meta = meta or {}
        n, m = len(self.thresholds), len(self.phases)
        self.correct = {c: [[0] * m for _ in range(n)] for c in self.EYE_CLASSES}
        self.wrong   = {c: [[0] * m for _ in range(n)] for c in self.EYE_CLASSES}
        self.prbs_err_cnt = None

    def add(self, iy, ix, counts):
        for c in self.EYE_CLASSES:
            self.correct[c][iy][ix] += counts[c][0]
            self.wrong[c][iy][ix] += counts[c][1]

    def hits(self, iy, ix, classes=EYE_CLASSES):
        return sum(self.correct[c][iy][ix] + self.wrong[c][iy][ix] for c in classes)

    def errors(self, iy, ix, classes=EYE_CLASSES):
        return sum(self.wrong[c][iy][ix] for c in classes)

    def ber(self, iy, ix, classes=EYE_CLASSES):
        n = self.hits(iy, ix, classes)
        if n == 0:
            return None
        e = self.errors(iy, ix, classes)
        return (1.0 / n) if e == 0 else (e / n)

    def open_area(self, target=1e-3):
        return sum(1 for iy in range(len(self.thresholds)) for ix in range(len(self.phases)) if (self.ber(iy, ix) or 1.0) < target)

    def best_phase_index(self):
        iy = min(range(len(self.thresholds)), key=lambda i: abs(self.thresholds[i]))
        row = [self.ber(iy, ix) or 1.0 for ix in range(len(self.phases))]
        lo = min(row)
        best = [ix for ix, v in enumerate(row) if v <= lo * 1.001]
        return best[len(best) // 2]

class EyePlot:
    def _eye_grid(self, eye, classes):
        z = np.array([[eye.ber(iy, ix, classes)
                    if eye.ber(iy, ix, classes) is not None else np.nan
                    for ix in range(len(eye.phases))]
                    for iy in range(len(eye.thresholds))], dtype=float)
        return z

    def eye_plot(self, eye, classes=EyeData.EYE_CLASSES, codes_per_ui=64.0, mv_per_lsb=None, levels=(1e-2, 1e-3, 1e-4), ax=None, title=None):
        z = self._eye_grid(eye, classes)
        ctr = eye.phases[eye.best_phase_index()]
        x = np.array([(p - ctr) / codes_per_ui for p in eye.phases])
        y = np.array(eye.thresholds, dtype=float) * (mv_per_lsb or 1.0)

        if ax is None:
            _, ax = plt.subplots(figsize=(8, 5))

        vmin = max(np.nanmin(z), 1e-12)
        im = ax.pcolormesh(x, y, z, norm=LogNorm(vmin=vmin, vmax=0.5), shading='nearest', cmap='viridis')

        lv = sorted(v for v in levels if vmin < v < 0.5)
        if lv:
            cs = ax.contour(x, y, z, levels=lv, colors='w', linewidths=0.9)
            ax.clabel(cs, fmt=lambda v: f'{v:.0e}', fontsize=7)

        ax.set_xlabel('monitor phase offset [UI]')
        ax.set_ylabel('threshold [mV]' if mv_per_lsb else 'threshold code [LSB]')

        # raw register codes on the top axis, so a point on the plot can be
        # mapped straight back to RX_MON_PH_OFFSET
        sec = ax.secondary_xaxis('top', functions=(lambda u: u * codes_per_ui + ctr, lambda c: (c - ctr) / codes_per_ui))
        sec.set_xlabel('RX_MON_PH_OFFSET [code]')

        m = eye.meta
        if title is None:
            title = (f"SerDes eye   {m.get('line_rate', 0) / 1e6:.0f} Mbit/s   "
                    f"mon{m.get('monitor', '?')}  sel_tap {m.get('sel_tap', 0):+d}   "
                    f"N={m.get('window', '?')} x{m.get('repeats', 1)}")
        ax.set_title(title, fontsize=10, pad=30)   # clear the secondary axis
        ax.text(0.99, 0.02,
                f"floor {vmin:.1e}   open area @1e-3: {eye.open_area(1e-3)} cells",
                transform=ax.transAxes, ha='right', va='bottom', fontsize=7,
                bbox=dict(boxstyle='round,pad=0.3', fc='w', ec='none', alpha=0.75))

        plt.colorbar(im, ax=ax, label='error probability')
        return ax

    def eye_plot_bathtubs(self, eye, classes=EyeData.EYE_CLASSES, codes_per_ui=64.0, axes=None):
        if axes is None:
            _, axes = plt.subplots(1, 2, figsize=(10, 3.6))

        iy0 = min(range(len(eye.thresholds)), key=lambda i: abs(eye.thresholds[i]))
        ix0 = eye.best_phase_index()
        ctr = eye.phases[ix0]

        axes[0].semilogy([(p - ctr) / codes_per_ui for p in eye.phases], [eye.ber(iy0, ix, classes) for ix in range(len(eye.phases))], marker='.')
        axes[0].set_xlabel('phase [UI]')
        axes[0].set_ylabel('error probability')
        axes[0].set_title(f'horizontal bathtub (threshold {eye.thresholds[iy0]:+d})', fontsize=9)

        axes[1].semilogy(eye.thresholds, [eye.ber(iy, ix0, classes) for iy in range(len(eye.thresholds))], marker='.')
        axes[1].set_xlabel('threshold code [LSB]')
        axes[1].set_ylabel('error probability')
        axes[1].set_title(f'vertical bathtub (phase code {ctr})', fontsize=9)

        for a in axes:
            a.grid(True, which='both', alpha=0.3)
        return axes

    def eye_plot_classes(self, eye, phase_code=None, ax=None):
        if ax is None:
            _, ax = plt.subplots(figsize=(6, 4))
        ix = (eye.phases.index(phase_code) if phase_code is not None else eye.best_phase_index())

        for c in EyeData.EYE_CLASSES:
            frac = []
            for iy in range(len(eye.thresholds)):
                n = eye.correct[c][iy][ix] + eye.wrong[c][iy][ix]
                if n == 0:
                    frac.append(float('nan'))
                    continue
                f = eye.correct[c][iy][ix] / n
                # express every class as P(sample above threshold)
                frac.append(f if c in ('11S', '001S') else 1.0 - f)
            ax.plot(eye.thresholds, frac, marker='.', label=c)

        ax.set_xlabel('threshold code [LSB]')
        ax.set_ylabel('P(sample above threshold)')
        ax.set_title(f'pattern-conditioned CDFs @ phase {eye.phases[ix]}', fontsize=9)
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
        return ax

    def eye_plot_report(self, eye, classes=EyeData.EYE_CLASSES, codes_per_ui=64.0, mv_per_lsb=None, filename=None, show=False):
        fig = plt.figure(figsize=(13, 8))
        gs = fig.add_gridspec(2, 3)
        self.eye_plot(eye, classes, codes_per_ui, mv_per_lsb, ax=fig.add_subplot(gs[0, :2]))
        self.eye_plot_classes(eye, ax=fig.add_subplot(gs[0, 2]))
        self.eye_plot_bathtubs(eye, classes, codes_per_ui, axes=[fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])])
        ax = fig.add_subplot(gs[1, 2])
        ax.axis('off')
        ax.text(0, 1, '\n'.join(f'{k}: {v}' for k, v in eye.meta.items()), va='top', fontsize=8, family='monospace')
        fig.tight_layout()

        if filename:
            fig.savefig(filename, dpi=140)
        if show:
            plt.show()
        return fig
