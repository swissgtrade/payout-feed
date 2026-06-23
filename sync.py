from __future__ import annotations

import io
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin

import requests
from PIL import Image

from certificate import generate_certificate

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
STATE_PATH = ROOT / "state.json"


def load_json(path: Path, default: dict | list) -> dict | list:
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, data: dict | list) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def update_state_field(field: str, values: set[str]) -> None:
    """Met à jour un champ de state.json sans écraser l'autre (Discord/WP)."""
    state = load_json(STATE_PATH, {"processed_ids": [], "wordpress_processed_ids": []})
    state[field] = sorted(values)
    save_json(STATE_PATH, state)


def env(name: str, required: bool = True, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if required and not value:
        print(f"Variable d'environnement manquante : {name}", file=sys.stderr)
        sys.exit(1)
    return value or ""


def api_headers(api_key: str) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "X-Client-Key": api_key,
    }


def _api_get_json(url: str, api_key: str, params: dict[str, str | int]) -> dict:
    response = requests.get(url, headers=api_headers(api_key), params=params, timeout=60)
    try:
        response.raise_for_status()
    except requests.HTTPError:
        print(f"Erreur API {response.status_code} pour {params}", file=sys.stderr)
        print(response.text, file=sys.stderr)
        raise
    return response.json()


def _fetch_status_pages(
    endpoint: str,
    api_key: str,
    config: dict,
    *,
    page_size: int,
    max_pages: int,
    status_filter: str | None,
    publish_states: set[str],
    filter_client_side: bool,
) -> tuple[list[dict], Counter[str]]:
    page = 1
    payouts: list[dict] = []
    seen_ids: set[str] = set()
    all_states: Counter[str] = Counter()
    label = status_filter or "tous"

    while page <= max_pages:
        params: dict[str, str | int] = {
            "page": page,
            "pageSize": page_size,
            "sortBy": config.get("sort_by", "createdAt"),
            "sortDirection": config.get("sort_direction", "desc"),
        }
        if status_filter:
            params["status"] = status_filter

        payload = _api_get_json(endpoint, api_key, params)
        batch = payload.get("results") or []
        if not batch:
            break

        page_states: Counter[str] = Counter()
        retained_page = 0
        for payout in batch:
            state = payout.get("state") or "(vide)"
            page_states[state] += 1
            all_states[state] += 1

            payout_id = payout.get("id")
            if not payout_id or payout_id in seen_ids:
                continue

            if filter_client_side and state.lower() not in publish_states:
                continue

            seen_ids.add(payout_id)
            payouts.append(payout)
            retained_page += 1

        total = payload.get("total") or payload.get("totalCount")
        total_pages = payload.get("totalPages")
        print(
            f"[{label}] Page {page}: {len(batch)} reçu(s), {retained_page} retenu(s) sur la page, "
            f"{len(payouts)} retenu(s) pour ce filtre"
            + (f", total API={total}" if total is not None else "")
            + (f", pages={total_pages}" if total_pages is not None else "")
        )
        if filter_client_side:
            print(f"  Statuts page {page}: {dict(page_states)}")

        if total_pages is not None and int(total_pages) > 0:
            if page >= int(total_pages):
                break
        elif len(batch) < page_size:
            break
        page += 1

    return payouts, all_states


