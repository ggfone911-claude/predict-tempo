#!/usr/bin/env python3
"""
predict-tempo — scoring/sentiment.py

Analyse LLM (Claude API) des actualités financières et du contexte macro.
Génère un score de sentiment par catégorie de fonds et un résumé thématique.

Pipeline :
  1. Charge data/news.json et data/macro.json
  2. Pour chaque catégorie, sélectionne les articles les plus pertinents
  3. Appelle Claude pour analyser l'impact macro + news sur la catégorie
  4. Retourne un score sentiment [-1, +1] + signal + facteurs clés

Sortie : data/sentiment.json
  {
    "last_updated": "...",
    "global_macro": {
      "sentiment": 0.15,
      "signal": "neutre+",
      "summary": "...",
      "key_themes": ["BCE", "inflation", "marchés actions"]
    },
    "categories": {
      "monetaire": {
        "sentiment": 0.30,
        "confidence": 0.85,
        "signal": "haussier",
        "key_factors": ["taux BCE stables", "monétaire attractif"],
        "risks": ["baisse prématurée des taux"],
        "analysis": "..."
      },
      ...
    }
  }

Prérequis :
  pip install anthropic
  export ANTHROPIC_API_KEY="sk-ant-..."

Usage :
  python -m scoring.sentiment
  python -m scoring.sentiment --dry-run   # sans appel API, données fictives
"""

from __future__ import annotations
import json
import os
import sys
import datetime
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.funds_meta import CATEGORIES

NEWS_PATH     = os.path.join(os.path.dirname(__file__), "..", "data", "news.json")
MACRO_PATH    = os.path.join(os.path.dirname(__file__), "..", "data", "macro.json")
OUTPUT_PATH   = os.path.join(os.path.dirname(__file__), "..", "data", "sentiment.json")

# Modèle Claude utilisé (Haiku = rapide et économique pour ce type d'analyse)
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

# Nombre max d'articles par catégorie envoyés au LLM
MAX_ARTICLES_PER_CAT = 8

# Nombre max d'articles macro/globaux
MAX_MACRO_ARTICLES = 10

# Mapping signal textuel → valeur numérique
SIGNAL_VALUES = {
    "fort_haussier":  1.0,
    "haussier":       0.6,
    "neutre+":        0.2,
    "neutre":         0.0,
    "neutre-":       -0.2,
    "baissier":      -0.6,
    "fort_baissier": -1.0,
}


# ── Chargement des données ────────────────────────────────────────────────────

def load_news() -> list[dict]:
    if not os.path.exists(NEWS_PATH):
        print("⚠  data/news.json introuvable — lance scraper_news.py d'abord")
        return []
    with open(NEWS_PATH, "r", encoding="utf-8") as f:
        return json.load(f).get("articles", [])


