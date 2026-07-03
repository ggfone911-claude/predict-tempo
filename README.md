# predict-tempo

Plateforme d'analyse prédictive des fonds Le Conservateur.

## Architecture

```
scrapers/
  scraper_vl.py        # VL historique Boursorama + Le Conservateur
  scraper_news.py      # Articles presse financière (RSS)
  scraper_macro.py     # Communiqués BCE, Fed, indicateurs marchés

scoring/
  engine.py            # Moteur de scoring (momentum quant + sentiment LLM)
  momentum.py          # Indicateurs quantitatifs (perf, drawdown, constance)
  sentiment.py         # Analyse macro via Claude API

data/                  # Cache JSON (gitignore)
output/                # Dashboard HTML généré
reports/               # Rapports PDF hebdos

gen_dashboard.py       # Générateur du dashboard interactif
gen_report.py          # Générateur du rapport PDF
run.py                 # Point d'entrée principal
```

## Usage

```bash
python run.py           # Scrape + score + génère dashboard + rapport
python run.py --score   # Score uniquement (sans re-scraper)
python run.py --report  # Rapport PDF uniquement
```
