#!/usr/bin/env python3
"""
run.py — Chef d'orchestre predict-tempo
========================================
Enchaîne tout le pipeline en une commande.

Pipeline complet :
  1. scraper_vl    → data/funds_vl.json       (cours + historique)
  2. scraper_news  → data/news.json            (actualités RSS)
  3. scraper_macro → data/macro.json           (taux, indices, CB)
  4. momentum      → data/momentum.json        (scores quantitatifs)
  5. sentiment     → data/sentiment.json       (analyse LLM)
  6. engine        → data/scores.json          (score final 0-10)
  7. gen_dashboard → dashboard.html            (interface interactive)
  8. gen_report    → reports/predict_tempo_*.pdf (rapport PDF)

Usage :
  python run.py                        # Pipeline complet
  python run.py --quick                # VL courante seulement (pas d'historique)
  python run.py --no-scrape            # Scoring + outputs uniquement (données existantes)
  python run.py --no-report            # Sans PDF
  python run.py --no-sentiment         # Sans appel LLM (momentum uniquement)
  python run.py --dry-run              # Sentiment en mode simulation (pas d'API)
  python run.py --open                 # Ouvre dashboard.html à la fin
  python run.py --step vl              # Un seul module (vl/news/macro/momentum/sentiment/engine/dashboard/report)
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# ── Couleurs terminal ──────────────────────────────────────────────────────
class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    BLUE   = "\033[94m"
    CYAN   = "\033[96m"
    DIM    = "\033[2m"

def ok(msg):   print(f"{C.GREEN}✅ {msg}{C.RESET}")
def warn(msg): print(f"{C.YELLOW}⚠️  {msg}{C.RESET}")
def err(msg):  print(f"{C.RED}❌ {msg}{C.RESET}")
def info(msg): print(f"{C.CYAN}ℹ  {msg}{C.RESET}")
def step(msg): print(f"\n{C.BOLD}{C.BLUE}{'─'*50}{C.RESET}\n{C.BOLD}▶ {msg}{C.RESET}")


def banner():
    print(f"""
{C.BOLD}{C.BLUE}╔══════════════════════════════════════╗
║       ⚡  predict-tempo  ⚡           ║
║  Pipeline d'analyse prédictive fonds ║
╚══════════════════════════════════════╝{C.RESET}
  Démarré le {datetime.now().strftime("%d/%m/%Y à %H:%M:%S")}
