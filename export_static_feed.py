from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from certificate import first_name_only, format_amount
from sync import CONFIG_PATH, env, fetch_payouts, load_json, payout_sort_key

ROOT = Path(__file__).resolve().parent


def main() -> None:
    base_url = env("API_BASE_URL")
    api_key = env("API_KEY")
    config = load_json(CONFIG_PATH, {})
    feed_config = config.get("static_feed", {})

    feed_size = int(feed_config.get("feed_size", 10))
    output_path = ROOT / feed_config.get("output_file", "payouts.json")

    payouts = fetch_payouts(base_url, api_key, config)
    payouts.sort(key=payout_sort_key, reverse=True)
    latest = payouts[:feed_size]

    items = []
    total = 0.0
    for payout in latest:
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
        items.append(
            {
                "name": name,
                "amount": format_amount(payout),
                "status": "Versé",
            }
        )

    feed = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_amount": round(total, 2),
        "payouts": items,
    }

    output_path.write_text(
        json.dumps(feed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Écrit {output_path} avec {len(items)} payout(s), total {feed['total_amount']}")


if __name__ == "__main__":
    main()
