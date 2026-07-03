#!/usr/bin/env python3
"""
predict-tempo — scrapers/scraper_vl.py

Scraper unifié des Valeurs Liquidatives :
  • VL courante + YTD          → depuis Boursorama (page OPCVM)
  • Historique mensuel (1 an)  → via GetTicksEOD Boursorama

Sortie : data/funds_vl.json
  {
    "last_updated": "YYYY-MM-DD",
    "funds": {
      "FR0013287315": {
        "vl": 642.78,
        "ytd": 0.88,
        "vl_date": "2026-07-03",
        "history": [
          {"date": "2025-07", "vl": 635.12},
          ...
          {"date": "2026-06", "vl": 641.50}
        ]
      },
      ...
    }
  }

Usage :
  python -m scrapers.scraper_vl          # pipeline complet
  python -m scrapers.scraper_vl --quick  # VL courante uniquement (pas d'historique)
"""

from __future__ import annotations
import json
import re
import time
import gzip
import datetime
import argparse
import urllib.request
import urllib.error
import http.cookiejar
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.funds_meta import FUNDS

# ── Constantes ───────────────────────────────────────────────────────────────

_EPOCH = datetime.date(1970, 1, 1)
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "funds_vl.json")

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

HEADERS_HTML = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

HEADERS_XHR = {
    "User-Agent": UA,
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "X-Requested-With": "XMLHttpRequest",
}

# Patterns VL (cours courant)
_PRICE_PATTERNS = [
    re.compile(r'"currentPrice"\s*:\s*([\d,\.]+)', re.IGNORECASE),
    re.compile(r'"last"\s*:\s*([\d,\.]+)', re.IGNORECASE),
    re.compile(r'data-ist-last="([^"]+)"', re.IGNORECASE),
    re.compile(r'class="[^"]*c-instrument--last[^"]*"[^>]*>\s*([\d\s,\.]+)', re.IGNORECASE),
]

# Patterns YTD
_YTD_PATTERNS = [
    re.compile(r'FONDS\s*</th>\s*<td[^>]*>\s*([-+\d,\.]+)\s*%', re.IGNORECASE | re.DOTALL),
    re.compile(r'"ytdReturn"\s*:\s*"?([-\d\.]+)"?', re.IGNORECASE),
    re.compile(r'1\s+jan\.?\s*[-–]\s*auj\.?\s*[:\s]+([-\d,\.]+)\s*%', re.IGNORECASE),
    re.compile(r'Depuis\s+le\s+1er\s+jan\.?\s*[:\s]+([-\d,\.]+)\s*%', re.IGNORECASE),
]


# ── Utilitaires ──────────────────────────────────────────────────────────────

def _clean_number(s: str) -> float | None:
    s = str(s).strip().replace('\xa0', '').replace(' ', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


def _decode(resp) -> str:
    raw = resp.read()
    if resp.headers.get("Content-Encoding", "") == "gzip":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="replace")


def _bourso_url(bid: str) -> str:
    return f"https://www.boursorama.com/bourse/opcvm/cours/{bid}/"


# ── Scraping VL courante ─────────────────────────────────────────────────────

def fetch_current_vl(bid: str, opener) -> dict | None:
    """Récupère VL et YTD depuis la page Boursorama du fonds."""
    url = _bourso_url(bid)
    try:
        req = urllib.request.Request(url, headers=HEADERS_HTML)
        with opener.open(req, timeout=15) as resp:
            html = _decode(resp)
    except Exception as e:
        print(f"    ✗ réseau : {e}")
        return None

    vl = None
    for pat in _PRICE_PATTERNS:
        m = pat.search(html)
        if m:
            v = _clean_number(m.group(1))
            if v and v > 0:
                vl = v
                break

    ytd = None
    for pat in _YTD_PATTERNS:
        m = pat.search(html)
        if m:
            v = _clean_number(m.group(1))
            if v is not None:
                ytd = v
                break

    if vl:
        return {"vl": vl, "ytd": ytd}
    print(f"    ✗ VL non trouvée dans la page")
    return None


# ── Scraping historique mensuel ───────────────────────────────────────────────

def fetch_history(bid: str, opener) -> list | None:
    """Récupère l'historique mensuel via l'API GetTicksEOD de Boursorama."""
    base_url = _bourso_url(bid)
    api_url = (
        f"https://www.boursorama.com/bourse/action/graph/ws/GetTicksEOD"
        f"?symbol={bid}&length=365&period=0&guid="
    )
    # Visite d'abord la page pour poser les cookies
    try:
        req = urllib.request.Request(base_url, headers=HEADERS_HTML)
        with opener.open(req, timeout=20) as resp:
            _decode(resp)
    except Exception:
        pass  # on tente quand même l'API

    headers_xhr = {**HEADERS_XHR, "Referer": base_url}
    try:
        req = urllib.request.Request(api_url, headers=headers_xhr)
        with opener.open(req, timeout=20) as resp:
            raw = _decode(resp)
        if not raw.strip():
            return None
        data = json.loads(raw)
        return _parse_ticks(data)
    except (json.JSONDecodeError, Exception) as e:
        print(f"    ✗ historique : {e}")
        return None


