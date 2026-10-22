"""Build the logo, favicon and web-sized marketing images from the renders (system Python + Pillow).

    python cad/blender/make_brand.py

Input:  cad/renders/marketing/cutout.png (transparent render of the real model), home_hero.png
Output: assets/brand/
    mirae-logo.png           512x512 transparent logo (the robot itself)
    mirae-logo-256.png       256x256
    favicon.ico              16/32/48/64 multi-size icon
    favicon-32.png, favicon-16.png
    apple-touch-icon.png     180x180 on the warm-white brand background
    hero.jpg                 2560x1280 README / web hero
    social-preview.jpg       1280x640 GitHub social preview (Settings -> General -> Social preview)
"""

import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(REPO, "cad", "renders", "marketing")
OUT = os.path.join(REPO, "assets", "brand")
BRAND_BG = (244, 242, 238, 255)


def square_logo(img, size, pad=0.06):
    """Crop to the robot (ignoring the faint contact shadow), centre it on a square canvas."""
    alpha = img.getchannel("A")
    solid = alpha.point(lambda a: 255 if a > 200 else 0)
    box = solid.getbbox()
    robot = img.crop(box)
    side = int(max(robot.size) * (1 + 2 * pad))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.alpha_composite(robot, ((side - robot.width) // 2, (side - robot.height) // 2))
    return canvas.resize((size, size), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    cut = Image.open(os.path.join(SRC, "cutout.png")).convert("RGBA")
    logo = square_logo(cut, 1024)
    logo.resize((512, 512), Image.LANCZOS).save(os.path.join(OUT, "mirae-logo.png"))
    logo.resize((256, 256), Image.LANCZOS).save(os.path.join(OUT, "mirae-logo-256.png"))
    # tiny sizes: a tighter crop reads better
    icon = square_logo(cut, 256, pad=0.02)
    icon.save(os.path.join(OUT, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    icon.resize((32, 32), Image.LANCZOS).save(os.path.join(OUT, "favicon-32.png"))
    icon.resize((16, 16), Image.LANCZOS).save(os.path.join(OUT, "favicon-16.png"))
    touch = Image.new("RGBA", (180, 180), BRAND_BG)
    touch.alpha_composite(square_logo(cut, 150, pad=0.04), (15, 15))
    touch.convert("RGB").save(os.path.join(OUT, "apple-touch-icon.png"))

    hero = Image.open(os.path.join(SRC, "home_hero.png")).convert("RGB")
    hero.save(os.path.join(OUT, "hero.jpg"), quality=88, optimize=True, progressive=True)
    hero.resize((1280, 640), Image.LANCZOS).save(
        os.path.join(OUT, "social-preview.jpg"), quality=90, optimize=True
    )
    for f in sorted(os.listdir(OUT)):
        print(f, os.path.getsize(os.path.join(OUT, f)) // 1024, "KB")


if __name__ == "__main__":
    main()
