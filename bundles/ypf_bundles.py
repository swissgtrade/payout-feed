#!/usr/bin/env python3
"""
Swiss Firmup – création automatique des comptes des bundles « 4 accounts (-5%) ».

Toutes les N minutes (Planificateur de tâches Windows / cron) :
  1. lit les commandes payées récentes via l'API YourPropFirm ;
  2. repère les bundles « 4 comptes » ;
  3. complète le client jusqu'à 4 comptes dans le même programme que le compte
     créé par le checkout.

Sûr à relancer : avant de créer quoi que ce soit, le script compte les comptes
du client déjà liés à la commande (même invoiceId ou compte d'origine) et ne crée
que ce qui manque. Aucune dépendance externe : Python 3.8+ suffit.

Usage :
  python ypf_bundles.py                 # utilise config.json à côté du script
  python ypf_bundles.py --dry-run       # force la simulation (ne crée rien)
  python ypf_bundles.py --live          # force le mode réel (crée les comptes)
  python ypf_bundles.py --config autre.json

Variables d'environnement (prioritaires sur config.json) :
  YPF_API_KEY        clé API client YourPropFirm
  YPF_API_BASE_URL   adresse de l'API (production ou sandbox)
"""
import argparse
import json
import logging
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
log = logging.getLogger("ypf_bundles")


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
def load_config(path):
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    # La clé peut venir d'une variable d'environnement (recommandé) plutôt que du fichier.
    cfg["api_key"] = os.environ.get("YPF_API_KEY") or cfg.get("api_key", "")
    # Idem pour l'adresse de l'API (permet de basculer production / sandbox sans toucher au fichier).
    cfg["api_base_url"] = os.environ.get("YPF_API_BASE_URL") or cfg.get("api_base_url", "")
    if not cfg["api_key"] or cfg["api_key"].startswith("COLLEZ"):
        sys.exit("Clé API manquante : définissez YPF_API_KEY ou remplissez api_key dans config.json")
    cfg.setdefault("dry_run", True)
    cfg.setdefault("bundle_size", 4)
    cfg.setdefault("lookback_minutes", 180)
    cfg.setdefault("income_per_extra_account", 0)
    cfg.setdefault("max_accounts_created_per_run", 30)
    cfg.setdefault("bundle_name_pattern", r"4\s*accounts?")
    cfg.setdefault("bundle_products", {})
    if not cfg.get("start_at"):
        sys.exit("start_at manquant dans config.json (ex. 2026-11-14T00:00:00Z)")
    return cfg


def parse_dt(value):
    if not value:
        return None
    v = value.replace("Z", "+00:00")
    # Python < 3.11 n'accepte pas plus de 6 décimales
    v = re.sub(r"(\.\d{6})\d+", r"\1", v)
    dt = datetime.fromisoformat(v)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


# --------------------------------------------------------------------------- #
# Client API YourPropFirm
# --------------------------------------------------------------------------- #
class YpfApi:
    def __init__(self, base_url, api_key):
        self.base = base_url.rstrip("/")
        self.key = api_key

    def _call(self, method, path, query=None, body=None):
        url = self.base + path
        if query:
            url += "?" + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("X-Client-Key", self.key)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode() or "null"
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:500]
            raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {detail}") from None

    def list_paid_orders(self, since, until):
        """Commandes payées dont updatedAt est dans la fenêtre (pagination 50 par 50)."""
        out, offset = [], 0
        while True:
            page = self._call("GET", "/productorder", {
                "statuses": "Completed", "from": iso(since), "to": iso(until),
                "limit": 50, "offset": offset,
            })
            results = (page or {}).get("results") or []
            out.extend(results)
            if len(results) < 50:
                return out
            offset += 50

    def list_user_accounts(self, user_id):
        return self._call("GET", f"/users/{urllib.parse.quote(user_id)}/accounts") or []

    def create_account(self, user_id, payload):
        return self._call("POST", f"/users/{urllib.parse.quote(user_id)}/accounts", body=payload)