def _parse_ticks(data) -> list | None:
    """Convertit la réponse GetTicksEOD → liste mensuelle triée."""
    series = None
    if isinstance(data, list):
        series = data
    elif isinstance(data, dict):
        d_val = data.get("d")
        if isinstance(d_val, list):
            series = d_val
        elif isinstance(d_val, dict) and "QuoteTab" in d_val:
            series = d_val["QuoteTab"]
        if series is None:
            try:
                series = data["DataSet"]["Series"][0]["Value"]
            except (KeyError, IndexError, TypeError):
                pass

    if not series:
        return None

    monthly: dict[str, float] = {}
    for pt in series:
        if not isinstance(pt, dict):
            continue
        raw_date = pt.get("d") or pt.get("Date") or pt.get("date") or pt.get("t")
        raw_val  = (pt.get("c") or pt.get("close") or pt.get("Value")
                    or pt.get("value") or pt.get("o"))
        if raw_date is None or raw_val is None:
            continue
        try:
            d = (_EPOCH + datetime.timedelta(days=int(raw_date))
                 if isinstance(raw_date, int)
                 else datetime.date.fromisoformat(str(raw_date).split("T")[0]))
        except (ValueError, OverflowError):
            continue
        try:
            val = float(raw_val)
        except (ValueError, TypeError):
            continue
        if val <= 0:
            continue
        monthly[d.strftime("%Y-%m")] = val

    if not monthly:
        return None
    return [{"date": k, "vl": v} for k, v in sorted(monthly.items())]


# ── Pipeline principal ────────────────────────────────────────────────────────

def scrape_vl(quick: bool = False) -> dict:
    """
    Lance le scraping pour tous les fonds.
    quick=True : VL courante uniquement (pas d'historique).
    Retourne le dict funds_vl complet.
    """
    today = datetime.date.today().isoformat()

    # Charge les données existantes (pour conserver l'historique en cas d'échec)
    existing: dict = {}
    if os.path.exists(DATA_PATH):
        try:
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f).get("funds", {})
            print(f"↩  Données existantes : {len(existing)} fonds")
        except Exception as e:
            print(f"⚠  Lecture existant : {e}")

    results: dict = {}
    ok = ko = 0

    print(f"\n{'─'*60}")
    print(f"Scraping VL — {today} — {len(FUNDS)} fonds"
          + (" (mode rapide)" if quick else ""))
    print(f"{'─'*60}")

    for i, fund in enumerate(FUNDS, 1):
        isin = fund["isin"]
        bid  = fund["bid"]
        name = fund["name"]
        print(f"[{i:2}/{len(FUNDS)}] {isin}  {name[:40]}")

        # Opener avec cookies par fonds
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cj),
            urllib.request.HTTPSHandler(),
        )

        entry = existing.get(isin, {}).copy()

        # VL courante
        current = fetch_current_vl(bid, opener)
        if current:
            entry["vl"]       = current["vl"]
            entry["ytd"]      = current["ytd"]
            entry["vl_date"]  = today
            print(f"    VL={current['vl']}  YTD={current['ytd']}%")
            ok += 1
        else:
            ko += 1

        # Historique mensuel
        if not quick:
            time.sleep(0.5)  # pause entre page et API
            hist = fetch_history(bid, opener)
            if hist and len(hist) >= 3:
                entry["history"] = hist
                print(f"    historique : {len(hist)} mois ({hist[0]['date']} → {hist[-1]['date']})")
            elif "history" in existing.get(isin, {}):
                entry["history"] = existing[isin]["history"]
                print(f"    historique : conservé ({len(entry['history'])} mois)")

        results[isin] = entry
        time.sleep(1.0 if not quick else 0.5)

    print(f"\n{'─'*60}")
    print(f"✅ {ok} VL récupérées  |  ✗ {ko} échecs")

    output = {"last_updated": today, "funds": results}
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"💾 Sauvegardé → {DATA_PATH}")

    return output


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="predict-tempo — scraper VL")
    parser.add_argument("--quick", action="store_true",
                        help="VL courante uniquement, sans historique mensuel")
    args = parser.parse_args()
    scrape_vl(quick=args.quick)
