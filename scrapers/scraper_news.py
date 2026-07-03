#!/usr/bin/env python3
"""
predict-tempo — scrapers/scraper_news.py

Collecte d'articles financiers depuis des flux RSS publics.
Tague chaque article par catégorie de fonds et mots-clés macro.

Sources :
  • Les Echos (bourse + économie)
  • BFM Bourse
  • Le Monde Économie
  • Boursorama Actualités
  • Reuters (marchés)
  • AMF (régulateur français)
  • Morningstar France
  • Investir / Le Revenu (via flux publics)

Sortie : data/news.json
  {
    "last_updated": "YYYY-MM-DD HH:MM",
    "count": 142,
    "articles": [
      {
        "id":        "sha1 de l'URL",
        "title":     "...",
        "url":       "https://...",
        "source":    "Les Echos",
        "published": "2026-07-03T10:30:00",
        "summary":   "...",
        "cat_tags":  ["oblig_lt", "monetaire"],
        "kw_tags":   ["BCE", "taux directeurs", "inflation"],
        "sentiment_hint": null   ← rempli par scoring/sentiment.py
      },
      ...
    ]
  }

Usage :
  python -m scrapers.scraper_news
  python -m scrapers.scraper_news --max 50   # limite par source
"""

import json
import re
import time
import gzip
import hashlib
import datetime
import argparse
import os
import sys
import xml.etree.ElementTree as ET
import urllib.request
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.funds_meta import FUNDS, CATEGORIES

# ── Chemins ───────────────────────────────────────────────────────────────────

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "news.json")

# ── Sources RSS ───────────────────────────────────────────────────────────────

RSS_SOURCES = [
    # Source                   URL flux RSS
    ("Les Echos Bourse",       "https://www.lesechos.fr/arc/outboundfeeds/rss/finance/?outputType=xml"),
    ("Les Echos Économie",     "https://www.lesechos.fr/arc/outboundfeeds/rss/economie/?outputType=xml"),
    ("BFM Bourse",             "https://www.bfmtv.com/rss/economie/bourse/"),
    ("BFM Économie",           "https://www.bfmtv.com/rss/economie/"),
    ("Le Monde Économie",      "https://www.lemonde.fr/economie/rss_full.xml"),
    ("Reuters Marchés",        "https://feeds.reuters.com/reuters/businessNews"),
    ("Boursorama Actualités",  "https://www.boursorama.com/rss/actualites.phtml"),
    ("Morningstar FR",         "https://www.morningstar.fr/fr/rss/news.aspx"),
    ("AMF",                    "https://www.amf-france.org/fr/rss/actualites"),
    ("Capital Économie",       "https://www.capital.fr/feed/economie"),
    ("Zonebourse",             "https://www.zonebourse.com/rss/actu/"),
]

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": UA,
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

# ── Taxonomie de mots-clés ────────────────────────────────────────────────────

# Mots-clés → catégories de fonds impactées
KEYWORD_CATS: list[tuple[list[str], list[str]]] = [
    # Obligataire / taux
    (["taux directeur", "taux d'intérêt", "taux d intérêt", "obligation", "spread",
      "credit", "crédit", "yield", "coupon", "emprunt d état", "emprunt d'état",
      "bund", "OAT", "T-bond", "treasury"],
     ["monetaire", "oblig_lt", "oblig_horizon", "mixtes_oblig"]),

    # Banques centrales
    (["BCE", "banque centrale européenne", "Fed", "réserve fédérale", "federal reserve",
      "taux de la fed", "taux fed", "pivot", "quantitative easing", "QE", "QT",
      "banque centrale", "Powell", "Lagarde"],
     ["monetaire", "oblig_lt", "oblig_horizon", "mixtes_oblig", "flexibles"]),

    # Inflation / macro
    (["inflation", "déflation", "IPC", "CPI", "PCE", "stagflation",
      "croissance économique", "PIB", "GDP", "récession", "soft landing",
      "hard landing", "atterrissage"],
     ["monetaire", "oblig_lt", "mixtes_oblig", "flexibles"]),

    # Marchés actions
    (["CAC 40", "CAC40", "Eurostoxx", "S&P 500", "S&P500", "Nasdaq",
      "bourse", "actions", "dividende", "résultats trimestriels", "earnings",
      "valorisation", "PER", "ratio cours"],
     ["actions_fr", "actions_eu", "actions_int", "flexibles"]),

    # Actions françaises
    (["SBF 120", "small cap français", "ETI française", "PME cotée", "Midcap",
      "marché parisien", "euronext paris", "bourse de paris"],
     ["actions_fr"]),

    # Actions européennes
    (["Europe", "zone euro", "marché européen", "actions européennes",
      "STOXX 600", "DAX", "FTSE", "MIB"],
     ["actions_eu"]),

    # Actions internationales / émergents
    (["émergents", "marchés émergents", "Chine", "Asie", "Inde", "États-Unis",
      "Amérique", "dollar", "USD", "yuan", "yen", "global", "mondial"],
     ["actions_int"]),

    # Énergie / ESG (impact fonds thématiques)
    (["énergie", "transition énergétique", "ESG", "ISR", "investissement responsable",
      "climat", "CO2", "carbone", "hydrogène", "renouvelable", "solaire", "éolien"],
     ["actions_int", "actions_eu", "mixtes_oblig"]),

    # Immobilier (impact SCPI, fonds immo)
    (["immobilier", "SCPI", "OPCI", "foncière", "REIT", "real estate", "pierre papier"],
     ["actions_eu", "mixtes_oblig"]),

    # Flexibles / multi-actifs
    (["allocation d actifs", "allocation d'actifs", "diversification",
      "multi-actifs", "flexible", "gestion flexible", "momentum"],
     ["flexibles", "mixtes_oblig"]),
]

