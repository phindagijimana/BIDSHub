"""Generate the BIDSHub app icons (.icns for macOS, .ico for Windows).

Renders a 1024x1024 master in the existing brand (navy field, white "BH"),
then derives a macOS .iconset -> .icns (via iconutil, macOS only) and a
multi-resolution .ico. Run from anywhere:

    python packaging/make_icons.py

Outputs into packaging/icons/.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

NAVY = "#002d72"
WHITE = "#ffffff"
OUT = Path(__file__).resolve().parent / "icons"
MASTER = 1024


def _font(size: int):
    for path in (
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial.ttf",
    ):
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def render_master() -> Image.Image:
    """1024px rounded-square navy icon with centred white 'BH'."""
    img = Image.new("RGBA", (MASTER, MASTER), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = int(MASTER * 0.22)
    draw.rounded_rectangle([0, 0, MASTER - 1, MASTER - 1], radius=radius, fill=NAVY)

    text = "BH"
    font = _font(int(MASTER * 0.46))
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (MASTER - tw) // 2 - bbox[0]
    y = (MASTER - th) // 2 - bbox[1]
    draw.text((x, y), text, fill=WHITE, font=font)
    return img


def make_icns(master: Image.Image) -> Path | None:
    """Build packaging/icons/BIDSHub.icns (macOS, needs iconutil)."""
    if sys.platform != "darwin" or shutil.which("iconutil") is None:
        print("[icons] skipping .icns (iconutil unavailable; not on macOS)")
        return None
    iconset = OUT / "BIDSHub.iconset"
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir(parents=True)
    for size in (16, 32, 64, 128, 256, 512):
        master.resize((size, size), Image.LANCZOS).save(iconset / f"icon_{size}x{size}.png")
        master.resize((size * 2, size * 2), Image.LANCZOS).save(
            iconset / f"icon_{size}x{size}@2x.png"
        )
    icns = OUT / "BIDSHub.icns"
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icns)], check=True)
    shutil.rmtree(iconset)
    print(f"[icons] wrote {icns}")
    return icns


def make_ico(master: Image.Image) -> Path:
    """Build packaging/icons/BIDSHub.ico (Windows)."""
    ico = OUT / "BIDSHub.ico"
    sizes = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]
    master.save(ico, format="ICO", sizes=sizes)
    print(f"[icons] wrote {ico}")
    return ico


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    master = render_master()
    master.save(OUT / "icon_1024.png")
    print(f"[icons] wrote {OUT / 'icon_1024.png'}")
    make_icns(master)
    make_ico(master)
    return 0


if __name__ == "__main__":
    sys.exit(main())
