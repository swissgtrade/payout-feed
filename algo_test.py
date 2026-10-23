"""Test en lecture seule de l'API YPF pour le classement des comptes algo.

Lancé à la main depuis GitHub Actions (workflow algo-test.yml). Le dépôt étant public,
les journaux le sont aussi : le script n'affiche que la structure des réponses, les
noms de compte BOT- et des valeurs numériques. Jamais d'email, de nom ni de mot de passe.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import requests

from sync import api_headers, env

PROGRAM = os.getenv("ALGO_PROGRAM", "")  # vide = tous les programmes, filtre sur le nom seul
PREFIX = os.getenv("ALGO_PREFIX", "BOT-")
STATUSES = [s.strip() for s in os.getenv("ALGO_STATUSES", "Active").split(",") if s.strip()]
HISTORY_DAYS = int(os.getenv("ALGO_HISTORY_DAYS", "7"))

# Chaînes affichées telles quelles : aucune ne contient de donnée personnelle.
SAFE_STRINGS = {
    "id", "accountid", "userid", "programid", "state", "currency", "tradeserver", "version",
    "createdat", "updatedat", "timestamp", "opentime", "closetime", "tradesymbol", "command",
    "name", "type", "key",
}


def describe(value, key: str = "") -> str:
    """Type et valeur sans risque pour un champ d'une réponse API."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return f"bool = {value}"
    if isinstance(value, (int, float)):
        return f"{type(value).__name__} = {value}"
    if isinstance(value, str):
        if value.startswith(PREFIX) or key.lower() in SAFE_STRINGS:
            return f"str = {value!r}"
        return f"str ({len(value)} car., masqué)"
    if isinstance(value, list):
        return f"liste de {len(value)} élément(s)"
    if isinstance(value, dict):
        return f"objet ({len(value)} champ(s))"
    return type(value).__name__


def print_fields(title: str, obj, indent: str = "  ") -> None:
    print(f"{indent}{title}")
    if not isinstance(obj, dict):
        print(f"{indent}  {describe(obj)}")
        return
    for key, value in obj.items():
        print(f"{indent}  - {key} : {describe(value, key)}")
        if isinstance(value, dict):
            print_fields(f"{key} :", value, indent + "    ")
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            print_fields(f"{key}[0] :", value[0], indent + "    ")


def as_list(payload) -> list:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return payload.get("results") or payload.get("data") or []
    return []


def call(method: str, url: str, api_key: str, **kwargs):
    short = url.split("/client/", 1)[-1]
    print(f"\n-> {method} /client/{short.split('?')[0]}")
    response = requests.request(method, url, headers=api_headers(api_key), timeout=60, **kwargs)
    if not response.ok:
        print(f"   ERREUR {response.status_code} : {response.text[:300]}")
        return None
    return response.json()


def account_name(account: dict) -> tuple[str, str] | None:
    """Le nom BOT- peut être dans le login ou dans les identifiants Volumetrica."""
    login = str(account.get("login") or "")
    if login.startswith(PREFIX):
        return login, "login"
    for extra in account.get("extraValues") or []:
        value = str((extra or {}).get("Value") or (extra or {}).get("value") or "")
        if value.startswith(PREFIX):
            return value, f"extraValues.{extra.get('Key') or extra.get('key')}"
    return None


def main() -> None:
    base_url = env("API_BASE_URL").rstrip("/") + "/"
    api_key = env("API_KEY")
    v1 = urljoin(base_url, "client/v1/")
    v2 = urljoin(base_url, "client/v2/")

    accounts: list[dict] = []
    for status in STATUSES:
        params = {"status": status, "pageSize": 1000}
        if PROGRAM:
            params["program"] = PROGRAM
        batch = as_list(call("GET", v1 + "tenant/accounts", api_key, params=params))
        print(f"   {len(batch)} compte(s) {status}"
              + ("  (1000 = plafond de l'API, liste peut-être incomplète)" if len(batch) >= 1000 else ""))
        accounts += batch

    bots = [(a, *n) for a in accounts if (n := account_name(a))]
    print(f"\n{len(accounts)} compte(s) au total, {len(bots)} commençant par '{PREFIX}'")
    print(f"programId des comptes {PREFIX} : {sorted({str(b[0].get('programId')) for b in bots})}")
    for account, name, field in bots:
        print(f"  {name:<14} (via {field}) state={account.get('state')} "
              f"balance={account.get('balance')} equity={account.get('equity')} "
              f"maxDrawDown={account.get('maxDrawDown')}")

    if not accounts:
        return
    if not bots:
        print("\nAucun compte BOT- : structure du premier compte pour voir où est le nom.")
        print_fields("Compte (liste) :", accounts[0])
        return

    account = bots[0][0]
    print(f"\n=== Détail sur {bots[0][1]} ===")
    print_fields("Compte (liste) :", account)

    user_id, account_id = account.get("userId"), account.get("id")
    detail = call("GET", v1 + f"users/{user_id}/accounts/{account_id}", api_key)
    if detail is not None:
        print_fields("Compte (détail) :", detail)

    daily = as_list(call("POST", v1 + "daily-reports", api_key, json={"accountId": account_id}))
    print(f"   {len(daily)} rapport(s) journalier(s)")
    for report in daily[:3]:
        print_fields("Rapport :", report)

    now = datetime.now(timezone.utc)
    window = {
        "from": (now - timedelta(days=HISTORY_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "to": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    trades = as_list(call("GET", v2 + f"users/{user_id}/accounts/{account_id}/history",
                          api_key, params=window))
    print(f"   {len(trades)} trade(s) sur {HISTORY_DAYS} jours")
    if trades:
        print_fields("Trade :", trades[0])


if __name__ == "__main__":
    main()
