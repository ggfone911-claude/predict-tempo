#!/usr/bin/env python3
"""
predict-tempo — scoring/momentum.py

Calcul des indicateurs quantitatifs de momentum pour chaque fonds.
Utilise l'historique mensuel de data/funds_vl.json.

Métriques calculées par fonds :
  ret_1m     : rendement dernier mois (%)
  ret_3m     : rendement 3 derniers mois (%)
  ret_6m     : rendement 6 derniers mois (%)
  ret_1y     : rendement 12 derniers mois (%)
  ytd        : rendement depuis le 01/01 de l'année en cours (%)
  volatility : écart-type des rendements mensuels (annualisé, %)
  max_dd     : drawdown maximum sur la période disponible (%)
  pos_ratio  : % de mois à rendement positif
  sharpe     : rendement 6M annualisé / volatilité (approximation)
  acceleration : ret_3m - (ret_6m - ret_3m)  → momentum accélère si > 0
  n_months   : nombre de mois d'historique disponibles

Score momentum (0–10) :
  Calculé en 2 passes :
  1. Score brut = combinaison pondérée des métriques normalisées
  2. Score final = rang percentile au sein de la catégorie → 0-10
     (un 10 = meilleur momentum de sa catégorie)

Pondérations par défaut :
  ret_1m       : 15 %
  ret_3m       : 30 %
  ret_6m       : 20 %
  ret_1y       : 15 %
  pos_ratio    : 10 %
  sharpe       : 10 %
"""

import json
import math
import os
import sys
import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.funds_meta import FUNDS, CATEGORIES

VL_PATH     = os.path.join(os.path.dirname(__file__), "..", "data", "funds_vl.json")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "momentum.json")

# Pondérations du score composite
WEIGHTS = {
    "ret_1m":    0.15,
    "ret_3m":    0.30,
    "ret_6m":    0.20,
    "ret_1y":    0.15,
    "pos_ratio": 0.10,
    "sharpe":    0.10,
}


# ── Calculs de base ───────────────────────────────────────────────────────────

def _pct_return(vl_start: float, vl_end: float) -> float | None:
    if vl_start and vl_end and vl_start > 0:
        return round((vl_end / vl_start - 1) * 100, 4)
    return None


def _monthly_returns(history: list[dict]) -> list[float]:
    """Calcule la liste des rendements mensuels (%) depuis l'historique trié."""
    rets = []
    for i in range(1, len(history)):
        v0 = history[i - 1]["vl"]
        v1 = history[i]["vl"]
        if v0 and v0 > 0:
            rets.append((v1 / v0 - 1) * 100)
    return rets


def _std(values: list[float]) -> float | None:
    n = len(values)
    if n < 2:
        return None
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return math.sqrt(variance)


def _max_drawdown(history: list[dict]) -> float | None:
    """Drawdown maximum (%) sur toute la série historique."""
    if len(history) < 2:
        return None
    peak = history[0]["vl"]
    max_dd = 0.0
    for pt in history[1:]:
        vl = pt["vl"]
        if vl > peak:
            peak = vl
        dd = (peak - vl) / peak * 100
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 4) if max_dd > 0 else 0.0


def _ytd(history: list[dict]) -> float | None:
    """Rendement depuis le 1er janvier de l'année en cours."""
    year = datetime.date.today().year
    jan_key = f"{year}-01"
    dec_prev_key = f"{year - 1}-12"

    # VL de référence : dernier point de déc N-1 ou premier de jan N
    ref_vl = None
    for pt in history:
        if pt["date"] == dec_prev_key:
            ref_vl = pt["vl"]
            break
    if ref_vl is None:
        for pt in history:
            if pt["date"] == jan_key:
                ref_vl = pt["vl"]
                break

    if ref_vl is None:
        return None

    # VL courante = dernier point disponible
    last_vl = history[-1]["vl"]
    return _pct_return(ref_vl, last_vl)


# ── Calcul des métriques d'un fonds ──────────────────────────────────────────

