from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIMULATION_DIR = ROOT / "simulation"
EXPORT_PATH = SIMULATION_DIR / "wordpress-export.json"
PREVIEW_PATH = SIMULATION_DIR / "preview.html"
CERT_DIR = SIMULATION_DIR / "certificates"

INTRO_TEXT = (
    "Constituez votre capital en toute sérénité et profitez d'un environnement de trading "
    "sûr et de qualité, où vos compétences peuvent s'épanouir pleinement sur les marchés à terme."
)


def load_export() -> dict:
    if not EXPORT_PATH.exists():
        raise FileNotFoundError(
            f"{EXPORT_PATH} introuvable. Lancez d'abord : WP_DRY_RUN=1 python sync_wordpress.py"
        )
    return json.loads(EXPORT_PATH.read_text(encoding="utf-8"))


def slide_items(export: dict) -> list[dict]:
    items = export.get("items") or []
    slides: list[dict] = []
    for item in items:
        filename = item.get("filename")
        if not filename:
            continue
        image_path = CERT_DIR / filename
        if not image_path.exists():
            continue
        slides.append(
            {
                "title": item.get("title") or filename,
                "src": f"certificates/{filename}",
            }
        )
    return slides


def build_preview(slides: list[dict], site_url: str) -> str:
    slide_html = "\n".join(
        f"""                <div class="swiper-slide firmup-payout-carousel__slide">
                    <img class="firmup-payout-carousel__image" src="{html.escape(slide["src"])}" alt="{html.escape(slide["title"])}" loading="lazy" />
                </div>"""
        for slide in slides
    )

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Simulation carrousel payouts — {html.escape(site_url)}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swiper@11/swiper-bundle.min.css" />
  <link rel="stylesheet" href="../wordpress/assets/payout-carousel.css" />
  <style>
    :root {{
      color-scheme: dark;
    }}
    body {{
      margin: 0;
      font-family: Inter,Segoe UI,Roboto,Arial,sans-serif;
      background: #050505;
      color: #f4f4f4;
    }}
    .preview-shell {{
      max-width: 1240px;
      margin: 0 auto;
      padding: 48px 24px 72px;
    }}
    .preview-badge {{
      display: inline-block;
      margin-bottom: 18px;
      padding: 6px 12px;
      border-radius: 999px;
      background: rgba(255, 201, 0, 0.12);
      color: #ffc900;
      font-size: 12px;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    .preview-intro {{
      max-width: 920px;
      margin: 0 auto 36px;
      text-align: center;
      line-height: 1.7;
      color: rgba(255, 255, 255, 0.82);
      font-size: 18px;
    }}
    .preview-note {{
      margin-top: 28px;
      text-align: center;
      color: rgba(255, 255, 255, 0.45);
      font-size: 14px;
    }}
  </style>
</head>
<body>
  <div class="preview-shell">
    <div class="preview-badge">Simulation locale — page d'accueil Elementor</div>
    <p class="preview-intro">{html.escape(INTRO_TEXT)}</p>

    <div
      class="firmup-payout-carousel"
      id="firmup-payout-carousel-preview"
      data-slides="3"
      data-autoplay="5000"
    >
      <div class="swiper firmup-payout-carousel__swiper">
        <div class="swiper-wrapper">
{slide_html}
        </div>
        <div class="swiper-pagination firmup-payout-carousel__pagination"></div>
      </div>
    </div>

    <p class="preview-note">
      Shortcode Elementor : <code>[firmup_payout_carousel slides="3" autoplay="5"]</code>
    </p>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/swiper@11/swiper-bundle.min.js"></script>
  <script src="../wordpress/assets/payout-carousel.js"></script>
</body>
</html>
"""


def main() -> None:
    export = load_export()
    slides = slide_items(export)
    if not slides:
        raise SystemExit("Aucune image trouvée dans simulation/certificates/. Relancez sync_wordpress.py.")

    site_url = export.get("site_url", "https://swissfirmup.com")
    PREVIEW_PATH.write_text(build_preview(slides, site_url), encoding="utf-8")
    print(f"Aperçu généré : {PREVIEW_PATH}")
    print(f"Slides : {len(slides)}")


if __name__ == "__main__":
    main()
