#!/usr/bin/env python3
"""Render each overlay with its actual DXF colors AND show the wrapper
INSERT markers in a contrasting color so you can see what's wrapped.

This uses ezdxf's matplotlib backend (which respects ACI colors) and
draws big X-markers on the wrapper INSERTs at modelspace so you can
visually distinguish Approach A (no wrappers) vs B (2) vs C (1).
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import ezdxf
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

ISGEC = Path(__file__).resolve().parent
OUT_DIR = ISGEC / "render"

APPROACHES = [
    ("A", ISGEC / "A" / "out" / "TP-104 OVERLAY_A.dxf"),
    ("B", ISGEC / "B" / "out" / "TP-104 OVERLAY_B.dxf"),
    ("C", ISGEC / "C" / "out" / "TP-104 OVERLAY_C.dxf"),
]

Y_MIN, Y_MAX = -200000, -140000

def _filter_to_y(entity, y_min=Y_MIN, y_max=Y_MAX):
    try:
        bb = entity.bbox()
        return not (bb.extmax[1] < y_min or bb.extmin[1] > y_max)
    except Exception:
        return True


for label, dxf_path in APPROACHES:
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    fig, ax = plt.subplots(figsize=(20, 14), dpi=100)
    ax.set_facecolor("white")
    ax.set_aspect("equal")
    ax.set_xlim(200000, 320000)
    ax.set_ylim(Y_MIN, Y_MAX)

    # Render with actual DXF colors (ezdxf backend maps ACI 1→red, ACI 5→blue)
    ctx = RenderContext(doc)
    out = MatplotlibBackend(ax)
    Frontend(ctx, out).draw_layout(
        msp, finalize=True,
        filter_func=_filter_to_y
    )

    # Mark wrapper INSERTs with bright green X
    wrapper_inserts = [e for e in msp
                       if e.dxftype() == "INSERT"
                       and e.dxf.name in ("MECH_DRAWING", "STR_DRAWING", "OVERLAY_DRAWING")]
    for ins in wrapper_inserts:
        x, y = ins.dxf.insert[0], ins.dxf.insert[1]
        # Check if visible in viewbox
        if Y_MIN <= y <= Y_MAX and 200000 <= x <= 320000:
            ax.scatter([x], [y], c="lime", s=600, marker="X",
                       edgecolors="black", linewidths=3, zorder=10)
            ax.annotate(ins.dxf.name, (x, y), xytext=(8, 8),
                        textcoords="offset points", fontsize=10,
                        fontweight="bold", color="green")

    # Count visible STR INSERTs at modelspace for the label
    all_inserts = [e for e in msp if e.dxftype() == "INSERT"]
    other = [i for i in all_inserts if i not in wrapper_inserts]

    ax.set_title(
        f"Approach {label}: {dxf_path.name}\n"
        f"  {len(wrapper_inserts)} wrapper INSERT(s) (green X)"
        f"  +  {len(other)} per-entity STR INSERT(s) loose at modelspace",
        fontsize=14, fontweight="bold")
    ax.set_xlabel("X (DXF units)")
    ax.set_ylabel("Y (DXF units)")
    ax.grid(True, alpha=0.2, linestyle="--")

    out_path = OUT_DIR / f"REAL_{label}.png"
    fig.savefig(str(out_path), bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    print(f"  → {out_path}")

# Composite
from PIL import Image, ImageDraw
imgs = [Image.open(OUT_DIR / f"REAL_{l}.png") for l, _ in APPROACHES]
w = max(i.width for i in imgs)
h = max(i.height for i in imgs)
composite = Image.new("RGB", (w * 3 + 30, h + 60), "white")
for idx, (lbl, _) in enumerate(APPROACHES):
    composite.paste(imgs[idx], (idx * (w + 15), 40))
draw = ImageDraw.Draw(composite)
draw.text((w // 2 - 50, 8), "Approach A: per-entity", fill="black")
draw.text((w + 15 + w // 2 - 50, 8), "Approach B: 2-block", fill="black")
draw.text((2 * w + 30 + w // 2 - 50, 8), "Approach C: 1-block", fill="black")
out_path = OUT_DIR / "real_all.png"
composite.save(out_path, "PNG")
print(f"Saved composite: {out_path}")
