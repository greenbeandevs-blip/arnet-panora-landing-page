#!/usr/bin/env python
"""
Regenerates the optimized assets that index.html and about.html reference.

Originals are never modified - everything is written into sibling "opt"
folders, plus style/font/woff2. Run from the project root:

    pip install Pillow fonttools brotli
    python tools/build-assets.py

Outputs
  style/images/opt/<name>-<w>.webp              landing page images
  style/images/portfolio/opt/<folder>/<n>-<w>.webp   about.html gallery
  360/opt/<folder>/<scene>-<w>.webp             panoramas (capped at 4096px:
                                                WebGL on most phones cannot
                                                sample a texture wider than that)
  style/font/woff2/*.woff2                      webfont builds of the ttf/otf
  asset-manifest.json                           widths that exist per source

If you add an image, re-run this, then update the matching srcset in
index.html (or, for about.html, paste the new asset-manifest entries into the
IMG_OPT / PANO_OPT maps inlined in that file).
"""

import glob
import json
import os

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

RASTER_EXTS = (".png", ".jpg", ".jpeg", ".jfif")

# (source glob, output dir template, widths, webp quality)
IMAGE_JOBS = [
    ("style/images/*.*",                 "style/images/opt",                    [480, 960, 1440, 1920], 78),
    ("style/images/portfolio/*/*.*",     "style/images/portfolio/opt/{folder}", [480, 960, 1536],       80),
    ("360/*/*.png",                      "360/opt/{folder}",                    [2048, 4096],           82),
]

FONT_JOBS = [
    ("style/font/arista_pro/Arista-Pro-Light-trial.ttf", "Arista-Pro-Light.woff2"),
    ("style/font/arista_pro/Arista-Pro-Bold-trial.ttf",  "Arista-Pro-Bold.woff2"),
    ("style/font/arista_pro/Arista-Pro-Fat-trial.ttf",   "Arista-Pro-Fat.woff2"),
    ("style/font/TT Norms sv/TTNorms-Light.otf",         "TTNorms-Light.woff2"),
    ("style/font/TT Norms sv/TTNorms-Regular.otf",       "TTNorms-Regular.woff2"),
    ("style/font/TT Norms sv/TTNorms-Bold.otf",          "TTNorms-Bold.woff2"),
    ("style/font/TT Norms sv/TTNorms-Italic.otf",        "TTNorms-Italic.woff2"),
]


def build_images():
    manifest = {}
    size_in = size_out = 0

    for pattern, outdir_tpl, widths, quality in IMAGE_JOBS:
        for src in sorted(glob.glob(pattern)):
            rel = src.replace("\\", "/")
            if "/opt/" in rel or os.path.splitext(rel)[1].lower() not in RASTER_EXTS:
                continue
            try:
                im = Image.open(src)
                im.load()
            except Exception as exc:                      # not an image (desktop.ini, ...)
                print("  skip %s (%s)" % (rel, exc))
                continue

            has_alpha = im.mode in ("RGBA", "LA") or (
                im.mode == "P" and "transparency" in im.info)
            im = im.convert("RGBA" if has_alpha else "RGB")
            ow, oh = im.size

            outdir = outdir_tpl.format(folder=rel.split("/")[-2])
            os.makedirs(outdir, exist_ok=True)
            name = os.path.splitext(os.path.basename(rel))[0]

            # every requested width below the original, plus one at the
            # original (or the cap, whichever is smaller)
            targets = sorted(set([w for w in widths if w < ow] + [min(ow, max(widths))]))

            size_in += os.path.getsize(src)
            made = []
            for w in targets:
                h = max(1, round(oh * w / ow))
                out = im if w == ow else im.resize((w, h), Image.LANCZOS)
                dst = os.path.join(outdir, "%s-%d.webp" % (name, w))
                out.save(dst, "WEBP", quality=quality, method=6)
                size_out += os.path.getsize(dst)
                made.append(w)

            manifest[rel] = made
            print("  %-62s -> %s" % (rel, made))

    json.dump(manifest, open("asset-manifest.json", "w"), indent=0, sort_keys=True)
    print("\n  images: %.1fMB of originals -> %.1fMB of derivatives (all widths)"
          % (size_in / 1048576, size_out / 1048576))


def build_fonts():
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        print("  fonttools not installed - skipping fonts (pip install fonttools brotli)")
        return

    os.makedirs("style/font/woff2", exist_ok=True)
    for src, out_name in FONT_JOBS:
        if not os.path.exists(src):
            print("  missing %s" % src)
            continue
        dst = os.path.join("style/font/woff2", out_name)
        font = TTFont(src)
        font.flavor = "woff2"
        font.save(dst)
        print("  %-52s %5dK -> %4dK"
              % (out_name, os.path.getsize(src) // 1024, os.path.getsize(dst) // 1024))


if __name__ == "__main__":
    print("images:")
    build_images()
    print("\nfonts:")
    build_fonts()
    print("\ndone")
