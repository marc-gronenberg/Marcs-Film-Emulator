"""Digitizes every graph in SPECS and draws the result over a raster of the page, for checking."""

import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from digitize import curves  # noqa: E402
from specs import SPECS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")

only = sys.argv[1:] if len(sys.argv) > 1 else None
for name, spec in SPECS.items():
    if only and not any(o in name for o in only):
        continue
    cs = curves(os.path.join(ROOT, "pdf", spec["pdf"]), spec)
    fig, ax = plt.subplots(figsize=(6, 3.4), dpi=110)
    for i, c in enumerate(cs):
        ax.plot(c[:, 0], c[:, 1], lw=1.2, label=f"{i}: {len(c)} pts, x {c[:,0].min():.0f}..{c[:,0].max():.0f}")
    ax.set_title(f"{name}: {len(cs)} curves")
    if spec.get("ylog"):
        ax.set_yscale("log")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(os.path.join(ROOT, "check", f"{name}.png"))
    plt.close(fig)
    print(f"{name}: {len(cs)} curves", [f"{len(c)}pts x {c[:,0].min():.2f}..{c[:,0].max():.2f} y {c[:,1].min():.2f}..{c[:,1].max():.2f}" for c in cs])
