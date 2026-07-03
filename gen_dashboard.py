"""
gen_dashboard.py — Générateur de dashboard HTML predict-tempo
=============================================================
Lit data/scores.json (+ data/momentum.json pour historique)
et produit dashboard.html — fichier autonome, toutes données embarquées.

Usage :
    python gen_dashboard.py
    python gen_dashboard.py --out /chemin/vers/dashboard.html
    python gen_dashboard.py --open    # ouvre dans le navigateur après génération
"""

import json
import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime

ROOT          = Path(__file__).parent
DATA          = ROOT / "data"
SCORES_PATH   = DATA / "scores.json"
MOMENTUM_PATH = DATA / "momentum.json"
OUT_DEFAULT   = ROOT / "dashboard.html"

SIGNAL_STYLE = {
    "fort_achat":   {"color": "#1D9E75", "bg": "#e8f8f2", "emoji": "🚀"},
    "achat":        {"color": "#2ecc71", "bg": "#eafaf1", "emoji": "📈"},
    "neutre_plus":  {"color": "#8BC34A", "bg": "#f1f8e9", "emoji": "↗️"},
    "neutre":       {"color": "#888780", "bg": "#f5f5f4", "emoji": "➡️"},
    "neutre_moins": {"color": "#FF9800", "bg": "#fff3e0", "emoji": "↘️"},
    "vente":        {"color": "#FF5722", "bg": "#fbe9e7", "emoji": "📉"},
    "fort_vente":   {"color": "#D32F2F", "bg": "#ffebee", "emoji": "🔻"},
    "inconnu":      {"color": "#9e9e9e", "bg": "#fafafa", "emoji": "❓"},
}

CAT_LABELS = {
    "monetaire":          "Monétaire",
    "oblig_eur_ct":       "Oblig. EUR CT",
    "oblig_eur_lt":       "Oblig. EUR LT",
    "oblig_us":           "Oblig. US",
    "diversifie_prudent": "Diversifié Prudent",
    "diversifie_equilib": "Diversifié Équilibré",
    "actions_eur":        "Actions EUR",
    "actions_monde":      "Actions Monde",
}


def load_json(path: Path) -> dict:
    if not path.exists():
        print(f"⚠️  {path.name} introuvable — données partielles.", file=sys.stderr)
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def format_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y à %H:%M UTC")
    except Exception:
        return iso


def generate_html(scores: dict, momentum: dict) -> str:
    funds_raw    = scores.get("funds", {})
    top_picks    = scores.get("top_picks", [])
    cat_summary  = scores.get("category_summary", {})
    global_macro = scores.get("global_macro", {})
    last_updated = scores.get("last_updated", "")
    weights      = scores.get("weights", {"momentum": 0.6, "sentiment": 0.4})

    # Enrichir les fonds avec l'historique VL
    mom_funds = momentum.get("funds", {})
    for isin, fd in funds_raw.items():
        mom_entry = mom_funds.get(isin, {})
        fd["history"] = mom_entry.get("history", [])

    funds_js    = json.dumps(funds_raw,    ensure_ascii=False)
    top_js      = json.dumps(top_picks,    ensure_ascii=False)
    cat_js      = json.dumps(cat_summary,  ensure_ascii=False)
    macro_js    = json.dumps(global_macro, ensure_ascii=False)
    signal_js   = json.dumps(SIGNAL_STYLE, ensure_ascii=False)
    catlabel_js = json.dumps(CAT_LABELS,   ensure_ascii=False)
    date_str    = format_date(last_updated) if last_updated else "—"
    w_mom_pct   = int(weights.get("momentum",  0.6) * 100)
    w_sent_pct  = int(weights.get("sentiment", 0.4) * 100)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>predict-tempo — Dashboard</title>