def load_macro() -> dict:
    if not os.path.exists(MACRO_PATH):
        print("⚠  data/macro.json introuvable — lance scraper_macro.py d'abord")
        return {}
    with open(MACRO_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Sélection des articles ────────────────────────────────────────────────────

def select_articles(articles: list[dict], cat_id: str, n: int = MAX_ARTICLES_PER_CAT) -> list[dict]:
    """
    Sélectionne les articles les plus pertinents pour une catégorie.
    Priorité : articles avec cat_id dans cat_tags, puis articles macro globaux.
    """
    # Articles directement taggués pour cette catégorie
    direct = [a for a in articles if cat_id in a.get("cat_tags", [])]
    # Articles macro (sans cat_tags ou avec beaucoup de catégories)
    macro  = [a for a in articles
              if not a.get("cat_tags") or len(a.get("cat_tags", [])) >= 4]

    # Déduplique et prend les n plus récents
    seen  = set()
    pool  = []
    for a in direct + macro:
        uid = a.get("id") or a.get("url", "")
        if uid not in seen:
            seen.add(uid)
            pool.append(a)

    # Tri par date desc
    pool.sort(key=lambda a: a.get("published", ""), reverse=True)
    return pool[:n]


def format_articles(articles: list[dict]) -> str:
    """Formate les articles pour injection dans le prompt."""
    lines = []
    for i, a in enumerate(articles, 1):
        lines.append(
            f"{i}. [{a['source']}] {a['title']}\n"
            f"   {a.get('summary', '')[:200]}"
        )
    return "\n".join(lines)


def format_macro(macro: dict) -> str:
    """Formate le contexte macro pour le prompt."""
    ctx = macro.get("context", {})
    rates = macro.get("rates", {})
    bonds = macro.get("bonds", {})
    indices = macro.get("indices", {})

    parts = []

    # Taux
    if rates.get("ecb_deposit") is not None:
        parts.append(f"Taux BCE dépôt : {rates['ecb_deposit']}%")
    if rates.get("ecb_main") is not None:
        parts.append(f"Taux BCE refi : {rates['ecb_main']}%")
    if rates.get("fed_funds_proxy") is not None:
        parts.append(f"Fed Funds proxy : {rates['fed_funds_proxy']}%")

    # Yields
    for k, label in [("bund_10y","Bund 10Y"), ("oat_10y","OAT 10Y"),
                     ("tbond_10y","T-Bond 10Y")]:
        if bonds.get(k) is not None:
            parts.append(f"{label} : {bonds[k]}%")

    # Indices
    for k, label in [("cac40","CAC 40"), ("eurostoxx50","Eurostoxx 50"),
                     ("sp500","S&P 500"), ("vix","VIX")]:
        v = indices.get(k)
        if v and isinstance(v, dict):
            chg = f" ({'+' if v['chg_pct']>=0 else ''}{v['chg_pct']}%)" if v.get("chg_pct") is not None else ""
            parts.append(f"{label} : {v['value']}{chg}")

    # Synthèse contexte
    if ctx.get("summary"):
        parts.append(f"Synthèse : {ctx['summary']}")

    return "\n".join(f"• {p}" for p in parts) if parts else "Données macro non disponibles."


# ── Appel Claude ──────────────────────────────────────────────────────────────

def _build_prompt_category(cat_label: str, macro_str: str, articles_str: str) -> str:
    return f"""Tu es un analyste financier senior spécialisé dans les fonds d'investissement français.

## Contexte macro actuel
{macro_str}

## Actualités récentes (catégorie : {cat_label})
{articles_str if articles_str else "Aucun article spécifique disponible pour cette catégorie."}

## Ta mission
Analyse l'impact de ce contexte macro et de ces actualités sur les fonds de la catégorie **{cat_label}**.

Réponds UNIQUEMENT en JSON valide, sans texte avant ou après, selon ce format exact :
{{
  "signal": "<fort_haussier|haussier|neutre+|neutre|neutre-|baissier|fort_baissier>",
  "sentiment": <float entre -1.0 et 1.0>,
  "confidence": <float entre 0.0 et 1.0>,
  "key_factors": ["<facteur positif 1>", "<facteur positif 2>"],
  "risks": ["<risque 1>", "<risque 2>"],
  "analysis": "<synthèse en 2-3 phrases, en français, sur l'impact pour cette catégorie>"
}}

Règles :
- signal et sentiment doivent être cohérents
- key_factors = éléments favorables à la catégorie
- risks = éléments défavorables
- analysis = texte factuel, concis, sans jargon excessif
"""


def _build_prompt_global(macro_str: str, articles_str: str) -> str:
    return f"""Tu es un analyste macroéconomique senior.

## Données macro actuelles
{macro_str}

## Actualités financières récentes (sélection)
{articles_str}

## Ta mission
Fournis une synthèse macro globale pour guider l'allocation entre classes d'actifs
(monétaire, obligataire, actions, flexibles).

Réponds UNIQUEMENT en JSON valide, sans texte avant ou après :
{{
  "signal": "<fort_haussier|haussier|neutre+|neutre|neutre-|baissier|fort_baissier>",
  "sentiment": <float entre -1.0 et 1.0>,
  "key_themes": ["<thème 1>", "<thème 2>", "<thème 3>"],
  "summary": "<synthèse macro en 3-4 phrases, en français>",
  "favors": ["<catégorie favorisée 1>", "<catégorie favorisée 2>"],
  "avoids": ["<catégorie à éviter 1>"]
}}
"""


def call_claude(prompt: str, client) -> dict | None:
    """Appelle l'API Claude et parse le JSON retourné."""
    try:
        msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()

        # Extrait le JSON (Claude peut parfois ajouter du texte)
        m = __import__("re").search(r'\{[\s\S]*\}', raw)
        if not m:
            print(f"    ✗ Pas de JSON dans la réponse : {raw[:100]}")
            return None
        return json.loads(m.group())

    except json.JSONDecodeError as e:
        print(f"    ✗ JSON invalide : {e}")
        return None
    except Exception as e:
        print(f"    ✗ Erreur API : {e}")
        return None


# ── Mode dry-run (sans API) ───────────────────────────────────────────────────

def _dummy_sentiment(cat_id: str) -> dict:
    """Retourne un sentiment fictif pour le dry-run."""
    import random
    random.seed(hash(cat_id) % 1000)
    s = round(random.uniform(-0.3, 0.6), 2)
    signal = (
        "haussier"  if s > 0.4 else
        "neutre+"   if s > 0.1 else
        "neutre"    if s > -0.1 else
        "neutre-"   if s > -0.4 else
        "baissier"
    )
    return {
        "sentiment":   s,
        "confidence":  round(random.uniform(0.5, 0.9), 2),
        "signal":      signal,
        "key_factors": ["Données fictives (dry-run)"],
        "risks":       ["Lancer sans --dry-run pour une vraie analyse"],
        "analysis":    f"[DRY-RUN] Sentiment simulé pour {cat_id} : {s}",
    }


# ── Pipeline principal ────────────────────────────────────────────────────────

def run_sentiment(dry_run: bool = False) -> dict:
    """
    Analyse le sentiment macro + news par catégorie de fonds.
    dry_run = True → pas d'appel API, données fictives.
    """
    articles = load_news()
    macro    = load_macro()
    macro_str = format_macro(macro)

    now = datetime.datetime.utcnow().isoformat()[:19]
    print(f"\n{'─'*60}")
    print(f"Analyse sentiment — {now}"
          + (" [DRY-RUN]" if dry_run else f" [{CLAUDE_MODEL}]"))
    print(f"{'─'*60}")
    print(f"  {len(articles)} articles chargés | macro : {'OK' if macro else 'manquante'}")

    client = None
    if not dry_run:
        try:
            import anthropic
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise EnvironmentError(
                    "Variable ANTHROPIC_API_KEY manquante.\n"
                    "Exporte-la : export ANTHROPIC_API_KEY='sk-ant-...'\n"
                    "Ou lance en mode test : python -m scoring.sentiment --dry-run"
                )
            client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            print("✗ Module 'anthropic' non installé.")
            print("  Lance : pip install anthropic")
            sys.exit(1)

    result: dict = {
        "last_updated": now,
        "global_macro": {},
        "categories":   {},
    }

    # ── Analyse macro globale ──────────────────────────────────────────────
    print("\n[Global] Analyse macro globale…")
    macro_articles = select_articles(articles, cat_id="", n=MAX_MACRO_ARTICLES)
    art_str = format_articles(macro_articles)

    if dry_run:
        import random; random.seed(42)
        s = round(random.uniform(-0.2, 0.4), 2)
        result["global_macro"] = {
            "sentiment":  s,
            "signal":     "neutre+" if s > 0 else "neutre-",
            "key_themes": ["BCE", "inflation", "marchés actions"],
            "summary":    "[DRY-RUN] Synthèse macro fictive.",
            "favors":     ["actions_eu", "monetaire"],
            "avoids":     ["oblig_lt"],
        }
    else:
        prompt = _build_prompt_global(macro_str, art_str)
        res = call_claude(prompt, client)
        if res:
            result["global_macro"] = res
            print(f"  signal={res.get('signal')}  sentiment={res.get('sentiment')}")
        else:
            result["global_macro"] = {"signal": "inconnu", "sentiment": 0.0}

    # ── Analyse par catégorie ──────────────────────────────────────────────
    for cat in CATEGORIES:
        cat_id    = cat["id"]
        cat_label = cat["label"]
        print(f"\n[{cat_id}] {cat_label}…")

        cat_articles = select_articles(articles, cat_id, n=MAX_ARTICLES_PER_CAT)
        art_str = format_articles(cat_articles)
        print(f"  {len(cat_articles)} articles sélectionnés")

        if dry_run:
            res = _dummy_sentiment(cat_id)
        else:
            prompt = _build_prompt_category(cat_label, macro_str, art_str)
            res = call_claude(prompt, client)
            if res is None:
                res = _dummy_sentiment(cat_id)
                res["analysis"] = "[Erreur API — données fictives]"

        result["categories"][cat_id] = res
        print(f"  → signal={res.get('signal')}  sentiment={res.get('sentiment'):.2f}"
              f"  conf={res.get('confidence', '?')}")

        if not dry_run:
            import time; time.sleep(0.5)  # rate limit

    # ── Sauvegarde ─────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"💾 Sauvegardé → {OUTPUT_PATH}")

    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="predict-tempo — analyse sentiment LLM")
    parser.add_argument("--dry-run", action="store_true",
                        help="Mode test sans appel API (données fictives)")
    args = parser.parse_args()
    run_sentiment(dry_run=args.dry_run)
