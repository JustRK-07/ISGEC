#!/usr/bin/env python3
"""check_overlap.py — focused overlap verification.

For each approach, this:
  1. Renders the overlay at a manageable size that lets us measure
     red/blue pixel coverage and bbox positions
  2. Identifies red (MECH) and blue (STR) pixel regions
  3. Computes bounding boxes of red and blue
  4. Reports:
     - Whether the blue bbox sits INSIDE the red bbox (i.e., STR lives
       on the MECH structural area, not far away)
     - Pixel-overlap count
     - Distance between red and blue centroids

Notes on rendering scale:
  Approach A preserves original colors — the red/blue test below will
  only see MECH entities that were originally red and STR entities that
  were originally blue. Other entity colors show up in the PNG but
  aren't part of the red/blue mask. For B/C, the test is meaningful
  because those approaches force everything red/blue.

If blue bbox is far from red bbox → alignment is broken.
If blue is OVERLAPPING with red → aligned properly.
"""

from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import ezdxf
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from PIL import Image

ISGEC = Path(__file__).resolve().parent

# Crop to the conveyor area (skip the corrupt RTR block at y=1.4M)
X_MIN, X_MAX = 200000, 320000
Y_MIN, Y_MAX = -200000, -140000

# Render at this many pixels per side (manageable; was 120000x60000 earlier
# but that exceeded available RAM). 4000x2000 is plenty for mask statistics.
W = 4000
H = 2000


