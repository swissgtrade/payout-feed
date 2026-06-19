"""Prépare le template : espace PAYOUT/CERTIFICATE + suppression du QR code."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "template-payout-source.png"
TARGET = ROOT / "assets" / "template-payout.png"

# Zone QR + cadre blanc + halo gris laissé par les bordures antialiassées.
QR_REMOVE_ZONE = (77, 765, 301, 990)
BG_COLOR = (3, 5, 4)


def widen_title_gap(image: Image.Image) -> Image.Image:
    """Élargit l'espace sombre entre PAYOUT et CERTIFICATE sans décaler le glow."""
    result = image.copy()
    pixels = result.load()

    for y in range(205, 235):
        for x in range(698, 752):
            r, g, b = pixels[x, y]
            if r + g + b < 520:
                pixels[x, y] = (0, 0, 0)

    return result


def remove_qr(image: Image.Image) -> Image.Image:
    """Supprime le QR code et restaure le fond sombre du certificat."""
    result = image.copy()
    x0, y0, x1, y1 = QR_REMOVE_ZONE
    result.paste(Image.new("RGB", (x1 - x0, y1 - y0), BG_COLOR), (x0, y0))
    return result


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(f"Template source introuvable : {SOURCE}")

    image = Image.open(SOURCE).convert("RGB")
    image = widen_title_gap(image)
    image = remove_qr(image)
    image.save(TARGET)
    print(f"Template préparé : {TARGET} ({image.size[0]}x{image.size[1]})")


if __name__ == "__main__":
    main()