def compute_metrics(history: list[dict], ytd_override: float | None = None) -> dict:
    """
    Calcule toutes les métriques momentum pour un fonds à partir de son historique.
    ytd_override : valeur YTD déjà scrappée depuis Boursorama (prioritaire).
    """
    if not history or len(history) < 2:
        return {}

    # Tri chronologique
    hist = sorted(history, key=lambda x: x["date"])
    n = len(hist)

    metrics: dict = {"n_months": n}

    # Rendements sur différentes fenêtres
    last_vl = hist[-1]["vl"]
    for label, offset in [("ret_1m", 1), ("ret_3m", 3), ("ret_6m", 6), ("ret_1y", 12)]:
        if n > offset:
            metrics[label] = _pct_return(hist[-(offset + 1)]["vl"], last_vl)
        else:
            metrics[label] = None

    # YTD
    metrics["ytd"] = ytd_override if ytd_override is not None else _ytd(hist)

    # Rendements mensuels
    monthly_rets = _monthly_returns(hist)

    # Volatilité annualisée (√12)
    std = _std(monthly_rets)
    metrics["volatility"] = round(std * math.sqrt(12), 4) if std else None

    # Max drawdown
    metrics["max_dd"] = _max_drawdown(hist)

    # % mois positifs
    if monthly_rets:
        pos = sum(1 for r in monthly_rets if r > 0)
        metrics["pos_ratio"] = round(pos / len(monthly_rets) * 100, 2)
    else:
        metrics["pos_ratio"] = None

    # Sharpe approximatif : rendement 6M annualisé / volatilité
    ret_6m = metrics.get("ret_6m")
    vol    = metrics.get("volatility")
    if ret_6m is not None and vol and vol > 0:
        ret_6m_ann = ret_6m * 2   # annualisé × 2 (6M → 12M)
        metrics["sharpe"] = round(ret_6m_ann / vol, 4)
    else:
        metrics["sharpe"] = None

    # Accélération : est-ce que le momentum récent (3M) > la moyenne historique ?
    ret_3m = metrics.get("ret_3m")
    if ret_3m is not None and ret_6m is not None:
        # ret derniers 3M vs ret 3M précédents = (ret_6m - ret_3m)
        prior_3m = ret_6m - ret_3m
        metrics["acceleration"] = round(ret_3m - prior_3m, 4)
    else:
        metrics["acceleration"] = None

    return metrics


# ── Normalisation et score ────────────────────────────────────────────────────

def _percentile_rank(value: float, all_values: list[float]) -> float:
    """Rang percentile de value dans all_values → [0, 100]."""
    if not all_values:
        return 50.0
    below = sum(1 for v in all_values if v < value)
    return below / len(all_values) * 100


def _normalize_series(values: dict[str, float | None]) -> dict[str, float]:
    """
    Normalise une série de valeurs {isin: val} en rang percentile [0, 100].
    Les valeurs None sont ignorées (gardées à None dans la sortie).
    """
    valid = {k: v for k, v in values.items() if v is not None}
    if not valid:
        return {k: None for k in values}
    all_vals = list(valid.values())
    return {
        k: (_percentile_rank(v, all_vals) if v is not None else None)
        for k, v in values.items()
    }


def compute_momentum_scores(metrics_by_isin: dict) -> dict[str, float | None]:
    """
    Calcule les scores momentum 0-10 pour chaque fonds.
    Le score est relatif à TOUS les fonds (pas par catégorie)
    pour permettre la comparaison cross-catégorie.
    Un score de 10 = meilleur momentum absolu.
    Un score de 5  = fonds médian.
    """
    # Normalise chaque métrique en rang percentile sur l'ensemble des fonds
    normalized: dict[str, dict] = {}
    for metric, weight in WEIGHTS.items():
        series = {isin: m.get(metric) for isin, m in metrics_by_isin.items()}
        normalized[metric] = _normalize_series(series)

    # Score brut = somme pondérée des percentiles (dans [0, 100])
    raw_scores: dict[str, float | None] = {}
    for isin in metrics_by_isin:
        total_w = 0.0
        score   = 0.0
        for metric, weight in WEIGHTS.items():
            val = normalized[metric].get(isin)
            if val is not None:
                score   += val * weight
                total_w += weight
        if total_w >= 0.3:   # au moins 30 % des métriques disponibles
            raw_scores[isin] = round(score / total_w, 2)  # normalisé à [0, 100]
        else:
            raw_scores[isin] = None

    # Convertit [0, 100] → [0, 10]
    return {
        isin: round(s / 10, 2) if s is not None else None
        for isin, s in raw_scores.items()
    }


# ── Score par catégorie (rang relatif intra-catégorie) ────────────────────────

