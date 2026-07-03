"""
scoring/engine.py — Moteur de scoring final predict-tempo
=========================================================
Combine momentum (quantitatif) + sentiment LLM (macro/news) en score final 0-10
par fonds, avec signal, explication et classements.

Pipeline :
    data/momentum.json + data/sentiment.json → data/scores.json

Usage :
    python scoring/engine.py
    python scoring/engine.py --no-momentum   # sentiment seul (debug)
    python scoring/engine.py --no-sentiment  # momentum seul (debug)
    python scoring/engine.py --json          # dump scores.json sur stdout
"""

from __future__ import annotations
import json
import os
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

# ── Chemins ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
MOMENTUM_PATH  = DATA / "momentum.json"
SENTIMENT_PATH = DATA / "sentiment.json"
SCORES_PATH    = DATA / "scores.json"

# ── Poids de fusion ────────────────────────────────────────────────────────
W_MOMENTUM  = 0.60   # score quantitatif (historique VL)
W_SENTIMENT = 0.40   # score LLM (news + macro)

# ── Seuils de signal ───────────────────────────────────────────────────────
SIGNALS = [
    (8.0,  "fort_achat",   "Fort signal d'achat"),
    (6.5,  "achat",        "Signal d'achat"),
    (5.5,  "neutre_plus",  "Légèrement positif"),
    (4.5,  "neutre",       "Neutre"),
    (3.5,  "neutre_moins", "Légèrement négatif"),
    (2.0,  "vente",        "Signal de vente"),
    (0.0,  "fort_vente",   "Fort signal de vente"),
]


def score_to_signal(score: float | None) -> tuple[str, str]:
    """Retourne (signal_id, label) pour un score 0-10."""
    if score is None:
        return "inconnu", "Données insuffisantes"
    for threshold, sig_id, label in SIGNALS:
        if score >= threshold:
            return sig_id, label
    return "fort_vente", "Fort signal de vente"


def sentiment_to_score(sentiment_value: float | None) -> float | None:
    """
    Convertit la valeur de sentiment (-1 à +1) en score 0-10.
    -1.0 → 0.0 | 0.0 → 5.0 | +1.0 → 10.0
    """
    if sentiment_value is None:
        return None
    return round((sentiment_value + 1.0) * 5.0, 2)


def build_explanation(
    fund: dict,
    score_final: float,
    score_momentum: float | None,
    score_sentiment: float | None,
    sentiment_signal: str | None,
    macro_summary: str | None,
) -> str:
    """Génère un texte d'explication concis pour le score final."""
    parts = []

    sig_id, sig_label = score_to_signal(score_final)
    parts.append(f"{sig_label} ({score_final:.1f}/10).")

    if score_momentum is not None:
        mom_sig, _ = score_to_signal(score_momentum)
        mom_txt = {
            "fort_achat":   "très fort momentum",
            "achat":        "bon momentum",
            "neutre_plus":  "momentum légèrement positif",
            "neutre":       "momentum neutre",
            "neutre_moins": "momentum légèrement faible",
            "vente":        "momentum faible",
            "fort_vente":   "momentum très faible",
        }.get(mom_sig, "momentum incertain")
        parts.append(f"Performance historique : {mom_txt} ({score_momentum:.1f}/10).")

    if score_sentiment is not None and sentiment_signal:
        sent_map = {
            "fort_haussier": "contexte macro/news très favorable",
            "haussier":      "contexte macro/news favorable",
            "neutre+":       "contexte légèrement favorable",
            "neutre":        "contexte neutre",
            "neutre-":       "contexte légèrement défavorable",
            "baissier":      "contexte défavorable",
            "fort_baissier": "contexte très défavorable",
        }
        sent_txt = sent_map.get(sentiment_signal, "contexte incertain")
        parts.append(f"Analyse macro/news : {sent_txt} ({score_sentiment:.1f}/10).")

    if macro_summary:
        parts.append(f"Contexte global : {macro_summary}")

    return " ".join(parts)