def fetch_payouts(base_url: str, api_key: str, config: dict) -> list[dict]:
    endpoint = urljoin(base_url.rstrip("/") + "/", "client/v2/payouts")
    page_size = int(config.get("page_size", 50))
    max_pages = int(config.get("max_pages", 200))
    publish_states = {state.lower() for state in config.get("payout_states", ["Approved"])}
    fetch_all_statuses = bool(config.get("fetch_all_statuses", True))

    payouts: list[dict] = []
    seen_ids: set[str] = set()
    all_states: Counter[str] = Counter()

    if fetch_all_statuses:
        batch, states = _fetch_status_pages(
            endpoint,
            api_key,
            config,
            page_size=page_size,
            max_pages=max_pages,
            status_filter=None,
            publish_states=publish_states,
            filter_client_side=True,
        )
        for payout in batch:
            payout_id = payout["id"]
            if payout_id not in seen_ids:
                seen_ids.add(payout_id)
                payouts.append(payout)
        all_states.update(states)
    else:
        for status in config.get("payout_states", ["Approved"]):
            try:
                batch, states = _fetch_status_pages(
                    endpoint,
                    api_key,
                    config,
                    page_size=page_size,
                    max_pages=max_pages,
                    status_filter=status,
                    publish_states=publish_states,
                    filter_client_side=False,
                )
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 400:
                    print(f"Statut API ignoré (invalide) : {status}", file=sys.stderr)
                    continue
                raise

            for payout in batch:
                payout_id = payout["id"]
                if payout_id not in seen_ids:
                    seen_ids.add(payout_id)
                    payouts.append(payout)
            all_states.update(states)

    if fetch_all_statuses:
        print(f"Répartition globale des statuts API : {dict(all_states)}")
        print(f"Statuts publiables configurés : {sorted(publish_states)}")

    return payouts


def post_discord_image(webhook_url: str, image: Image.Image, filename: str) -> None:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    response = requests.post(
        webhook_url,
        files={"file": (filename, buffer, "image/png")},
        timeout=60,
    )
    response.raise_for_status()


def payout_sort_key(payout: dict) -> str:
    return str(payout.get("stateTimestamp") or payout.get("createdAt") or "")


def main() -> None:
    base_url = env("API_BASE_URL")
    api_key = env("API_KEY")
    webhook_url = env("DISCORD_WEBHOOK_URL")

    config = load_json(CONFIG_PATH, {})
    state = load_json(STATE_PATH, {"processed_ids": [], "wordpress_processed_ids": []})
    processed_ids = set(state.get("processed_ids") or [])

    payouts = fetch_payouts(base_url, api_key, config)
    print(f"Payouts éligibles récupérés : {len(payouts)}")
    new_payouts = [p for p in payouts if p.get("id") and p["id"] not in processed_ids]
    new_payouts.sort(key=payout_sort_key)
    print(f"Déjà publiés : {len(processed_ids)} | Nouveaux : {len(new_payouts)}")

    if not new_payouts:
        print("Aucun nouveau payout à publier.")
        return

    max_per_run = int(config.get("max_per_run", 0))
    delay_seconds = float(config.get("discord_delay_seconds", 2))
    to_publish = new_payouts[:max_per_run] if max_per_run > 0 else new_payouts

    print(
        f"Ordre : du plus ancien au plus récent "
        f"({payout_sort_key(to_publish[0])} → {payout_sort_key(to_publish[-1])})"
    )
    if max_per_run > 0 and len(new_payouts) > max_per_run:
        print(
            f"Limite max_per_run={max_per_run} : "
            f"{len(to_publish)} publication(s) ce run, "
            f"{len(new_payouts) - len(to_publish)} en attente au prochain run"
        )
    else:
        print(f"À publier ce run : {len(to_publish)}")

    published = 0
    for index, payout in enumerate(to_publish):
        payout_id = payout["id"]
        try:
            image = generate_certificate(payout, config)
            post_discord_image(webhook_url, image, f"payout-{payout_id}.png")
            processed_ids.add(payout_id)
            published += 1
            update_state_field("processed_ids", processed_ids)
            print(f"Publié ({index + 1}/{len(to_publish)}) : {payout_id}")
        except Exception as exc:  # noqa: BLE001 - continuer sur les autres payouts
            print(f"Échec pour {payout_id} : {exc}", file=sys.stderr)
            continue

        if delay_seconds > 0 and index < len(to_publish) - 1:
            time.sleep(delay_seconds)

    print(f"Terminé. {published} publication(s).")


if __name__ == "__main__":
    main()
