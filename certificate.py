from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
FONTS_DIR = ROOT / "fonts"
DEFAULT_TEMPLATE = ROOT / "assets" / "template-payout.png"

MONTHS_EN = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
}


def load_font(filename: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = FONTS_DIR / filename
    if path.exists():
        return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def scale_point(x: int, y: int, design_size: tuple[int, int], image_size: tuple[int, int]) -> tuple[int, int]:
    design_w, design_h = design_size
    image_w, image_h = image_size
    return int(x * image_w / design_w), int(y * image_h / design_h)


def scale_font_size(size: int, design_size: tuple[int, int], image_size: tuple[int, int]) -> int:
    scale = min(image_size[0] / design_size[0], image_size[1] / design_size[1])
    return max(1, int(round(size * scale)))


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    position: tuple[int, int],
    font: ImageFont.ImageFont,
    color: str,
) -> None:
    draw.text(position, text, font=font, fill=color, anchor="mm")


def first_name_only(full_name: str | None) -> str:
    if not full_name:
        return ""
    parts = full_name.strip().split()
    return parts[0] if parts else ""


def format_amount(payout: dict) -> str:
    amount = payout.get("transferAmount")
    if amount in (None, 0):
        amount = payout.get("actualAmount")
    if amount is None:
        amount = payout.get("amount", 0)

    currency = (payout.get("currency") or "USD").upper()
    symbol = CURRENCY_SYMBOLS.get(currency, f"{currency} ")
    return f"{symbol}{float(amount):,.2f}"


def format_date(payout: dict) -> str:
    raw = payout.get("stateTimestamp") or payout.get("createdAt")
    if not raw:
        return ""
    dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return f"{MONTHS_EN[dt.month - 1]} {dt.day}, {dt.year}"


def generate_certificate(
    payout: dict,
    config: dict,
    template_path: Path | None = None,
) -> Image.Image:
    cert_config = config["certificate"]
    template = Image.open(template_path or Path(cert_config.get("template", DEFAULT_TEMPLATE))).convert("RGBA")
    image = template.copy()
    draw = ImageDraw.Draw(image)

    design_size = tuple(cert_config["design_size"])
    image_size = image.size

    fields = cert_config["fields"]
    amount_font = load_font(
        fields["amount"]["font"],
        scale_font_size(fields["amount"]["size"], design_size, image_size),
    )
    program_font = load_font(
        fields["program_name"]["font"],
        scale_font_size(fields["program_name"]["size"], design_size, image_size),
    )
    username_font = load_font(
        fields["username"]["font"],
        scale_font_size(fields["username"]["size"], design_size, image_size),
    )
    date_font = load_font(
        fields["date"]["font"],
        scale_font_size(fields["date"]["size"], design_size, image_size),
    )

    amount_pos = scale_point(*fields["amount"]["position"], design_size, image_size)
    program_pos = scale_point(*fields["program_name"]["position"], design_size, image_size)
    username_pos = scale_point(*fields["username"]["position"], design_size, image_size)
    date_pos = scale_point(*fields["date"]["position"], design_size, image_size)

    draw_centered_text(draw, format_amount(payout), amount_pos, amount_font, f"#{fields['amount']['color']}")
    draw_centered_text(
        draw,
        payout.get("programName") or "",
        program_pos,
        program_font,
        f"#{fields['program_name']['color']}",
    )

    if cert_config.get("privacy", "first_name_only") == "first_name_only":
        username = first_name_only(payout.get("fullName"))
    else:
        username = payout.get("fullName") or ""

    draw_centered_text(draw, username, username_pos, username_font, f"#{fields['username']['color']}")
    draw_centered_text(draw, format_date(payout), date_pos, date_font, f"#{fields['date']['color']}")

    return image.convert("RGB")


if __name__ == "__main__":
    sample = {
        "fullName": "Maxime Daiber",
        "programName": "Firmup Funded - 50k",
        "transferAmount": 953.10,
        "currency": "USD",
        "stateTimestamp": "2026-06-18T00:00:00Z",
    }
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    output = generate_certificate(sample, cfg)
    output.save(ROOT / "test-certificate.png")
    print("Généré : test-certificate.png")