def load_momentum() -> dict:
    """Charge data/momentum.json."""
    if not MOMENTUM_PATH.exists():
        print(f"⚠️  {MOMENTUM_PATH} introuvable — momentum ignoré.", file=sys.stderr)
        return {}
    with open(MOMENTUM_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_sentiment() -> dict:
    """Charge data/sentiment.json."""
    if not SENTIMENT_PATH.exists():
        print(f"⚠️  {SENTIMENT_PATH} introuvable — sentiment ignoré.", file=sys.stderr)
        return {}
    with open(SENTIMENT_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_funds_meta() -> list[dict]:
    """Charge la liste des fonds depuis data/funds_meta.py via import."""
    sys.path.insert(0, str(ROOT / "data"))
    from funds_meta import FUNDS  # type: ignore
    return FUNDS


def run_engine(
    use_momentum: bool = True,
    use_sentiment: bool = True,
) -> dict:
    """
    Moteur principal.

    Returns
    -------
    dict : structure complète des scores (prête à sauvegarder dans scores.json)
    """
    print("🔧 predict-tempo — Moteur de scoring final")

    # ── Chargement des données ──────────────────────────────────────────
    momentum_data  = load_momentum()  if use_momentum  else {}
    sentiment_data = load_sentiment() if use_sentiment else {}
    funds_meta     = load_funds_meta()

    momentum_funds  = momentum_data.get("funds", {})
    sentiment_cats  = sentiment_data.get("categories", {})
    global_macro    = sentiment_data.get("global_macro", {})
    macro_summary   = global_macro.get("summary", "")

    # ── Calcul des scores par fonds ─────────────────────────────────────
    fund_scores: list[dict] = []

    for fund in funds_meta:
        isin    = fund["isin"]
        cat_id  = fund["cat_id"]
        srri    = fund.get("srri", 3)

        # — Score momentum (0-10) —
        mom_entry     = momentum_funds.get(isin, {})
        score_global  = mom_entry.get("score_global")   # 0-10 parmi tous les fonds
        score_cat_mom = mom_entry.get("score_cat")      # 0-10 au sein de la catégorie
        metrics       = mom_entry.get("metrics", {})

        # — Score sentiment (0-10) via catégorie —
        cat_sentiment    = sentiment_cats.get(cat_id, {})
        sentiment_value  = cat_sentiment.get("score")   # -1 à +1
        sentiment_signal = cat_sentiment.get("signal")  # ex: "haussier"
        score_sentiment  = sentiment_to_score(sentiment_value)

        # — Fusion momentum + sentiment —
        if score_global is not None and score_sentiment is not None:
            score_final = round(
                W_MOMENTUM * score_global + W_SENTIMENT * score_sentiment, 2
            )
        elif score_global is not None:
            # Pas de sentiment : score momentum seul
            score_final = round(score_global, 2)
        elif score_sentiment is not None:
            # Pas de momentum : score sentiment seul
            score_final = round(score_sentiment, 2)
        else:
            score_final = None

        signal_id, signal_label = score_to_signal(score_final)

        explanation = build_explanation(
            fund=fund,
            score_final=score_final if score_final is not None else 5.0,
            score_momentum=score_global,
            score_sentiment=score_sentiment,
            sentiment_signal=sentiment_signal,
            macro_summary=macro_summary,
        )

        # — Drivers clés (métriques momentum) —
        drivers = []
        if metrics:
            ret1m  = metrics.get("ret_1m")
            ret3m  = metrics.get("ret_3m")
            ytd    = metrics.get("ytd")
            sharpe = metrics.get("sharpe")
            if ret1m  is not None: drivers.append(f"Perf 1 mois : {ret1m*100:.2f}%")
            if ret3m  is not None: drivers.append(f"Perf 3 mois : {ret3m*100:.2f}%")
            if ytd    is not None: drivers.append(f"YTD : {ytd*100:.2f}%")
            if sharpe is not None: drivers.append(f"Sharpe : {sharpe:.2f}")

        fund_scores.append({
            "isin":             isin,
            "name":             fund["name"],
            "cat_id":           cat_id,
            "srri":             srri,
            "score_final":      score_final,
            "score_momentum":   score_global,
            "score_cat_mom":    score_cat_mom,
            "score_sentiment":  score_sentiment,
            "sentiment_signal": sentiment_signal,
            "signal_id":        signal_id,
            "signal_label":     signal_label,
            "explanation":      explanation,
            "drivers":          drivers,
            "metrics":          metrics,
        })

    # ── Classements globaux ─────────────────────────────────────────────
    scored = [f for f in fund_scores if f["score_final"] is not None]
    scored_sorted = sorted(scored, key=lambda x: x["score_final"], reverse=True)

    for rank, f in enumerate(scored_sorted, start=1):
        f["rank_global"] = rank

    # Classements par catégorie
    from collections import defaultdict
    by_cat: dict[str, list] = defaultdict(list)
    for f in scored_sorted:
        by_cat[f["cat_id"]].append(f)

    for cat_funds in by_cat.values():
        for rank, f in enumerate(cat_funds, start=1):
            f["rank_cat"] = rank

    # Fonds sans score (rank = None)
    for f in fund_scores:
        if "rank_global" not in f:
            f["rank_global"] = None
        if "rank_cat" not in f:
            f["rank_cat"] = None

    # ── Top 5 picks ────────────────────────────────────────────────────
    top_picks = [
        {
            "isin":         f["isin"],
            "name":         f["name"],
            "cat_id":       f["cat_id"],
            "score_final":  f["score_final"],
            "signal_label": f["signal_label"],
        }
        for f in scored_sorted[:5]
    ]

    # ── Résumé par catégorie ────────────────────────────────────────────
    cat_summary: dict[str, dict] = {}
    for cat_id, funds_in_cat in by_cat.items():
        scores = [f["score_final"] for f in funds_in_cat if f["score_final"] is not None]
        cat_sent = sentiment_cats.get(cat_id, {})
        cat_summary[cat_id] = {
            "avg_score":       round(sum(scores) / len(scores), 2) if scores else None,
            "top_fund":        funds_in_cat[0]["name"] if funds_in_cat else None,
            "fund_count":      len(funds_in_cat),
            "sentiment":       cat_sent.get("signal"),
            "sentiment_score": sentiment_to_score(cat_sent.get("score")),
        }

    # ── Structure de sortie ────────────────────────────────────────────
    now = datetime.now(timezone.utc).isoformat()

    output = {
        "last_updated":     now,
        "weights": {
            "momentum":  W_MOMENTUM,
            "sentiment": W_SENTIMENT,
        },
        "global_macro":     global_macro,
        "top_picks":        top_picks,
        "category_summary": cat_summary,
        "funds": {
            f["isin"]: {k: v for k, v in f.items() if k != "isin"}
            for f in fund_scores
        },
    }

    # ── Sauvegarde ─────────────────────────────────────────────────────
    DATA.mkdir(parents=True, exist_ok=True)
    with open(SCORES_PATH, "w", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)

    scored_count = len([f for f in fund_scores if f["score_final"] is not None])
    print(f"✅ {scored_count}/{len(funds_meta)} fonds scorés → {SCORES_PATH}")

    if top_picks:
        print("\n🏆 Top 5 picks :")
        for i, p in enumerate(top_picks, 1):
            print(f"   {i}. [{p['score_final']:.1f}] {p['name']} ({p['signal_label']})")

    return output


# ── CLI ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Moteur de scoring final predict-tempo"
    )
    parser.add_argument(
        "--no-momentum",
        action="store_true",
        help="Ignorer les scores momentum (debug)",
    )
    parser.add_argument(
        "--no-sentiment",
        action="store_true",
        help="Ignorer les scores sentiment (debug)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Afficher le JSON complet sur stdout après calcul",
    )
    args = parser.parse_args()

    result = run_engine(
        use_momentum=not args.no_momentum,
        use_sentiment=not args.no_sentiment,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