# Mots-clés macro globaux (toutes catégories)
MACRO_KEYWORDS = [
    "BCE", "Fed", "banque centrale", "inflation", "taux directeur",
    "récession", "croissance", "PIB", "chômage", "QE", "QT",
    "Lagarde", "Powell", "politique monétaire", "resserrement monétaire",
    "assouplissement monétaire", "marché obligataire", "marché actions",
    "volatilité", "risque", "crise", "krach", "rebond", "correction",
]

# Noms de sociétés de gestion / fonds pour tagger les articles spécifiques
MGR_KEYWORDS = sorted(set(f["mgr"] for f in FUNDS if f["mgr"]))
FUND_NAMES   = sorted(set(
    re.split(r'[\(\[]', f["name"])[0].strip()
    for f in FUNDS
))


# ── Parsing RSS ───────────────────────────────────────────────────────────────

def _fetch_rss(url: str) -> str | None:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            enc = resp.headers.get("Content-Encoding", "")
            if enc == "gzip":
                raw = gzip.decompress(raw)
            return raw.decode("utf-8", errors="replace")
    except Exception as e:
        print(f"    ✗ {url[:60]}… : {e}")
        return None


def _clean_html(s: str) -> str:
    """Supprime les balises HTML et nettoie les espaces."""
    s = re.sub(r'<[^>]+>', ' ', s or '')
    s = re.sub(r'&amp;',  '&',  s)
    s = re.sub(r'&lt;',   '<',  s)
    s = re.sub(r'&gt;',   '>',  s)
    s = re.sub(r'&nbsp;', ' ',  s)
    s = re.sub(r'&#\d+;', ' ',  s)
    s = re.sub(r'\s+',    ' ',  s)
    return s.strip()


def _parse_date(s: str | None) -> str:
    """Tente de normaliser une date RSS en ISO 8601."""
    if not s:
        return datetime.datetime.utcnow().isoformat()
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",   # RFC 822
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",         # Atom
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            dt = datetime.datetime.strptime(s.strip(), fmt)
            return dt.isoformat()
        except ValueError:
            continue
    return s.strip()


NS = {
    "atom":    "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc":      "http://purl.org/dc/elements/1.1/",
    "media":   "http://search.yahoo.com/mrss/",
}

def _text(el, *tags) -> str:
    """Cherche le premier tag existant dans un élément XML."""
    for tag in tags:
        child = el.find(tag)
        if child is not None and child.text:
            return child.text.strip()
    return ""


def parse_rss(xml_str: str, source_name: str, max_items: int = 100) -> list[dict]:
    """Parse un flux RSS ou Atom, retourne une liste d'articles bruts."""
    articles = []
    try:
        # Nettoyage des namespaces inconnus
        xml_clean = re.sub(r'xmlns:[a-z]+="[^"]+"', '', xml_str)
        root = ET.fromstring(xml_clean)
    except ET.ParseError as e:
        print(f"    ✗ XML invalide ({source_name}) : {e}")
        return []

    # Détecte RSS vs Atom
    items = root.findall(".//item") or root.findall(".//entry")

    for item in items[:max_items]:
        # Titre
        title = _clean_html(_text(item, "title"))
        if not title:
            continue

        # URL
        url = (_text(item, "link") or
               (item.find("link") is not None and item.find("link").get("href", "")) or
               "")
        url = url.strip()
        if not url:
            continue

        # Date
        pub = _parse_date(
            _text(item, "pubDate", "published", "updated",
                  "{http://purl.org/dc/elements/1.1/}date")
        )

        # Résumé
        summary = _clean_html(
            _text(item, "description", "summary",
                  "{http://purl.org/rss/1.0/modules/content/}encoded")
        )
        # Tronque à 500 chars
        if len(summary) > 500:
            summary = summary[:497] + "…"

        articles.append({
            "title":     title,
            "url":       url,
            "source":    source_name,
            "published": pub,
            "summary":   summary,
        })

    return articles