# --------------------------------------------------------------------------- #
# Logique métier
# --------------------------------------------------------------------------- #
def is_bundle(order, cfg):
    """Vrai si la commande est un bundle « 4 accounts »."""
    name = order.get("productName") or ""
    if re.search(cfg["bundle_name_pattern"], name, re.I):
        return True
    # Repli : produit connu + prix avant coupon >= prix du bundle
    rule = cfg["bundle_products"].get(order.get("productId") or "")
    if rule:
        gross = order.get("subTotal")
        if gross is None:
            gross = (order.get("amount") or 0) + (order.get("discount") or 0)
        return float(gross) >= float(rule["bundle_price"]) - 0.5
    return False


def process(cfg, api):
    now = datetime.now(timezone.utc)
    start_at = parse_dt(cfg["start_at"])
    since = max(now - timedelta(minutes=cfg["lookback_minutes"]), start_at)
    if since >= now:
        log.info("start_at est dans le futur : rien à faire pour l'instant.")
        return 0
    dry = cfg["dry_run"]
    size = int(cfg["bundle_size"])
    budget = int(cfg["max_accounts_created_per_run"])
    created_total = 0

    orders = api.list_paid_orders(since, now)
    log.info("%d commande(s) payée(s) entre %s et %s", len(orders), iso(since), iso(now))

    for o in orders:
        if (o.get("paymentStatus") or "").lower() != "completed":
            continue
        paid = parse_dt(o.get("paidAt") or o.get("createdAt"))
        if paid and paid < start_at:
            continue
        if not is_bundle(o, cfg):
            continue

        inv, uid = o.get("invoiceId"), o.get("userId")
        who = f"{o.get('userFirstName','')} {o.get('userLastName','')} <{o.get('userEmail','')}>".strip()
        tag = f"[commande {inv} · {o.get('productName')} · {who}]"
        if not inv or not uid:
            log.warning("%s invoiceId ou userId manquant – ignorée", tag)
            continue

        accounts = api.list_user_accounts(uid)
        linked = {a["id"]: a for a in accounts
                  if a.get("id") and (a.get("id") == o.get("accountId") or (a.get("invoiceId") and a.get("invoiceId") == inv))}
        base = linked.get(o.get("accountId")) or next(iter(linked.values()), None)
        if base is None:
            log.info("%s compte du checkout pas encore créé – réessai au prochain passage", tag)
            continue
        missing = size - len(linked)
        if missing <= 0:
            log.info("%s déjà complet (%d comptes)", tag, len(linked))
            continue
        if missing > budget:
            log.error("%s il manque %d comptes mais la limite de sécurité restante est %d – arrêt", tag, missing, budget)
            break

        payload = {
            "mtVersion": base.get("version") or "Volumetrica",
            "programId": base["programId"],
            "invoiceId": inv,
            "productId": o.get("productId"),
            "currency": o.get("currency") or base.get("currency"),
            "income": cfg["income_per_extra_account"],
        }
        log.info("%s %d compte(s) existant(s) – création de %d compte(s) programme=%s plateforme=%s%s",
                 tag, len(linked), missing, payload["programId"], payload["mtVersion"],
                 "  [SIMULATION]" if dry else "")
        for i in range(missing):
            if dry:
                continue
            acc = api.create_account(uid, payload)
            log.info("%s   ✔ compte créé %s/%s : id=%s login=%s", tag, i + 1, missing,
                     (acc or {}).get("id"), (acc or {}).get("login"))
            created_total += 1
            budget -= 1

    log.info("Terminé : %d compte(s) créé(s)%s", created_total, " (simulation)" if dry else "")
    return created_total


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=os.path.join(HERE, "config.json"))
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="simulation : n'appelle jamais la création de compte")
    mode.add_argument("--live", action="store_true", help="mode réel : crée les comptes même si dry_run vaut true dans la config")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout),
                  logging.FileHandler(os.path.join(HERE, "ypf_bundles.log"), encoding="utf-8")],
    )
    cfg = load_config(args.config)
    if args.dry_run:
        cfg["dry_run"] = True
    elif args.live:
        cfg["dry_run"] = False
    log.info("Mode : %s · API : %s", "SIMULATION" if cfg["dry_run"] else "RÉEL", cfg["api_base_url"])
    api = YpfApi(cfg["api_base_url"], cfg["api_key"])
    try:
        process(cfg, api)
    except Exception as e:  # noqa: BLE001
        log.exception("Erreur : %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
