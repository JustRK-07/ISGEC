#!/usr/bin/env python3
"""Render the user's working TP-104 OVERLAY.dxf for comparison."""
import os
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import ezdxf
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "render"
dxf_path = HERE / "TP-104 OVERLAY.dxf"

doc = ezdxf.readfile(str(dxf_path))
msp = doc.modelspace()

fig, ax = plt.subplots(figsize=(24, 16), dpi=100)
ax.set_facecolor("white")
ax.set_aspect("equal")
ax.set_xlim(200000, 320000)
ax.set_ylim(-200000, -140000)

ctx = RenderContext(doc)
out = MatplotlibBackend(ax)
Frontend(ctx, out).draw_layout(msp, finalize=True,
    filter_func=lambda e: (e.bbox().extmax[1] < -140000 or e.bbox().extmin[1] > -200000) == False
    if hasattr(e, "bbox") else True)

ax.set_title("TP-104 OVERLAY.dxf (user says mostly correct)", fontsize=20, pad=12)
ax.grid(True, alpha=0.2, linestyle="--")
out_path = OUT_DIR / "OVERLAY_WORKING.png"
fig.savefig(str(out_path), bbox_inches="tight", facecolor="white", edgecolor="none")
plt.close(fig)
print(f"Saved {out_path}")