<style>
  :root {{
    --bg:#f0f2f5; --card:#fff; --border:#e2e5ea; --text:#1a1a2e;
    --muted:#6b7280; --accent:#3266ad; --green:#1D9E75; --red:#D32F2F;
    --radius:12px; --shadow:0 2px 12px rgba(0,0,0,.08);
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        background:var(--bg);color:var(--text);overflow-x:hidden}}

  header{{background:linear-gradient(135deg,#1a1a2e,#16213e 60%,#0f3460);
          color:#fff;padding:20px 32px;display:flex;align-items:center;
          justify-content:space-between;position:sticky;top:0;z-index:100;
          box-shadow:0 2px 20px rgba(0,0,0,.3)}}
  .logo{{display:flex;align-items:center;gap:12px}}
  .logo-icon{{width:40px;height:40px;background:var(--green);border-radius:10px;
              display:flex;align-items:center;justify-content:center;font-size:20px}}
  .logo h1{{font-size:1.4rem;font-weight:700}}
  .logo span{{font-size:.75rem;color:#94a3b8}}
  .header-meta{{text-align:right;font-size:.78rem;color:#94a3b8}}
  .header-meta strong{{color:#e2e8f0}}
  .weights-badge{{display:inline-flex;gap:8px;margin-top:6px}}
  .wb{{padding:2px 8px;border-radius:20px;font-size:.7rem;font-weight:600}}
  .wb.mom{{background:#1D9E7533;color:#4ade80}}
  .wb.sent{{background:#3266ad33;color:#93c5fd}}

  main{{max-width:1400px;margin:0 auto;padding:24px 20px}}
  .section-title{{font-size:1rem;font-weight:700;color:var(--muted);
                  text-transform:uppercase;letter-spacing:.05em;margin-bottom:14px}}

  .macro-banner{{background:var(--card);border:1px solid var(--border);
    border-radius:var(--radius);padding:16px 24px;display:flex;gap:32px;
    align-items:center;flex-wrap:wrap;margin-bottom:24px;box-shadow:var(--shadow)}}
  .macro-item{{display:flex;flex-direction:column;gap:2px}}
  .macro-label{{font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}}
  .macro-val{{font-size:1rem;font-weight:700}}
  .macro-summary{{flex:1;min-width:200px;font-size:.82rem;color:var(--muted);
    border-left:2px solid var(--border);padding-left:24px;line-height:1.5}}
  .mood-pill{{display:inline-block;padding:2px 10px;border-radius:20px;
    font-size:.72rem;font-weight:700;text-transform:uppercase}}

  .top-picks{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
    gap:14px;margin-bottom:28px}}
  .pick-card{{background:var(--card);border:1px solid var(--border);
    border-radius:var(--radius);padding:18px 20px;cursor:pointer;
    transition:transform .15s,box-shadow .15s;position:relative;overflow:hidden}}
  .pick-card:hover{{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,.12)}}
  .pick-rank{{position:absolute;top:14px;right:16px;font-size:1.6rem;
    font-weight:900;color:var(--border);line-height:1}}
  .pick-cat{{font-size:.68rem;color:var(--muted);text-transform:uppercase;
    letter-spacing:.04em;margin-bottom:6px}}
  .pick-name{{font-size:.88rem;font-weight:600;margin-bottom:12px;line-height:1.3}}
  .pick-score-row{{display:flex;align-items:center;gap:10px}}
  .score-circle{{width:48px;height:48px;border-radius:50%;display:flex;
    align-items:center;justify-content:center;font-size:1rem;font-weight:800;
    color:#fff;flex-shrink:0}}
  .signal-badge{{display:inline-block;padding:3px 10px;border-radius:20px;
    font-size:.7rem;font-weight:700}}

  .cat-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));
    gap:12px;margin-bottom:28px}}
  .cat-card{{background:var(--card);border:1px solid var(--border);
    border-radius:var(--radius);padding:14px 18px}}
  .cat-name{{font-size:.78rem;font-weight:700;margin-bottom:10px}}
  .cat-stat{{display:flex;justify-content:space-between;align-items:center;
    font-size:.75rem;color:var(--muted);margin-bottom:4px}}
  .cat-stat strong{{color:var(--text);font-size:.9rem}}
  .score-bar-wrap{{background:#eee;border-radius:4px;height:6px;margin-top:8px}}
  .score-bar{{height:6px;border-radius:4px;transition:width .4s}}

  .table-controls{{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-bottom:14px}}
  .search-box{{flex:1;min-width:200px;padding:8px 14px;border:1px solid var(--border);
    border-radius:8px;font-size:.85rem;outline:none;background:var(--card)}}
  .search-box:focus{{border-color:var(--accent)}}
  select.filter{{padding:8px 12px;border:1px solid var(--border);border-radius:8px;
    font-size:.82rem;background:var(--card);cursor:pointer;outline:none}}
  .table-wrap{{background:var(--card);border:1px solid var(--border);
    border-radius:var(--radius);overflow:hidden;box-shadow:var(--shadow)}}
  table{{width:100%;border-collapse:collapse;font-size:.82rem}}
  thead th{{background:#f8f9fc;padding:10px 14px;text-align:left;font-size:.7rem;
    font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;
    border-bottom:1px solid var(--border);cursor:pointer;user-select:none;white-space:nowrap}}
  thead th:hover{{color:var(--accent)}}
  thead th .sort-icon{{margin-left:4px;opacity:.4}}
  thead th.sorted .sort-icon{{opacity:1;color:var(--accent)}}
  tbody tr{{border-bottom:1px solid #f0f2f5;cursor:pointer;transition:background .1s}}
  tbody tr:hover{{background:#f8f9fc}}
  tbody tr:last-child{{border-bottom:none}}
  td{{padding:10px 14px;vertical-align:middle}}
  td.rank{{font-weight:800;color:var(--muted);font-size:.9rem;width:40px}}
  td.fund-name{{font-weight:600;max-width:240px}}
  td.fund-name .fund-isin{{font-size:.68rem;color:var(--muted)}}
  td.srri-cell{{text-align:center}}
  .srri-dot{{display:inline-block;width:20px;height:20px;border-radius:50%;
    line-height:20px;text-align:center;font-size:.65rem;font-weight:700;color:#fff}}
  .score-pill{{display:inline-block;padding:4px 10px;border-radius:6px;
    font-weight:800;font-size:.88rem}}
  .mini-bar-wrap{{background:#eee;border-radius:3px;height:5px;width:60px;
    display:inline-block;vertical-align:middle;margin-left:6px}}
  .mini-bar{{height:5px;border-radius:3px}}

  .modal-overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);
    z-index:500;align-items:center;justify-content:center;padding:20px}}
  .modal-overlay.open{{display:flex}}
  .modal{{background:var(--card);border-radius:16px;max-width:680px;width:100%;
    max-height:90vh;overflow-y:auto;padding:32px;position:relative;
    box-shadow:0 20px 60px rgba(0,0,0,.3)}}
  .modal-close{{position:absolute;top:16px;right:20px;font-size:1.4rem;
    cursor:pointer;color:var(--muted);background:none;border:none;line-height:1}}
  .modal-close:hover{{color:var(--text)}}
  .modal-cat{{font-size:.72rem;color:var(--muted);text-transform:uppercase;
    letter-spacing:.05em;margin-bottom:4px}}
  .modal-title{{font-size:1.2rem;font-weight:700;margin-bottom:4px;line-height:1.3}}
  .modal-isin{{font-size:.72rem;color:var(--muted);margin-bottom:20px}}
  .score-big-row{{display:flex;align-items:center;gap:20px;margin-bottom:24px}}
  .score-big-circle{{width:80px;height:80px;border-radius:50%;display:flex;
    align-items:center;justify-content:center;font-size:1.8rem;font-weight:900;
    color:#fff;flex-shrink:0}}
  .score-big-info h3{{font-size:1rem;font-weight:700;margin-bottom:4px}}
  .score-big-info p{{font-size:.8rem;color:var(--muted);line-height:1.5}}
  .modal-section{{margin-bottom:20px}}
  .modal-section-title{{font-size:.75rem;font-weight:700;color:var(--muted);
    text-transform:uppercase;letter-spacing:.04em;margin-bottom:10px}}
  .sub-scores{{display:flex;gap:16px}}
  .sub-score-box{{flex:1;background:#f8f9fc;border-radius:10px;padding:12px 16px;text-align:center}}
  .sub-score-box .label{{font-size:.68rem;color:var(--muted);margin-bottom:4px}}
  .sub-score-box .val{{font-size:1.4rem;font-weight:800}}
  .drivers-list{{list-style:none}}
  .drivers-list li{{display:flex;align-items:center;gap:8px;padding:6px 0;
    border-bottom:1px solid #f0f2f5;font-size:.82rem}}
  .drivers-list li:last-child{{border-bottom:none}}
  .driver-dot{{width:8px;height:8px;border-radius:50%;background:var(--accent);flex-shrink:0}}
  .expl-text{{background:#f8f9fc;border-radius:10px;padding:14px 16px;
    font-size:.82rem;line-height:1.6;color:var(--muted)}}
  .chart-wrap{{height:160px;position:relative;margin-top:8px}}

  .empty{{text-align:center;padding:48px 20px;color:var(--muted)}}
  .empty .e-icon{{font-size:2.5rem;margin-bottom:12px}}

  @media(max-width:700px){{
    header{{flex-direction:column;gap:12px;text-align:center}}
    .macro-banner{{gap:16px}}
    .sub-scores{{flex-direction:column}}
  }}
</style>
</head>
<body>

<header>
  <div class="logo">
    <div class="logo-icon">⚡</div>
    <div>
      <h1>predict-tempo</h1>
      <span>Analyse prédictive des fonds</span>
    </div>
  </div>
  <div class="header-meta">
    <div>Mis à jour le <strong>{date_str}</strong></div>
    <div class="weights-badge">
      <span class="wb mom">Momentum {w_mom_pct}%</span>
      <span class="wb sent">Sentiment {w_sent_pct}%</span>
    </div>
  </div>
</header>

<main>

  <div id="macroBanner" class="macro-banner" style="display:none">
    <div class="macro-item">
      <span class="macro-label">BCE dépôt</span>
      <span class="macro-val" id="mEcbDep">—</span>
    </div>
    <div class="macro-item">
      <span class="macro-label">Taux Fed</span>
      <span class="macro-val" id="mFed">—</span>
    </div>
    <div class="macro-item">
      <span class="macro-label">VIX</span>
      <span class="macro-val" id="mVix">—</span>
    </div>
    <div class="macro-item">
      <span class="macro-label">Bund 10y</span>
      <span class="macro-val" id="mBund">—</span>
    </div>
    <div class="macro-item">
      <span class="macro-label">Humeur marché</span>
      <span class="macro-val" id="mMood">—</span>
    </div>
    <div class="macro-summary" id="mSummary">—</div>
  </div>

  <div class="section-title">🏆 Top 5 — Meilleurs fonds du moment</div>
  <div class="top-picks" id="topPicks"></div>

  <div class="section-title">📊 Résumé par catégorie</div>
  <div class="cat-grid" id="catGrid"></div>

  <div class="section-title">🔍 Tous les fonds</div>
  <div class="table-controls">
    <input type="text" class="search-box" id="searchBox" placeholder="Rechercher un fonds ou ISIN…">
    <select class="filter" id="catFilter">
      <option value="">Toutes catégories</option>
    </select>
    <select class="filter" id="signalFilter">
      <option value="">Tous les signaux</option>
      <option value="fort_achat">Fort achat 🚀</option>
      <option value="achat">Achat 📈</option>
      <option value="neutre_plus">Neutre+ ↗️</option>
      <option value="neutre">Neutre ➡️</option>
      <option value="neutre_moins">Neutre- ↘️</option>
      <option value="vente">Vente 📉</option>
      <option value="fort_vente">Fort vente 🔻</option>
    </select>
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th data-col="rank_global">Rang <span class="sort-icon">↕</span></th>
          <th data-col="name">Fonds <span class="sort-icon">↕</span></th>
          <th data-col="cat_id">Catégorie <span class="sort-icon">↕</span></th>
          <th data-col="srri">SRRI <span class="sort-icon">↕</span></th>
          <th data-col="score_final">Score <span class="sort-icon">↕</span></th>
          <th data-col="score_momentum">Momentum <span class="sort-icon">↕</span></th>
          <th data-col="score_sentiment">Sentiment <span class="sort-icon">↕</span></th>
          <th data-col="signal_id">Signal <span class="sort-icon">↕</span></th>
        </tr>
      </thead>
      <tbody id="fundsBody"></tbody>
    </table>
    <div class="empty" id="emptyState" style="display:none">
      <div class="e-icon">🔍</div>
      <p>Aucun fonds ne correspond aux filtres.</p>
    </div>
  </div>

</main>

<div class="modal-overlay" id="modalOverlay">
  <div class="modal">
    <button class="modal-close" id="modalClose">✕</button>
    <div class="modal-cat" id="mdCat"></div>
    <div class="modal-title" id="mdTitle"></div>
    <div class="modal-isin" id="mdIsin"></div>
    <div class="score-big-row">
      <div class="score-big-circle" id="mdCircle"></div>
      <div class="score-big-info">
        <h3 id="mdSignalLabel"></h3>
        <p id="mdSignalEmoji"></p>
      </div>
    </div>
    <div class="modal-section">
      <div class="modal-section-title">Décomposition du score</div>
      <div class="sub-scores">
        <div class="sub-score-box"><div class="label">Momentum</div><div class="val" id="mdMom">—</div></div>
        <div class="sub-score-box"><div class="label">Sentiment</div><div class="val" id="mdSent">—</div></div>
        <div class="sub-score-box"><div class="label">Rang global</div><div class="val" id="mdRankG">—</div></div>
        <div class="sub-score-box"><div class="label">Rang catégorie</div><div class="val" id="mdRankC">—</div></div>
      </div>
    </div>
    <div class="modal-section">
      <div class="modal-section-title">Analyse</div>
      <div class="expl-text" id="mdExpl"></div>
    </div>
    <div class="modal-section" id="mdDriversSection">
      <div class="modal-section-title">Indicateurs clés</div>
      <ul class="drivers-list" id="mdDrivers"></ul>
    </div>
    <div class="modal-section" id="mdChartSection">
      <div class="modal-section-title">Historique VL (mensuel)</div>
      <div class="chart-wrap"><canvas id="mdChart" style="width:100%;height:100%"></canvas></div>
    </div>
  </div>
</div>

<script>
const FUNDS       = {funds_js};
const TOP_PICKS   = {top_js};
const CAT_SUMMARY = {cat_js};
const MACRO       = {macro_js};
const SIG_STYLE   = {signal_js};
const CAT_LABELS  = {catlabel_js};

function scoreColor(s) {{
  if (s==null) return '#9e9e9e';
  if (s>=8.0) return '#1D9E75'; if (s>=6.5) return '#2ecc71';
  if (s>=5.5) return '#8BC34A'; if (s>=4.5) return '#888780';
  if (s>=3.5) return '#FF9800'; if (s>=2.0) return '#FF5722';
  return '#D32F2F';
}}
function srriColor(n) {{
  return ['#1D9E75','#4CAF50','#8BC34A','FF9800','#FF5722','#D32F2F','#7B1FA2'][Math.min(n-1,6)]||'#9e9e9e';
}}
function fmtScore(s){{return s!=null?s.toFixed(1):'—'}}
function ss(sig){{return SIG_STYLE[sig]||SIG_STYLE.inconnu}}
function catLabel(id){{return CAT_LABELS[id]||id}}

// Macro banner
(function(){{
  if(!MACRO||!MACRO.rates) return;
  const r=MACRO.rates||{{}},b=MACRO.bonds||{{}},ix=MACRO.indices||{{}},ctx=MACRO.context||{{}};
  const set=(id,v,u='')=>{{const el=document.getElementById(id);if(el&&v!=null)el.textContent=parseFloat(v).toFixed(2)+u;}};
  set('mEcbDep',r.ecb_deposit,'%'); set('mFed',r.fed_funds_proxy,'%'); set('mBund',b.bund_10y,'%');
  const vixEl=document.getElementById('mVix');
  if(vixEl&&ix.vix){{vixEl.textContent=parseFloat(ix.vix).toFixed(1);
    vixEl.style.color=ix.vix>25?'#D32F2F':ix.vix>18?'#FF9800':'#1D9E75';}}
  const moodEl=document.getElementById('mMood');
  if(moodEl&&ctx.market_mood){{
    const c=ctx.market_mood==='risk_on'?'#1D9E75':ctx.market_mood==='risk_off'?'#D32F2F':'#888780';
    moodEl.innerHTML=`<span class="mood-pill" style="background:${{c}}22;color:${{c}}">${{ctx.market_mood}}</span>`;
  }}
  const sEl=document.getElementById('mSummary');if(sEl&&ctx.summary)sEl.textContent=ctx.summary;
  document.getElementById('macroBanner').style.display='flex';
}})();

// Top picks
(function(){{
  const wrap=document.getElementById('topPicks');
  TOP_PICKS.forEach((p,i)=>{{
    const fd=FUNDS[p.isin]||{{}},st=ss(fd.signal_id),col=scoreColor(p.score_final);
    wrap.innerHTML+=`<div class="pick-card" onclick="openModal('${{p.isin}}')">
      <div class="pick-rank">#${{i+1}}</div>
      <div class="pick-cat">${{catLabel(p.cat_id)}}</div>
      <div class="pick-name">${{p.name}}</div>
      <div class="pick-score-row">
        <div class="score-circle" style="background:${{col}}">${{fmtScore(p.score_final)}}</div>
        <div><div class="signal-badge" style="background:${{st.bg}};color:${{st.color}}">${{st.emoji}} ${{p.signal_label}}</div></div>
      </div></div>`;
  }});
}})();

// Category grid
(function(){{
  const wrap=document.getElementById('catGrid'),catF=document.getElementById('catFilter');
  Object.entries(CAT_SUMMARY).forEach(([catId,cat])=>{{
    const sc=cat.avg_score,col=scoreColor(sc),pct=sc!=null?(sc/10*100).toFixed(0):0;
    const sentMap={{'fort_haussier':'fort_achat','haussier':'achat','neutre+':'neutre_plus',
      'neutre':'neutre','neutre-':'neutre_moins','baissier':'vente','fort_baissier':'fort_vente'}};
    const st=ss(sentMap[cat.sentiment]||'neutre');
    wrap.innerHTML+=`<div class="cat-card">
      <div class="cat-name">${{catLabel(catId)}}</div>
      <div class="cat-stat"><span>Score moyen</span><strong style="color:${{col}}">${{sc!=null?sc.toFixed(1):'—'}}</strong></div>
      <div class="cat-stat"><span>Sentiment</span>
        <span class="signal-badge" style="background:${{st.bg}};color:${{st.color}};font-size:.65rem;padding:2px 8px">${{st.emoji}} ${{cat.sentiment||'—'}}</span>
      </div>
      <div class="cat-stat"><span>Fonds</span><strong>${{cat.fund_count}}</strong></div>
      <div class="score-bar-wrap"><div class="score-bar" style="width:${{pct}}%;background:${{col}}"></div></div>
    </div>`;
    const opt=document.createElement('option');opt.value=catId;opt.textContent=catLabel(catId);catF.appendChild(opt);
  }});
}})();

// Fund table
let sortCol='rank_global',sortDir=1;
function buildTable(){{
  const q=document.getElementById('searchBox').value.toLowerCase();
  const catF=document.getElementById('catFilter').value;
  const sigF=document.getElementById('signalFilter').value;
  let rows=Object.entries(FUNDS).map(([isin,f])=>({{...f,isin}}));
  if(q) rows=rows.filter(f=>f.name.toLowerCase().includes(q)||f.isin.toLowerCase().includes(q));
  if(catF) rows=rows.filter(f=>f.cat_id===catF);
  if(sigF) rows=rows.filter(f=>f.signal_id===sigF);
  rows.sort((a,b)=>{{
    let va=a[sortCol],vb=b[sortCol];
    if(va==null) va=sortDir>0?Infinity:-Infinity;
    if(vb==null) vb=sortDir>0?Infinity:-Infinity;
    return (va<vb?-1:va>vb?1:0)*sortDir;
  }});
  const body=document.getElementById('fundsBody'),empty=document.getElementById('emptyState');
  if(!rows.length){{body.innerHTML='';empty.style.display='block';return;}}
  empty.style.display='none';
  body.innerHTML=rows.map(f=>{{
    const st=ss(f.signal_id),col=scoreColor(f.score_final);
    const mc=scoreColor(f.score_momentum),sc2=scoreColor(f.score_sentiment);
    const mp=f.score_momentum!=null?(f.score_momentum/10*100).toFixed(0):0;
    const sp=f.score_sentiment!=null?(f.score_sentiment/10*100).toFixed(0):0;
    return `<tr onclick="openModal('${{f.isin}}')">
      <td class="rank">${{f.rank_global??'—'}}</td>
      <td class="fund-name">${{f.name}}<br><span class="fund-isin">${{f.isin}}</span></td>
      <td>${{catLabel(f.cat_id)}}</td>
      <td class="srri-cell"><span class="srri-dot" style="background:${{srriColor(f.srri)}}">${{f.srri}}</span></td>
      <td><span class="score-pill" style="background:${{col}}22;color:${{col}}">${{fmtScore(f.score_final)}}</span></td>
      <td>${{fmtScore(f.score_momentum)}}<span class="mini-bar-wrap"><span class="mini-bar" style="width:${{mp}}%;background:${{mc}}"></span></span></td>
      <td>${{fmtScore(f.score_sentiment)}}<span class="mini-bar-wrap"><span class="mini-bar" style="width:${{sp}}%;background:${{sc2}}"></span></span></td>
      <td><span class="signal-badge" style="background:${{st.bg}};color:${{st.color}}">${{st.emoji}} ${{f.signal_label}}</span></td>
    </tr>`;
  }}).join('');
}}

document.querySelectorAll('thead th[data-col]').forEach(th=>{{
  th.addEventListener('click',()=>{{
    const col=th.dataset.col;
    if(sortCol===col) sortDir*=-1; else{{sortCol=col;sortDir=col==='rank_global'?1:-1;}}
    document.querySelectorAll('thead th').forEach(t=>t.classList.remove('sorted'));
    th.classList.add('sorted');
    th.querySelector('.sort-icon').textContent=sortDir>0?'↑':'↓';
    buildTable();
  }});
}});
document.getElementById('searchBox').addEventListener('input',buildTable);
document.getElementById('catFilter').addEventListener('change',buildTable);
document.getElementById('signalFilter').addEventListener('change',buildTable);
buildTable();

// Modal
function openModal(isin){{
  const f=FUNDS[isin];if(!f)return;
  const st=ss(f.signal_id),col=scoreColor(f.score_final);
  document.getElementById('mdCat').textContent=catLabel(f.cat_id);
  document.getElementById('mdTitle').textContent=f.name;
  document.getElementById('mdIsin').textContent=`ISIN : ${{isin}} · SRRI ${{f.srri}}`;
  document.getElementById('mdSignalLabel').textContent=f.signal_label||'—';
  document.getElementById('mdSignalEmoji').textContent=st.emoji+' '+(f.signal_id||'');
  const circ=document.getElementById('mdCircle');
  circ.style.background=col;circ.textContent=fmtScore(f.score_final);
  const momEl=document.getElementById('mdMom'),sentEl=document.getElementById('mdSent');
  momEl.textContent=fmtScore(f.score_momentum);momEl.style.color=scoreColor(f.score_momentum);
  sentEl.textContent=fmtScore(f.score_sentiment);sentEl.style.color=scoreColor(f.score_sentiment);
  document.getElementById('mdRankG').textContent=f.rank_global??'—';
  document.getElementById('mdRankC').textContent=`${{f.rank_cat??'—'}} / ${{CAT_SUMMARY[f.cat_id]?.fund_count??'—'}}`;
  document.getElementById('mdExpl').textContent=f.explanation||'Données insuffisantes.';
  const dSec=document.getElementById('mdDriversSection'),dList=document.getElementById('mdDrivers');
  if(f.drivers&&f.drivers.length){{
    dList.innerHTML=f.drivers.map(d=>`<li><span class="driver-dot"></span>${{d}}</li>`).join('');
    dSec.style.display='block';
  }}else dSec.style.display='none';

  // History chart
  const cSec=document.getElementById('mdChartSection');
  if(f.history&&f.history.length>1){{
    cSec.style.display='block';
    requestAnimationFrame(()=>requestAnimationFrame(()=>drawChart(f.history,col)));
  }}else cSec.style.display='none';

  document.getElementById('modalOverlay').classList.add('open');
}}

function drawChart(history,col){{
  const canvas=document.getElementById('mdChart');
  const W=canvas.parentElement.clientWidth||600,H=160;
  canvas.width=W;canvas.height=H;
  const ctx=canvas.getContext('2d');
  const vals=history.map(h=>h.vl),labels=history.map(h=>h.date);
  const minV=Math.min(...vals)*.995,maxV=Math.max(...vals)*1.005;
  const p={{t:10,r:10,b:30,l:52}},dw=W-p.l-p.r,dh=H-p.t-p.b;
  ctx.clearRect(0,0,W,H);
  ctx.strokeStyle='#e2e5ea';ctx.lineWidth=1;
  for(let i=0;i<=4;i++){{
    const y=p.t+dh*(1-i/4);
    ctx.beginPath();ctx.moveTo(p.l,y);ctx.lineTo(W-p.r,y);ctx.stroke();
    ctx.fillStyle='#9ca3af';ctx.font='10px sans-serif';ctx.textAlign='right';
    ctx.fillText((minV+(maxV-minV)*(i/4)).toFixed(2),p.l-4,y+3);
  }}
  const step=Math.max(1,Math.floor(labels.length/6));
  labels.forEach((lb,i)=>{{
    if(i%step===0){{
      const x=p.l+(i/(labels.length-1))*dw;
      ctx.fillStyle='#9ca3af';ctx.textAlign='center';ctx.fillText(lb.substring(0,7),x,H-8);
    }}
  }});
  const pts=vals.map((v,i)=>({{x:p.l+(i/(vals.length-1))*dw,y:p.t+dh*(1-(v-minV)/(maxV-minV))}}));
  const grad=ctx.createLinearGradient(0,p.t,0,H-p.b);
  grad.addColorStop(0,col+'55');grad.addColorStop(1,col+'00');
  ctx.beginPath();ctx.moveTo(pts[0].x,H-p.b);
  pts.forEach(pt=>ctx.lineTo(pt.x,pt.y));
  ctx.lineTo(pts[pts.length-1].x,H-p.b);ctx.closePath();
  ctx.fillStyle=grad;ctx.fill();
  ctx.beginPath();ctx.strokeStyle=col;ctx.lineWidth=2;
  pts.forEach((pt,i)=>i===0?ctx.moveTo(pt.x,pt.y):ctx.lineTo(pt.x,pt.y));
  ctx.stroke();
}}

document.getElementById('modalClose').onclick=()=>document.getElementById('modalOverlay').classList.remove('open');
document.getElementById('modalOverlay').onclick=e=>{{if(e.target===document.getElementById('modalOverlay'))document.getElementById('modalOverlay').classList.remove('open');}};
document.addEventListener('keydown',e=>{{if(e.key==='Escape')document.getElementById('modalOverlay').classList.remove('open');}});
</script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Génère le dashboard HTML predict-tempo")
    parser.add_argument("--out", default=str(OUT_DEFAULT), help="Fichier de sortie")
    parser.add_argument("--open", action="store_true", help="Ouvrir dans le navigateur")
    args = parser.parse_args()

    scores   = load_json(SCORES_PATH)
    momentum = load_json(MOMENTUM_PATH)

    if not scores:
        print("❌ data/scores.json vide. Lance d'abord scoring/engine.py", file=sys.stderr)
        sys.exit(1)

    html = generate_html(scores, momentum)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ Dashboard généré : {out_path}  ({len(scores.get('funds', {}))} fonds)")

    if args.open:
        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(out_path)])


if __name__ == "__main__":
    main()