""")


def run_step(name: str, fn, *args, **kwargs) -> bool:
    """Exécute une étape du pipeline, capture les erreurs."""
    t0 = time.time()
    try:
        fn(*args, **kwargs)
        elapsed = time.time() - t0
        ok(f"{name} ({elapsed:.1f}s)")
        return True
    except SystemExit as e:
        if e.code == 0:
            ok(f"{name} (terminé proprement)")
            return True
        err(f"{name} a échoué (code {e.code})")
        return False
    except Exception as e:
        err(f"{name} a échoué : {e}")
        import traceback
        traceback.print_exc()
        return False


# ── Étapes du pipeline ─────────────────────────────────────────────────────

def step_vl(quick: bool = False):
    step("1/8 — Scraping VL (cours + historique)")
    from scrapers.scraper_vl import scrape_vl
    result = scrape_vl(quick=quick)
    n = len(result.get("funds", {}))
    info(f"{n} fonds collectés (mode {'rapide' if quick else 'complet'})")


def step_news():
    step("2/8 — Scraping actualités RSS")
    from scrapers.scraper_news import scrape_news
    result = scrape_news()
    n = len(result.get("articles", []))
    info(f"{n} articles collectés")


def step_macro():
    step("3/8 — Scraping données macroéconomiques")
    from scrapers.scraper_macro import scrape_macro
    result = scrape_macro()
    rates = result.get("rates", {})
    info(f"BCE dépôt : {rates.get('ecb_deposit','—')} | "
         f"Fed : {rates.get('fed_funds_proxy','—')} | "
         f"VIX : {result.get('indices',{}).get('vix','—')}")


def step_momentum():
    step("4/8 — Calcul scores momentum")
    from scoring.momentum import run_momentum
    result = run_momentum()
    n_scored = sum(1 for f in result.get("funds", {}).values()
                   if f.get("score_global") is not None)
    info(f"{n_scored} fonds scorés en momentum")


def step_sentiment(dry_run: bool = False):
    step("5/8 — Analyse sentiment LLM" + (" (dry-run)" if dry_run else ""))
    from scoring.sentiment import run_sentiment
    result = run_sentiment(dry_run=dry_run)
    n_cats = len(result.get("categories", {}))
    info(f"{n_cats} catégories analysées")


def step_engine(use_momentum: bool = True, use_sentiment: bool = True):
    step("6/8 — Calcul scores finaux")
    from scoring.engine import run_engine
    result = run_engine(use_momentum=use_momentum, use_sentiment=use_sentiment)
    n = sum(1 for f in result.get("funds", {}).values()
            if f.get("score_final") is not None)
    top = result.get("top_picks", [])
    info(f"{n} fonds scorés")
    if top:
        info(f"Top 1 : {top[0]['name']} ({top[0]['score_final']:.1f}/10)")


def step_dashboard(open_after: bool = False):
    step("7/8 — Génération dashboard HTML")
    from gen_dashboard import main as dash_main
    import gen_dashboard
    # Appel direct sans sous-processus
    from pathlib import Path as _P
    scores   = gen_dashboard.load_json(gen_dashboard.SCORES_PATH)
    momentum = gen_dashboard.load_json(gen_dashboard.MOMENTUM_PATH)
    if not scores:
        warn("scores.json introuvable — dashboard ignoré")
        return
    html = gen_dashboard.generate_html(scores, momentum)
    out  = gen_dashboard.OUT_DEFAULT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    info(f"dashboard.html → {out}")
    if open_after:
        import subprocess
        subprocess.run(["open", str(out)])


def step_report(open_after: bool = False):
    step("8/8 — Génération rapport PDF")
    import gen_report
    scores    = gen_report.load_json(gen_report.SCORES_PATH)
    sentiment = gen_report.load_json(gen_report.SENTIMENT_PATH)
    macro     = gen_report.load_json(gen_report.MACRO_PATH)
    if not scores:
        warn("scores.json introuvable — rapport ignoré")
        return
    from datetime import datetime as _dt
    gen_report.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = gen_report.REPORTS_DIR / f"predict_tempo_{_dt.now().strftime('%Y%m%d')}.pdf"
    gen_report.generate_report(scores, sentiment, macro, out_path)
    info(f"PDF → {out_path}")
    if open_after:
        import subprocess
        subprocess.run(["open", str(out_path)])


# ── Point d'entrée ─────────────────────────────────────────────────────────

STEPS_MAP = {
    "vl":        ("Scraping VL",         step_vl),
    "news":      ("Scraping news",        step_news),
    "macro":     ("Scraping macro",       step_macro),
    "momentum":  ("Momentum scoring",     step_momentum),
    "sentiment": ("Sentiment LLM",        step_sentiment),
    "engine":    ("Engine (score final)", step_engine),
    "dashboard": ("Dashboard HTML",       step_dashboard),
    "report":    ("Rapport PDF",          step_report),
}


def main():
    parser = argparse.ArgumentParser(
        description="predict-tempo — pipeline complet d'analyse prédictive",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python run.py                     # Pipeline complet
  python run.py --quick             # VL rapide (pas d'historique)
  python run.py --no-scrape         # Scoring uniquement (données déjà collectées)
  python run.py --no-report         # Sans PDF
  python run.py --dry-run           # Simulation LLM (pas d'API Anthropic)
  python run.py --step momentum     # Module unique : momentum
  python run.py --open              # Ouvre le dashboard à la fin
        """,
    )
    parser.add_argument("--quick",        action="store_true", help="VL courante seulement (pas d'historique)")
    parser.add_argument("--no-scrape",    action="store_true", help="Passer les scrapers (utilise les données existantes)")
    parser.add_argument("--no-report",    action="store_true", help="Ne pas générer le PDF")
    parser.add_argument("--no-sentiment", action="store_true", help="Passer l'analyse LLM (momentum seul)")
    parser.add_argument("--dry-run",      action="store_true", help="Sentiment en simulation (pas d'appel API)")
    parser.add_argument("--open",         action="store_true", help="Ouvrir le dashboard HTML à la fin")
    parser.add_argument(
        "--step", metavar="MODULE",
        choices=list(STEPS_MAP.keys()),
        help=f"Exécuter un seul module : {', '.join(STEPS_MAP.keys())}",
    )
    args = parser.parse_args()

    banner()
    t_start = time.time()
    failures = []

    # ── Mode module unique ─────────────────────────────────────────────
    if args.step:
        name, fn = STEPS_MAP[args.step]
        kwargs = {}
        if args.step == "vl":        kwargs["quick"]     = args.quick
        if args.step == "sentiment":  kwargs["dry_run"]   = args.dry_run
        if args.step == "engine":
            kwargs["use_sentiment"] = not args.no_sentiment
        if args.step in ("dashboard", "report"):
            kwargs["open_after"] = args.open
        if not run_step(name, fn, **kwargs):
            sys.exit(1)
        print(f"\n{C.GREEN}{C.BOLD}✔ Module '{args.step}' terminé.{C.RESET}")
        return

    # ── Pipeline complet ───────────────────────────────────────────────
    pipeline = []

    if not args.no_scrape:
        pipeline.append(("Scraping VL",    step_vl,        {"quick": args.quick}))
        pipeline.append(("Scraping news",  step_news,      {}))
        pipeline.append(("Scraping macro", step_macro,     {}))

    pipeline.append(("Momentum",   step_momentum,  {}))

    if not args.no_sentiment:
        pipeline.append(("Sentiment LLM", step_sentiment, {"dry_run": args.dry_run}))

    pipeline.append(("Engine", step_engine, {
        "use_momentum":  True,
        "use_sentiment": not args.no_sentiment,
    }))

    pipeline.append(("Dashboard", step_dashboard, {"open_after": False}))

    if not args.no_report:
        pipeline.append(("Rapport PDF", step_report, {"open_after": args.open}))
    elif args.open:
        # Open dashboard if --open but --no-report
        import subprocess, gen_dashboard as gd
        subprocess.run(["open", str(gd.OUT_DEFAULT)])

    # Exécution
    for name, fn, kwargs in pipeline:
        if not run_step(name, fn, **kwargs):
            failures.append(name)
            warn(f"Étape '{name}' échouée — poursuite du pipeline...")

    # ── Résumé ─────────────────────────────────────────────────────────
    elapsed = time.time() - t_start
    print(f"\n{C.BOLD}{'═'*50}{C.RESET}")
    if not failures:
        print(f"{C.GREEN}{C.BOLD}✔ Pipeline complet terminé en {elapsed:.0f}s{C.RESET}")
    else:
        print(f"{C.YELLOW}{C.BOLD}⚠ Pipeline terminé en {elapsed:.0f}s "
              f"avec {len(failures)} erreur(s) : {', '.join(failures)}{C.RESET}")

    # Affiche les sorties principales
    data_dir = ROOT / "data"
    for fname in ("funds_vl.json", "news.json", "macro.json",
                  "momentum.json", "sentiment.json", "scores.json"):
        p = data_dir / fname
        if p.exists():
            size = p.stat().st_size / 1024
            print(f"  {C.DIM}data/{fname} → {size:.0f} Ko{C.RESET}")

    dash = ROOT / "dashboard.html"
    if dash.exists():
        print(f"  {C.CYAN}dashboard.html → {dash}{C.RESET}")

    reports = sorted((ROOT / "reports").glob("*.pdf")) if (ROOT / "reports").exists() else []
    if reports:
        print(f"  {C.CYAN}Dernier rapport → {reports[-1]}{C.RESET}")

    print()
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
