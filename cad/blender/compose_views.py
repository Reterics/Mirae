"""Compose the three marketing views into one sheet (run with the system Python + Pillow).

    python cad/blender/compose_views.py

Reads cad/renders/marketing/{front,side,bottom}.png and layout.json (pixel positions
projected from the Blender cameras), writes views.png. Dimension lines are drawn
between the projected model extremes, so they match the geometry.
"""

import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "renders", "marketing"))
FONT_DIR = r"C:\Windows\Fonts"


def font(name, size):
    try:
        return ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    except OSError:
        return ImageFont.load_default()


def spaced(text):
    return " ".join(text)


def centered(draw, x, y, text, f, fill):
    w = draw.textlength(text, font=f)
    draw.text((x - w / 2, y), text, font=f, fill=fill)
    return w


def dimension(draw, x0, x1, y, text, f, fill):
    x0, x1 = sorted((x0, x1))
    tw = draw.textlength(text, font=f)
    mid = (x0 + x1) / 2
    gap = tw / 2 + 18
    for a, b in ((x0, mid - gap), (mid + gap, x1)):
        draw.line((a, y, b, y), fill=fill, width=2)
    for x in (x0, x1):
        draw.line((x, y - 12, x, y + 12), fill=fill, width=2)
    centered(draw, mid, y - f.size * 0.62, text, f, fill)


def main():
    lay = json.load(open(os.path.join(SRC, "layout.json")))
    panels = [
        Image.open(os.path.join(SRC, n + ".png")).convert("RGB")
        for n in ("front", "side", "bottom")
    ]
    w, h = panels[0].size
    sep = 4
    sheet = Image.new("RGB", (3 * w + 2 * sep, h), (120, 116, 112))
    for i, im in enumerate(panels):
        sheet.paste(im, (i * (w + sep), 0))
    d = ImageDraw.Draw(sheet)
    ink = (236, 232, 226)
    f_lbl, f_dim, f_note, f_small = (
        font("segoeuil.ttf", int(h * 0.026)),
        font("segoeuil.ttf", int(h * 0.024)),
        font("segoeui.ttf", int(h * 0.02)),
        font("segoeuil.ttf", int(h * 0.016)),
    )
    y_lbl, y_dim = int(h * 0.80), int(h * 0.88)
    for i, name in enumerate(("front", "side", "bottom")):
        ox = i * (w + sep)
        centered(d, ox + w / 2, y_lbl, spaced(name.upper()), f_lbl, ink)
        if "dim" in lay[name]:
            (x0, _), (x1, _) = lay[name]["dim"]
            dimension(d, ox + x0, ox + x1, y_dim, f"{lay[name]['mm']} mm", f_dim, ink)
    # bottom: caster callout with a leader line to the projected caster position
    ox = 2 * (w + sep)
    cx, cy = lay["bottom"]["caster"]
    tx, ty = ox + w * 0.60, h * 0.07
    d.line((ox + cx + 6, cy - 6, tx - 8, ty + f_note.size * 1.9), fill=ink, width=2)
    d.text((tx, ty), "Front caster", font=f_note, fill=ink)
    d.text((tx, ty + f_note.size * 1.25), "HESTORE BCASTER-15-10K", font=f_small, fill=ink)
    out = os.path.join(SRC, "views.png")
    sheet.save(out)
    print(out, sheet.size)


if __name__ == "__main__":
    main()
