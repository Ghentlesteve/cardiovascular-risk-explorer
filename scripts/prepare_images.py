"""Make small, Power BI-ready copies of the organ images.

Reads   assets/organs/<organ>_<state>.png   (any size, transparent background)
Writes  assets/organs/powerbi/<organ>_<state>.png  (300 x 300, ~25 KB each)

The report embeds these small copies (see powerbi/organ_images.pq), so keep them small.

Usage:  python scripts/prepare_images.py
"""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets" / "organs"
OUT = SRC / "powerbi"
NAMES = [f"{o}_{s}" for o in ("heart", "brain", "kidney") for s in ("healthy", "damaged")]
SIZE = 300


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name in NAMES:
        src = SRC / f"{name}.png"
        if not src.exists():
            print(f"missing: {src.relative_to(ROOT)}")
            continue
        im = Image.open(src).convert("RGBA")
        # crop to the visible organ, then centre it on a square transparent canvas
        bbox = im.getchannel("A").point(lambda a: 255 if a > 10 else 0).getbbox()
        if bbox:
            im = im.crop(bbox)
        im.thumbnail((SIZE, SIZE), Image.LANCZOS)
        canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        canvas.paste(im, ((SIZE - im.width) // 2, (SIZE - im.height) // 2), im)
        dst = OUT / f"{name}.png"
        canvas.quantize(colors=128, method=Image.FASTOCTREE).save(dst, optimize=True)
        print(f"{dst.relative_to(ROOT)}  {dst.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
