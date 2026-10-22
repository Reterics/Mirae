"""Download the CC0 Poly Haven assets used by the lifestyle renders (system Python).

    python cad/blender/fetch_assets.py

Files land in cad/renders/assets/ (git-ignored). Existing files are skipped.
"""

import json
import os
import urllib.request

ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "renders", "assets")
)
API = "https://api.polyhaven.com/files/"
HDRIS = {"photo_studio_loft_hall": "4k"}
TEXTURES = {"laminate_floor_02": "2k"}
MODELS = {
    "modern_arm_chair_01": "2k",
    "mid_century_lounge_chair": "2k",
    "potted_plant_02": "2k",
    "modern_coffee_table_01": "2k",
    "book_encyclopedia_set_01": "1k",
}


def get(url, path):
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "mirae-cad"})
    with urllib.request.urlopen(req) as r, open(path, "wb") as f:
        f.write(r.read())
    print("got", os.path.relpath(path, ROOT))


def files(asset):
    req = urllib.request.Request(API + asset, headers={"User-Agent": "mirae-cad"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def main():
    for name, res in HDRIS.items():
        get(files(name)["hdri"][res]["hdr"]["url"], os.path.join(ROOT, "hdri", f"{name}_{res}.hdr"))
    for name, res in TEXTURES.items():
        d = files(name)
        for key, short in (("Diffuse", "diff"), ("Rough", "rough"), ("nor_gl", "nor_gl")):
            get(d[key][res]["jpg"]["url"], os.path.join(ROOT, name, f"{name}_{short}_{res}.jpg"))
    for name, res in MODELS.items():
        g = files(name)["gltf"][res]["gltf"]
        base = os.path.join(ROOT, "models", name)
        get(g["url"], os.path.join(base, os.path.basename(g["url"])))
        for rel, info in g.get("include", {}).items():
            get(info["url"], os.path.join(base, rel))


if __name__ == "__main__":
    main()
