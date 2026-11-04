"""Render the PWA icons: python scripts/make_icons.py  (needs Pillow). Writes web/icons/icon.svg, icon-192.png, icon-512.png, icon-maskable-512.png."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "web" / "icons"
BG, GREEN = (2, 6, 23), (34, 197, 94)


def font(size: int):
    for p in (r"C:\Windows\Fonts\consolab.ttf", r"C:\Windows\Fonts\consola.ttf", r"C:\Windows\Fonts\cour.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default(size)


def render(size: int, safe: float) -> Image.Image:
    """safe is the fraction of the canvas the glyph may use (maskable icons need a larger margin)."""
    img = Image.new("RGB", (size, size), BG)
    d = ImageDraw.Draw(img)
    f = font(int(size * 0.5 * safe / 0.8))
    box = d.textbbox((0, 0), ">_", font=f)
    d.text(((size - (box[2] - box[0])) / 2 - box[0], (size - (box[3] - box[1])) / 2 - box[1]), ">_", font=f, fill=GREEN)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    render(192, 0.8).save(OUT / "icon-192.png")
    render(512, 0.8).save(OUT / "icon-512.png")
    render(512, 0.6).save(OUT / "icon-maskable-512.png")
    (OUT / "icon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="12" fill="#020617"/>'
                                  '<text x="32" y="42" font-family="monospace" font-size="30" font-weight="700" text-anchor="middle" fill="#22c55e">&gt;_</text></svg>\n', encoding="utf-8")
    print("icons written to", OUT)


if __name__ == "__main__":
    main()
