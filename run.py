#!/usr/bin/env python3
"""
predict-tempo — Point d'entrée principal
Usage:
  python run.py           # Pipeline complet
  python run.py --score   # Scoring uniquement
  python run.py --report  # Rapport PDF uniquement
"""
import argparse, sys

def main():
    parser = argparse.ArgumentParser(description="predict-tempo pipeline")
    parser.add_argument("--score",  action="store_true", help="Score uniquement")
    parser.add_argument("--report", action="store_true", help="Rapport PDF uniquement")
    args = parser.parse_args()

    if args.score:
        print("→ Mode scoring uniquement")
        # from scoring.engine import run_scoring; run_scoring()
    elif args.report:
        print("→ Mode rapport PDF uniquement")
        # from gen_report import generate; generate()
    else:
        print("→ Pipeline complet : scraping → scoring → dashboard → rapport")
        # 1. Scraping
        # from scrapers.scraper_vl import scrape_vl; scrape_vl()
        # from scrapers.scraper_news import scrape_news; scrape_news()
        # from scrapers.scraper_macro import scrape_macro; scrape_macro()
        # 2. Scoring
        # from scoring.engine import run_scoring; run_scoring()
        # 3. Dashboard
        # from gen_dashboard import generate_dashboard; generate_dashboard()
        # 4. Rapport
        # from gen_report import generate_report; generate_report()
        print("✓ Pipeline terminé")

if __name__ == "__main__":
    main()
