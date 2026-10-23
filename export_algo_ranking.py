"""Classement des comptes algo (BOT-) pour la page Compte Algo du site statique.

Lit les comptes YPF dont le login commence par BOT-, garde ceux en gain, calcule
6 critères notés sur 100 et écrit algo-ranking.json (lu par le site).
Aucune donnée personnelle ni le prix payé ne sont écrits : le dépôt est public.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests

from sync import CONFIG_PATH, api_headers, env, load_json

ROOT = Path(__file__).resolve().parent

DEFAULTS = {
    "prefix": "BOT-",
    "statuses": ["Active"],
    "initial_balance": 5000,
    "top_n": 10,
    "period_start": None,
    "period_end": None,
    "day_start_utc_hour": 22,
    # Le Sharpe est instable sur peu de jours : ses points montent jusqu'à ce nombre de jours tradés.
    "sharpe_full_days": 10,
    "output_file": "algo-ranking.json",
    # [clé, points, valeur à 0 point, valeur au maximum]
    "criteria": [
        ["net_profit", 25, 0, 2500],
        ["profit_factor", 15, 1, 3],
        ["max_drawdown", 25, 2500, 250],
        ["sharpe", 15, 0, 3],
        ["positive_days", 10, 40, 80],
        ["best_day_share", 10, 80, 20],
    ],
}


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    # YPF renvoie parfois 5 ou 7 décimales, que fromisoformat de Python 3.10 refuse.
    if "." in text:
        head, tail = text.split(".", 1)
        digits = "".join(ch for ch in tail if ch.isdigit())
        zone = tail[len(digits):]
        text = f"{head}.{digits[:6].ljust(6, '0')}{zone}"
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def as_list(payload) -> list:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return payload.get("results") or payload.get("data") or []
    return []


def api_get(url: str, api_key: str, params: dict) -> list:
    response = requests.get(url, headers=api_headers(api_key), params=params, timeout=60)
    response.raise_for_status()
    return as_list(response.json())


def fraction(value: float | None, zero: float, full: float) -> float:
    """Part des points obtenus, linéaire entre la valeur à 0 point et la valeur au maximum."""
    if value is None:
        return 0.0
    ratio = (value - zero) / (full - zero)
    return min(1.0, max(0.0, ratio))


def trading_day(moment: datetime, day_start_hour: int) -> str:
    """Une séance futures commence le soir (22h UTC par défaut) et compte pour le lendemain."""
    return (moment + timedelta(hours=24 - day_start_hour)).date().isoformat()


def market(symbol: str) -> str:
    return (symbol or "").split(".")[0].upper()


def compute_stats(account: dict, trades: list[dict], cfg: dict, start: datetime) -> dict:
    initial = float(cfg["initial_balance"])
    balance = float(account.get("balance") or 0)
    net_profit = round(balance - initial, 2)

    daily: dict[str, float] = defaultdict(float)
    gross_win = gross_loss = 0.0
    closed = []
    for trade in trades:
        close_time = parse_time(trade.get("closeTime"))
        if close_time is None:
            continue
        result = float(trade.get("profit") or 0) - float(trade.get("commission") or 0)
        closed.append((close_time, result, trade))
        daily[trading_day(close_time, cfg["day_start_utc_hour"])] += result
        if result > 0:
            gross_win += result
        else:
            gross_loss += -result
    closed.sort(key=lambda item: item[0])

    # Drawdown sur la courbe des trades clôturés.
    level = peak = initial
    curve_drawdown = 0.0
    for _, result, _ in closed:
        level += result
        peak = max(peak, level)
        curve_drawdown = max(curve_drawdown, peak - level)
    # Drawdown YPF, en % depuis le plus haut d'equity : il inclut l'intraday.
    equity_high = max(float(account.get("lastEquityHigh") or 0), initial)
    ypf_drawdown = float(account.get("maxDrawDown") or 0) / 100 * equity_high
    max_drawdown = round(max(curve_drawdown, ypf_drawdown), 2)

    days = sorted(daily)
    day_results = [daily[d] for d in days]
    positive_days = round(100 * sum(1 for r in day_results if r > 0) / len(days), 1) if days else None

    trades_total = sum(day_results)
    best_day = max(day_results) if day_results else None
    best_day_share = (
        round(100 * best_day / trades_total, 1) if best_day is not None and trades_total > 0 else None
    )

    sharpe = None
    if len(day_results) >= 2:
        returns = [r / initial for r in day_results]
        mean = sum(returns) / len(returns)
        std = math.sqrt(sum((r - mean) ** 2 for r in returns) / (len(returns) - 1))
        if std > 0:
            sharpe = round(mean / std * math.sqrt(252), 2)

    profit_factor = round(gross_win / gross_loss, 2) if gross_loss > 0 else None
    no_loss = gross_loss == 0 and gross_win > 0

    # Point de départ la veille du premier jour tradé s'il tombe le même jour que l'ouverture.
    first_day = start.date()
    if days and days[0] <= first_day.isoformat():
        first_day = datetime.fromisoformat(days[0]).date() - timedelta(days=1)
    curve = [[first_day.isoformat(), initial]]
    running = initial
    for day in days:
        running += daily[day]
        curve.append([day, round(running, 2)])

    return {
        "net_profit": net_profit,
        "return_pct": round(100 * net_profit / initial, 2),
        "balance": round(balance, 2),
        "max_drawdown": max_drawdown,
        "profit_factor": profit_factor,
        "no_losing_trade": no_loss,
        "sharpe": sharpe,
        "positive_days": positive_days,
        "best_day": round(best_day, 2) if best_day is not None else None,
        "best_day_share": best_day_share,
        "trades": len(closed),
        "days_traded": len(days),
        "markets": sorted({market(t.get("tradeSymbol")) for _, _, t in closed if t.get("tradeSymbol")}),
        "start_date": start.date().isoformat(),
        "curve": curve,
        "_trades_net": round(trades_total, 2),
    }


def score(stats: dict, cfg: dict) -> tuple[int, dict]:
    points = {}
    for key, weight, zero, full in cfg["criteria"]:
        value = stats.get(key)
        if key == "profit_factor" and stats.get("no_losing_trade"):
            value = full
        earned = weight * fraction(value, zero, full)
        if key == "sharpe":
            earned *= min(1.0, stats["days_traded"] / cfg["sharpe_full_days"])
        points[key] = round(earned, 1)
    return round(sum(points.values())), points


def main() -> None:
    base_url = env("API_BASE_URL").rstrip("/") + "/"
    api_key = env("API_KEY")
    config = load_json(CONFIG_PATH, {})
    cfg = {**DEFAULTS, **config.get("algo_ranking", {})}
    v1 = urljoin(base_url, "client/v1/")
    v2 = urljoin(base_url, "client/v2/")

    now = datetime.now(timezone.utc)
    period_start = parse_time(cfg["period_start"])
    period_end = min(parse_time(cfg["period_end"]) or now, now)

    bots = []
    for status in cfg["statuses"]:
        batch = api_get(v1 + "tenant/accounts", api_key, {"status": status, "pageSize": 1000})
        if len(batch) >= 1000:
            print(f"Attention : {status} a atteint le plafond de 1000 comptes, liste incomplète.")
        bots += [a for a in batch if str(a.get("login") or "").startswith(cfg["prefix"])]
    in_gain = [a for a in bots if float(a.get("balance") or 0) > cfg["initial_balance"]]
    print(f"{len(bots)} compte(s) {cfg['prefix']}, dont {len(in_gain)} en gain")

    ranked = []
    for account in in_gain:
        created = parse_time(account.get("createdAt")) or now
        start = max(created, period_start) if period_start else created
        trades = api_get(
            v2 + f"users/{account['userId']}/accounts/{account['id']}/history",
            api_key,
            {"from": iso(start), "to": iso(period_end)},
        )
        stats = compute_stats(account, trades, cfg, start)
        total, points = score(stats, cfg)
        gap = round(stats["net_profit"] - stats.pop("_trades_net"), 2)
        print(
            f"  {account['login']:<22} score {total:>3}  profit {stats['net_profit']:>9}  "
            f"DD {stats['max_drawdown']:>8}  PF {stats['profit_factor']}  Sharpe {stats['sharpe']}  "
            f"jours {stats['days_traded']}  trades {stats['trades']}  écart solde/trades {gap}"
        )
        ranked.append({"id": account["login"], "score": total, "points": points, **stats})

    ranked.sort(key=lambda r: (r["score"], r["net_profit"]), reverse=True)
    ranked = ranked[: int(cfg["top_n"])]
    for position, row in enumerate(ranked, start=1):
        row["rank"] = position

    feed = {
        "updated_at": iso(now),
        "period": {
            "start": period_start.date().isoformat() if period_start else None,
            "end": parse_time(cfg["period_end"]).date().isoformat() if cfg["period_end"] else None,
        },
        "initial_balance": cfg["initial_balance"],
        "criteria": [
            {"key": key, "points": weight, "zero": zero, "full": full,
             **({"full_days": cfg["sharpe_full_days"]} if key == "sharpe" else {})}
            for key, weight, zero, full in cfg["criteria"]
        ],
        "accounts_tracked": len(bots),
        "accounts_in_gain": len(in_gain),
        "ranking": ranked,
    }
    output = ROOT / cfg["output_file"]
    output.write_text(json.dumps(feed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Écrit {output.name} : {len(ranked)} compte(s) classé(s)")


if __name__ == "__main__":
    main()
