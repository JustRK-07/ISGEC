#!/usr/bin/env python3
"""Combine the 3 overlay PNGs into one side-by-side image for review."""
from PIL import Image
from pathlib import Path

HERE = Path(__file__).resolve().parent
out_dir = HERE / "render"

a = Image.open(out_dir / "OVERLAY_A.png")
b = Image.open(out_dir / "OVERLAY_B.png")
c = Image.open(out_dir / "OVERLAY_C.png")

w = max(a.width, b.width, c.width)
h = max(a.height, b.height, c.height)

composite = Image.new("RGB", (w * 3 + 30, h + 50), "white")
composite.paste(a, (0, 30))
composite.paste(b, (w + 15, 30))
composite.paste(c, (2 * w + 30, 30))

# Add labels with PIL
from PIL import ImageDraw, ImageFont
draw = ImageDraw.Draw(composite)
draw.text((w // 2 - 30, 5), "Approach A", fill="black")
draw.text((w + 15 + w // 2 - 30, 5), "Approach B", fill="black")
draw.text((2 * w + 30 + w // 2 - 30, 5), "Approach C", fill="black")

out_path = out_dir / "all_overlays.png"
composite.save(out_path, "PNG")
print(f"Saved {out_path}")
