from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from certificate import generate_certificate
from sync import (
    CONFIG_PATH,
    STATE_PATH,
    env,
    fetch_payouts,
    load_json,
    payout_sort_key,
    save_json,
)
from wordpress_client import WordPressClient, WordPressConfig

ROOT = Path(__file__).resolve().parent


def wordpress_config_from_file(config: dict) -> WordPressConfig:
    wp = config.get("wordpress") or {}
    return WordPressConfig.from_dict(wp)


def is_dry_run() -> bool:
    value = os.getenv("WP_DRY_RUN", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def main() -> None:
    dry_run = is_dry_run()
    base_url = env("API_BASE_URL", required=not dry_run)
    api_key = env("API_KEY", required=not dry_run)

    wp_username = os.getenv("WP_USERNAME")
    wp_app_password = os.getenv("WP_APP_PASSWORD")
    if not dry_run and (not wp_username or not wp_app_password):
        print("Variables d'environnement manquantes : WP_USERNAME et/ou WP_APP_PASSWORD", file=sys.stderr)
        sys.exit(1)

    config = load_json(CONFIG_PATH, {})
    wp_config = wordpress_config_from_file(config)
    wp_settings = config.get("wordpress") or {}

    state = load_json(STATE_PATH, {"processed_ids": [], "wordpress_processed_ids": []})
    processed_ids = set(state.get("wordpress_processed_ids") or [])

    client = WordPressClient(
        wp_config,
        username=wp_username,
        app_password=wp_app_password,
        dry_run=dry_run,
        export_dir=ROOT / "simulation",
    )

    connection = client.check_connection()
    print(f"WordPress : {connection}")

    if dry_run:
        print("Mode simulation activé (WP_DRY_RUN=1). Aucune écriture sur swissfirmup.com.")
        payouts = _sample_payouts_for_dry_run()
    else:
        payouts = fetch_payouts(base_url, api_key, config)

    print(f"Payouts éligibles récupérés : {len(payouts)}")
    new_payouts = [p for p in payouts if p.get("id") and p["id"] not in processed_ids]
    new_payouts.sort(key=payout_sort_key)
    print(f"Déjà publiés WP : {len(processed_ids)} | Nouveaux : {len(new_payouts)}")

    if not new_payouts:
        print("Aucun nouveau payout à publier sur WordPress.")
        return

    max_per_run = int(wp_settings.get("max_per_run", config.get("max_per_run", 0)))
    delay_seconds = float(wp_settings.get("delay_seconds", 2))
    to_publish = new_payouts[:max_per_run] if max_per_run > 0 else new_payouts

    print(f"À publier sur WordPress ce run : {len(to_publish)}")
    results = []
    published = 0

    for index, payout in enumerate(to_publish):
        payout_id = payout["id"]
        try:
            image = generate_certificate(payout, config)
            result = client.publish_payout(payout, image)
            results.append(result)
            processed_ids.add(payout_id)
            published += 1
            state["wordpress_processed_ids"] = sorted(processed_ids)
            save_json(STATE_PATH, state)
            label = "Simulé" if dry_run else "Publié"
            print(f"{label} ({index + 1}/{len(to_publish)}) : {payout_id} — {result.title}")
        except Exception as exc:  # noqa: BLE001
            print(f"Échec pour {payout_id} : {exc}", file=sys.stderr)
            continue

        if delay_seconds > 0 and index < len(to_publish) - 1:
            time.sleep(delay_seconds)

    if results:
        export_path = client.append_export(results)
        print(f"Export simulation : {export_path}")

    if dry_run and results:
        preview_script = ROOT / "scripts" / "simulate_wordpress.py"
        print(f"Générez l'aperçu carrousel : python {preview_script}")

    print(f"Terminé. {published} publication(s) WordPress.")


def _sample_payouts_for_dry_run() -> list[dict]:
    return [
        {
            "id": "sim-001",
            "fullName": "Michele Rossi",
            "programName": "Firmup Funded - 50k",
            "transferAmount": 900.00,
            "currency": "USD",
            "state": "Approved",
            "stateTimestamp": "2026-06-10T00:00:00Z",
        },
        {
            "id": "sim-002",
            "fullName": "Hafiz Ahmad",
            "programName": "Firmup Funded - 100k",
            "transferAmount": 3600.00,
            "currency": "USD",
            "state": "Approved",
            "stateTimestamp": "2026-06-12T00:00:00Z",
        },
        {
            "id": "sim-003",
            "fullName": "Victor Martin",
            "programName": "Firmup Funded - 25k",
            "transferAmount": 430.20,
            "currency": "USD",
            "state": "Processed",
            "stateTimestamp": "2026-06-15T00:00:00Z",
        },
        {
            "id": "sim-004",
            "fullName": "Maxime Daiber",
            "programName": "Firmup Funded - 50k",
            "transferAmount": 953.10,
            "currency": "USD",
            "state": "Approved",
            "stateTimestamp": "2026-06-18T00:00:00Z",
        },
        {
            "id": "sim-005",
            "fullName": "Sarah Chen",
            "programName": "Firmup Funded - 150k",
            "transferAmount": 2150.75,
            "currency": "USD",
            "state": "Approved",
            "stateTimestamp": "2026-06-20T00:00:00Z",
        },
        {
            "id": "sim-006",
            "fullName": "Luca Bianchi",
            "programName": "Firmup Funded - 75k",
            "transferAmount": 1280.00,
            "currency": "USD",
            "state": "Approved",
            "stateTimestamp": "2026-06-22T00:00:00Z",
        },
    ]


if __name__ == "__main__":
    main()