# ── Tagging thématique ────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    return text.lower()


def tag_article(article: dict) -> dict:
    """
    Ajoute cat_tags (catégories de fonds impactées)
    et kw_tags (mots-clés macro détectés) à un article.
    """
    blob = _normalize(
        f"{article['title']} {article['summary']} {article['source']}"
    )

    cat_hits: set[str] = set()
    kw_hits:  set[str] = set()

    # Catégories par mots-clés
    for keywords, cats in KEYWORD_CATS:
        for kw in keywords:
            if kw.lower() in blob:
                cat_hits.update(cats)
                kw_hits.add(kw)
                break  # un seul match suffit par groupe

    # Mots-clés macro globaux
    for kw in MACRO_KEYWORDS:
        if kw.lower() in blob:
            kw_hits.add(kw)

    # Sociétés de gestion / noms de fonds
    for mgr in MGR_KEYWORDS:
        if mgr.lower() in blob:
            kw_hits.add(mgr)
    for fname in FUND_NAMES:
        if len(fname) > 4 and fname.lower() in blob:
            kw_hits.add(fname)

    article["cat_tags"]      = sorted(cat_hits)
    article["kw_tags"]       = sorted(kw_hits)
    article["sentiment_hint"] = None   # rempli par scoring/sentiment.py

    return article


# ── Pipeline principal ────────────────────────────────────────────────────────

def scrape_news(max_per_source: int = 100) -> dict:
    """
    Scrape tous les flux RSS, déduplique, tague et sauvegarde.
    Retourne le dict complet.
    """
    now   = datetime.datetime.utcnow()
    today = now.strftime("%Y-%m-%d %H:%M")

    # Charge les articles existants pour dédupliquer par URL
    existing_urls: set[str] = set()
    existing_articles: list[dict] = []
    if os.path.exists(DATA_PATH):
        try:
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                old = json.load(f)
            existing_articles = old.get("articles", [])
            existing_urls     = {a["url"] for a in existing_articles}
            # Conserve les articles des 7 derniers jours
            cutoff = (now - datetime.timedelta(days=7)).isoformat()
            existing_articles = [
                a for a in existing_articles
                if a.get("published", "") >= cutoff
            ]
            existing_urls = {a["url"] for a in existing_articles}
            print(f"↩  Articles existants (7j) : {len(existing_articles)}")
        except Exception as e:
            print(f"⚠  Lecture existant : {e}")

    new_articles: list[dict] = []
    total_parsed = 0

    print(f"\n{'─'*60}")
    print(f"Scraping news — {today} — {len(RSS_SOURCES)} sources")
    print(f"{'─'*60}")

    for source_name, url in RSS_SOURCES:
        print(f"\n→ {source_name}")
        xml_str = _fetch_rss(url)
        if not xml_str:
            continue

        raw_articles = parse_rss(xml_str, source_name, max_items=max_per_source)
        total_parsed += len(raw_articles)

        added = 0
        for art in raw_articles:
            if art["url"] in existing_urls:
                continue
            tagged = tag_article(art)
            # ID stable basé sur l'URL
            tagged["id"] = hashlib.sha1(art["url"].encode()).hexdigest()[:12]
            new_articles.append(tagged)
            existing_urls.add(art["url"])
            added += 1

        print(f"    {len(raw_articles)} articles parsés → {added} nouveaux")
        time.sleep(0.5)

    # Fusion : nouveaux + anciens, triés par date desc
    all_articles = new_articles + existing_articles
    all_articles.sort(key=lambda a: a.get("published", ""), reverse=True)

    print(f"\n{'─'*60}")
    print(f"Total : {len(all_articles)} articles  "
          f"({len(new_articles)} nouveaux, {total_parsed} parsés)")

    output = {
        "last_updated": today,
        "count":        len(all_articles),
        "articles":     all_articles,
    }

    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"💾 Sauvegardé → {DATA_PATH}")

    return output


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="predict-tempo — scraper news RSS")
    parser.add_argument("--max", type=int, default=100,
                        help="Nombre max d'articles par source (défaut: 100)")
    args = parser.parse_args()
    scrape_news(max_per_source=args.max)
