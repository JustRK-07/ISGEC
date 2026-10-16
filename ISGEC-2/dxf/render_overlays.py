#!/usr/bin/env python3
"""Render each OVERLAY_*.dxf as a PNG with extent clamping (skip entities with
absurd y values like the corrupt RTR block in MECH).

Outputs:
  render/OVERLAY_A.png
  render/OVERLAY_B.png
  render/OVERLAY_C.png
"""

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import ezdxf
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend


def _filter_to_y(entity, y_min, y_max):
    """Return True if any vertex of entity is inside the y range."""
    try:
        bb = entity.bbox()
        return not (bb.extmax[1] < y_min or bb.extmin[1] > y_max)
    except Exception:
        return True


HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "render"
OUT_DIR.mkdir(exist_ok=True)

OVERLAYS = [
    ("A", HERE / "A_per_entity" / "TP-104 OVERLAY_A.dxf"),
    ("B", HERE / "B_two_block"  / "TP-104 OVERLAY_B.dxf"),
    ("C", HERE / "C_one_block"  / "TP-104 OVERLAY_C.dxf"),
]

# A sane Y range for the TP-104 conveyor; explicitly excludes the
# corrupt RTR block that lives at y≈+1.4M and y≈-1.6M.
Y_MIN, Y_MAX = -200000, -140000

for label, dxf_path in OVERLAYS:
    if not dxf_path.exists():
        print(f"skip {dxf_path} (missing)")
        continue

    print(f"Rendering {label} from {dxf_path.name} ...")
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    fig, ax = plt.subplots(figsize=(24, 16), dpi=100)
    ax.set_facecolor("white")
    ax.set_aspect("equal")
    ax.set_xlim(200000, 320000)
    ax.set_ylim(Y_MIN, Y_MAX)

    ctx = RenderContext(doc)
    out = MatplotlibBackend(ax)
    Frontend(ctx, out).draw_layout(
        msp,
        finalize=True,
        filter_func=lambda e: _filter_to_y(e, Y_MIN, Y_MAX)
    )

    ax.set_title(f"Approach {label}: {dxf_path.name}",
                 fontsize=20, pad=12)
    ax.set_xlabel("X (DXF units, cropped to 200K-320K)")
    ax.set_ylabel("Y (DXF units, cropped to -200K to -140K)")
    ax.grid(True, alpha=0.2, linestyle="--")

    out_path = OUT_DIR / f"OVERLAY_{label}.png"
    fig.savefig(str(out_path), bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)

    print(f"  → {out_path}  ({os.path.getsize(out_path) / 1e6:.2f} MB)")


print(f"\nAll renders in {OUT_DIR}/")