def compute_cat_ranks(metrics_by_isin: dict, funds_meta: list) -> dict[str, float | None]:
    """
    Score 0-10 relatif à la catégorie du fonds.
    Utile pour identifier les pépites dans une catégorie donnée.
    """
    # Groupe les ISIN par catégorie
    by_cat: dict[str, list[str]] = {}
    meta_idx = {f["isin"]: f for f in funds_meta}
    for isin in metrics_by_isin:
        cat = meta_idx.get(isin, {}).get("cat_id", "other")
        by_cat.setdefault(cat, []).append(isin)

    cat_scores: dict[str, float | None] = {}
    for cat, isins in by_cat.items():
        cat_metrics = {i: metrics_by_isin[i] for i in isins if i in metrics_by_isin}
        cat_s = compute_momentum_scores(cat_metrics)
        cat_scores.update(cat_s)

    return cat_scores


# ── Pipeline principal ────────────────────────────────────────────────────────

def run_momentum(vl_data: dict | None = None) -> dict:
    """
    Calcule les métriques et scores momentum pour tous les fonds.
    vl_data : dict issu de funds_vl.json (si None, charge depuis disque).
    Retourne le dict complet et sauvegarde dans data/momentum.json.
    """
    if vl_data is None:
        if not os.path.exists(VL_PATH):
            raise FileNotFoundError(
                f"Fichier VL manquant : {VL_PATH}\n"
                "Lance d'abord : python -m scrapers.scraper_vl"
            )
        with open(VL_PATH, "r", encoding="utf-8") as f:
            vl_data = json.load(f)

    funds_data = vl_data.get("funds", {})
    print(f"\n{'─'*60}")
    print(f"Calcul momentum — {len(FUNDS)} fonds")
    print(f"{'─'*60}")

    metrics_by_isin: dict = {}
    skipped = 0

    for fund in FUNDS:
        isin = fund["isin"]
        fd   = funds_data.get(isin, {})
        hist = fd.get("history", [])
        ytd  = fd.get("ytd")

        if len(hist) < 3:
            print(f"  ⚠  {isin} — historique insuffisant ({len(hist)} mois), ignoré")
            skipped += 1
            metrics_by_isin[isin] = {}
            continue

        m = compute_metrics(hist, ytd_override=ytd)
        metrics_by_isin[isin] = m

        print(
            f"  {isin}  "
            f"1M={m.get('ret_1m','-'):>7}%  "
            f"3M={m.get('ret_3m','-'):>7}%  "
            f"6M={m.get('ret_6m','-'):>7}%  "
            f"vol={m.get('volatility','-'):>6}%  "
            f"sharpe={m.get('sharpe','-'):>5}"
        )

    print(f"\n  {len(metrics_by_isin) - skipped} fonds calculés, {skipped} ignorés")

    # Scores globaux (0-10, toutes catégories confondues)
    print("\n→ Calcul des scores momentum globaux…")
    global_scores = compute_momentum_scores(metrics_by_isin)

    # Scores relatifs par catégorie (0-10 dans la catégorie)
    print("→ Calcul des scores par catégorie…")
    cat_scores = compute_cat_ranks(metrics_by_isin, FUNDS)

    # Assemblage final
    today = datetime.date.today().isoformat()
    result: dict = {
        "last_updated": today,
        "scores": {}
    }

    for fund in FUNDS:
        isin = fund["isin"]
        result["scores"][isin] = {
            "isin":       isin,
            "name":       fund["name"],
            "cat_id":     fund["cat_id"],
            "srri":       fund["srri"],
            "metrics":    metrics_by_isin.get(isin, {}),
            "score_global": global_scores.get(isin),
            "score_cat":    cat_scores.get(isin),
        }

    # Top 10 global
    ranked = sorted(
        [(isin, d["score_global"]) for isin, d in result["scores"].items()
         if d["score_global"] is not None],
        key=lambda x: x[1], reverse=True
    )
    print(f"\n{'─'*60}")
    print("TOP 10 momentum (toutes catégories) :")
    for rank, (isin, score) in enumerate(ranked[:10], 1):
        name = result["scores"][isin]["name"]
        print(f"  {rank:2}. {score:.1f}/10  {name[:50]}")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Sauvegardé → {OUTPUT_PATH}")

    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_momentum()
