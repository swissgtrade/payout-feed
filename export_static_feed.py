from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from certificate import first_name_only, format_amount, generate_certificate
from sync import CONFIG_PATH, env, fetch_payouts, load_json, payout_sort_key

ROOT = Path(__file__).resolve().parent


def prune_stale_certs(certs_dir: Path, keep_filenames: set[str]) -> None:
    """Supprime les miniatures de certificats qui ne sont plus dans le flux."""
    if not certs_dir.exists():
        return
    for path in certs_dir.iterdir():
        if path.is_file() and path.name not in keep_filenames:
            path.unlink()


def main() -> None:
    base_url = env("API_BASE_URL")
    api_key = env("API_KEY")
    config = load_json(CONFIG_PATH, {})
    feed_config = config.get("static_feed", {})

    feed_size = int(feed_config.get("feed_size", 10))
    output_path = ROOT / feed_config.get("output_file", "payouts.json")
    certs_dir = ROOT / feed_config.get("certs_dir", "certs")
    thumb_width = int(feed_config.get("thumb_width", 480))
    certs_dir.mkdir(exist_ok=True)

    payouts = fetch_payouts(base_url, api_key, config)
    payouts.sort(key=payout_sort_key, reverse=True)
    latest = payouts[:feed_size]

    items = []
    keep_filenames: set[str] = set()
    total = 0.0

    for payout in latest:
        payout_id = payout.get("id") or ""
        name = first_name_only(payout.get("fullName")).upper()
        amount_value = (
            payout.get("transferAmount")
            or payout.get("actualAmount")
            or payout.get("amount")
            or 0
        )
        try:
            total += float(amount_value)
        except (TypeError, ValueError):
            pass

        image_rel = None
        if payout_id:
            filename = f"{payout_id}.png"
            try:
                cert = generate_certificate(payout, config)
                ratio = thumb_width / cert.width
                thumb = cert.resize(
                    (thumb_width, int(cert.height * ratio)), Image.Resampling.LANCZOS
                )
                thumb.save(certs_dir / filename, optimize=True)
                keep_filenames.add(filename)
                image_rel = f"{certs_dir.name}/{filename}"
            except Exception as exc:  # noqa: BLE001 - le payout reste publié en mode texte
                print(f"Miniature échouée pour {payout_id} : {exc}")

        items.append(
            {
                "name": name,
                "amount": format_amount(payout),
                "status": "Versé",
                "image": image_rel,
            }
        )

    prune_stale_certs(certs_dir, keep_filenames)

    feed = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_amount": round(total, 2),
        "payouts": items,
    }

    output_path.write_text(
        json.dumps(feed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Écrit {output_path} avec {len(items)} payout(s), total {feed['total_amount']}, "
        f"miniatures dans {certs_dir}"
    )


if __name__ == "__main__":
    main()