def render_overlay(dxf_path, save_path, viewbox_only=True):
    """Render the DXF at W×H pixels cropped to (X_MIN..X_MAX) × (Y_MIN..Y_MAX).
    Preserves actual DXF colors."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    def _in_view(e):
        try:
            bb = e.bbox()
            return not (bb.extmax[0] < X_MIN or bb.extmin[0] > X_MAX or
                        bb.extmax[1] < Y_MIN or bb.extmin[1] > Y_MAX)
        except Exception:
            return True

    dpi = 100
    fig_w_in = W / dpi
    fig_h_in = H / dpi
    fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in), dpi=dpi)
    ax.set_xlim(X_MIN, X_MAX)
    ax.set_ylim(Y_MIN, Y_MAX)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_facecolor("white")

    ctx = RenderContext(doc)
    out = MatplotlibBackend(ax)
    Frontend(ctx, out).draw_layout(msp, finalize=True,
                                   filter_func=_in_view if viewbox_only else None)

    fig.savefig(str(save_path), bbox_inches=None, pad_inches=0,
                facecolor="white")
    plt.close(fig)


def is_blue(rgb):
    """Return True if pixel looks blue (STR is rendered ACI 5 = pure blue)."""
    r, g, b = rgb[:3]
    return b > 100 and b > r + 30 and b > g + 30


def is_red(rgb):
    """Return True if pixel looks red (MECH is rendered ACI 1 = pure red)."""
    r, g, b = rgb[:3]
    return r > 100 and r > b + 30 and r > g + 30


def analyze_png(png_path):
    """Find red/blue bboxes + overlap counts."""
    img = Image.open(png_path).convert("RGB")
    arr = np.array(img)

    red_mask = (
        (arr[..., 0] > 100) & (arr[..., 0] > arr[..., 2] + 30) &
        (arr[..., 0] > arr[..., 1] + 30)
    )
    blue_mask = (
        (arr[..., 2] > 100) & (arr[..., 2] > arr[..., 0] + 30) &
        (arr[..., 2] > arr[..., 1] + 30)
    )

    n_red = red_mask.sum()
    n_blue = blue_mask.sum()
    n_overlap = (red_mask & blue_mask).sum()

    if n_red == 0 or n_blue == 0:
        return None

    red_rows, red_cols = np.where(red_mask)
    blue_rows, blue_cols = np.where(blue_mask)

    red_bbox = (int(red_rows.min()), int(red_cols.min()),
                int(red_rows.max()), int(red_cols.max()))
    blue_bbox = (int(blue_rows.min()), int(blue_cols.min()),
                 int(blue_rows.max()), int(blue_cols.max()))

    red_centroid = (float(red_rows.mean()), float(red_cols.mean()))
    blue_centroid = (float(blue_rows.mean()), float(blue_cols.mean()))

    dist = ((red_centroid[0] - blue_centroid[0]) ** 2
            + (red_centroid[1] - blue_centroid[1]) ** 2) ** 0.5

    inside = (
        red_bbox[0] <= blue_bbox[0] and blue_bbox[2] <= red_bbox[2] and
        red_bbox[1] <= blue_bbox[1] and blue_bbox[3] <= red_bbox[3]
    )

    return {
        "n_red": int(n_red),
        "n_blue": int(n_blue),
        "n_overlap": int(n_overlap),
        "red_bbox": red_bbox,
        "blue_bbox": blue_bbox,
        "dist_px": float(dist),
        "blue_inside_red": bool(inside),
        "img_size": (int(arr.shape[1]), int(arr.shape[0])),
    }


def main():
    RENDER_DIR = ISGEC / "render"
    RENDER_DIR.mkdir(exist_ok=True)

    approaches = [
        ("A", "A_per_entity_overlap.png"),
        ("B", "B_two_block_overlap.png"),
        ("C", "C_one_block_overlap.png"),
    ]

    print("═" * 70)
    print("  OVERLAP VERIFICATION — render with actual colors, analyze")
    print("═" * 70)

    all_ok = True
    for label, png_name in approaches:
        dxf_path = ISGEC / label / "out" / f"TP-104 OVERLAY_{label}.dxf"
        if not dxf_path.exists():
            print(f"\n  ✗ {label}: output missing — run.sh first")
            all_ok = False
            continue

        print(f"\n  Approach {label}:")
        print(f"    Rendering {dxf_path.name} ...")
        png_path = RENDER_DIR / png_name
        render_overlay(dxf_path, png_path)

        print(f"    Analyzing pixel-level overlap ...")
        stats = analyze_png(png_path)
        if stats is None:
            print(f"    ✗ FAIL: no red or blue pixels")
            all_ok = False
            continue

        W_img, H_img = stats["img_size"]
        sx_unit = (X_MAX - X_MIN) / W_img
        sy_unit = (Y_MAX - Y_MIN) / H_img

        red_y1 = Y_MAX - stats["red_bbox"][0] * sy_unit
        red_y2 = Y_MAX - stats["red_bbox"][2] * sy_unit
        red_x1 = X_MIN + stats["red_bbox"][1] * sx_unit
        red_x2 = X_MIN + stats["red_bbox"][3] * sx_unit

        blue_y1 = Y_MAX - stats["blue_bbox"][0] * sy_unit
        blue_y2 = Y_MAX - stats["blue_bbox"][2] * sy_unit
        blue_x1 = X_MIN + stats["blue_bbox"][1] * sx_unit
        blue_x2 = X_MIN + stats["blue_bbox"][3] * sx_unit

        red_cx = (red_x1 + red_x2) / 2
        red_cy = (red_y1 + red_y2) / 2
        blue_cx = (blue_x1 + blue_x2) / 2
        blue_cy = (blue_y1 + blue_y2) / 2
        dist_units = ((red_cx - blue_cx) ** 2
                      + (red_cy - blue_cy) ** 2) ** 0.5

        print(f"    MECH  red pixels:  {stats['n_red']:>8,}")
        print(f"    STR   blue pixels: {stats['n_blue']:>8,}")
        print(f"    Overlap (red+blue same px): {stats['n_overlap']:>8,}")
        print(f"    MECH bbox: X={red_x1:.0f}..{red_x2:.0f}  Y={red_y1:.0f}..{red_y2:.0f}")
        print(f"    STR  bbox: X={blue_x1:.0f}..{blue_x2:.0f}  Y={blue_y1:.0f}..{blue_y2:.0f}")
        print(f"    Centroid distance: {dist_units:.0f} DXF units")
        print(f"    Blue INSIDE red bbox: {'✓ YES' if stats['blue_inside_red'] else '✗ NO'}")

        if not stats["blue_inside_red"]:
            print(f"    ✗ FAIL: blue bbox not inside red bbox")
            all_ok = False
        elif dist_units > 5000:
            print(f"    ✗ FAIL: centroid distance {dist_units:.0f} > 5000 units")
            all_ok = False
        elif stats["n_overlap"] < 1000:
            print(f"    ✗ FAIL: overlap only {stats['n_overlap']} px (need >1000)")
            all_ok = False
        else:
            print(f"    ✓ PASS: STR sits on MECH, beams overlap, distance {dist_units:.0f}u")

    print()
    print("═" * 70)
    if all_ok:
        print("  ✓ ALL APPROACHES OVERLAP PROPERLY")
    else:
        print("  ✗ At least one approach failed overlap check")
    print("═" * 70)
    return 0 if all_ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
