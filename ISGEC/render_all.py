#!/usr/bin/env python3
"""Render all 3 ISGEC/<approach>/out/ overlays + a side-by-side composite."""
import os
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import ezdxf
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from PIL import Image, ImageDraw

ISGEC = Path(__file__).resolve().parent
OUT_DIR = ISGEC / "render"
OUT_DIR.mkdir(exist_ok=True)

APPROACHES = [
    ("A", ISGEC / "A" / "out" / "TP-104 OVERLAY_A.dxf"),
    ("B", ISGEC / "B" / "out" / "TP-104 OVERLAY_B.dxf"),
    ("C", ISGEC / "C" / "out" / "TP-104 OVERLAY_C.dxf"),
]

Y_MIN, Y_MAX = -200000, -140000

for label, dxf_path in APPROACHES:
    if not dxf_path.exists():
        print(f"skip {dxf_path} (missing)")
        continue

    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    def _filter_to_y(entity, y_min=Y_MIN, y_max=Y_MAX):
        try:
            bb = entity.bbox()
            return not (bb.extmax[1] < y_min or bb.extmin[1] > y_max)
        except Exception:
            return True

    fig, ax = plt.subplots(figsize=(24, 16), dpi=100)
    ax.set_facecolor("white")
    ax.set_aspect("equal")
    ax.set_xlim(200000, 320000)
    ax.set_ylim(Y_MIN, Y_MAX)
    ax.grid(True, alpha=0.2, linestyle="--")

    ctx = RenderContext(doc)
    out = MatplotlibBackend(ax)
    Frontend(ctx, out).draw_layout(msp, finalize=True,
                                   filter_func=_filter_to_y)
    ax.set_title(f"Approach {label}: {dxf_path.name}",
                 fontsize=20, pad=12)

    out_path = OUT_DIR / f"ISGEC_{label}.png"
    fig.savefig(str(out_path), bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    print(f"  → {out_path}  ({os.path.getsize(out_path) / 1e6:.2f} MB)")

# Composite
imgs = [Image.open(OUT_DIR / f"ISGEC_{l}.png") for l, _ in APPROACHES]
if imgs:
    w = max(i.width for i in imgs)
    h = max(i.height for i in imgs)
    composite = Image.new("RGB", (w * 3 + 30, h + 50), "white")
    for idx, (lbl, _) in enumerate(APPROACHES):
        composite.paste(imgs[idx], (idx * (w + 15), 30))
    draw = ImageDraw.Draw(composite)
    draw.text((w // 2 - 30, 5), "Approach A", fill="black")
    draw.text((w + 15 + w // 2 - 30, 5), "Approach B", fill="black")
    draw.text((2 * w + 30 + w // 2 - 30, 5), "Approach C", fill="black")
    out_path = OUT_DIR / "isgec_all.png"
    composite.save(out_path, "PNG")
    print(f"\nSaved composite: {out_path}")
