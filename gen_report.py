"""
gen_report.py — Générateur de rapport PDF hebdomadaire predict-tempo
====================================================================
Lit data/scores.json + data/sentiment.json + data/macro.json
et produit reports/predict_tempo_YYYYMMDD.pdf

Dépendances :
    pip install reportlab

Usage :
    python gen_report.py
    python gen_report.py --out /chemin/rapport.pdf
    python gen_report.py --open    # ouvre le PDF après génération
"""

import json
import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm, mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak, KeepTogether
    )
    from reportlab.graphics.shapes import Drawing, Rect, String, Circle, Line
    from reportlab.graphics import renderPDF
    from reportlab.graphics.charts.lineplots import LinePlot
    from reportlab.graphics.widgets.markers import makeMarker
except ImportError:
    print("❌ reportlab non installé. Lance : pip3 install reportlab", file=sys.stderr)
    sys.exit(1)

# ── Chemins ────────────────────────────────────────────────────────────────
ROOT          = Path(__file__).parent
DATA          = ROOT / "data"
REPORTS_DIR   = ROOT / "reports"
SCORES_PATH   = DATA / "scores.json"
SENTIMENT_PATH = DATA / "sentiment.json"
MACRO_PATH    = DATA / "macro.json"

# ── Palette ────────────────────────────────────────────────────────────────
DARK_BLUE  = colors.HexColor("#1a1a2e")
MID_BLUE   = colors.HexColor("#0f3460")
ACCENT     = colors.HexColor("#3266ad")
GREEN      = colors.HexColor("#1D9E75")
RED        = colors.HexColor("#D32F2F")
ORANGE     = colors.HexColor("#FF9800")
LIGHT_GREY = colors.HexColor("#f0f2f5")
BORDER     = colors.HexColor("#e2e5ea")
MUTED      = colors.HexColor("#6b7280")
WHITE      = colors.white
BLACK      = colors.black

SIGNAL_COLORS = {
    "fort_achat":   colors.HexColor("#1D9E75"),
    "achat":        colors.HexColor("#2ecc71"),
    "neutre_plus":  colors.HexColor("#8BC34A"),
    "neutre":       colors.HexColor("#888780"),
    "neutre_moins": colors.HexColor("#FF9800"),
    "vente":        colors.HexColor("#FF5722"),
    "fort_vente":   colors.HexColor("#D32F2F"),
    "inconnu":      colors.HexColor("#9e9e9e"),
}

SIGNAL_LABELS = {
    "fort_achat":   "Fort achat 🚀",
    "achat":        "Achat 📈",
    "neutre_plus":  "Neutre+ ↗",
    "neutre":       "Neutre →",
    "neutre_moins": "Neutre- ↘",
    "vente":        "Vente 📉",
    "fort_vente":   "Fort vente 🔻",
    "inconnu":      "—",
}

CAT_LABELS = {
    "monetaire":          "Monétaire",
    "oblig_eur_ct":       "Obligations EUR CT",
    "oblig_eur_lt":       "Obligations EUR LT",
    "oblig_us":           "Obligations US",
    "diversifie_prudent": "Diversifié Prudent",
    "diversifie_equilib": "Diversifié Équilibré",
    "actions_eur":        "Actions Europe",
    "actions_monde":      "Actions Monde",
}

PAGE_W, PAGE_H = A4
MARGIN = 1.8 * cm


# ── Helpers ────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def signal_color(sig: str):
    return SIGNAL_COLORS.get(sig, SIGNAL_COLORS["inconnu"])


def score_color(score):
    if score is None:
        return SIGNAL_COLORS["inconnu"]
    if score >= 8.0: return SIGNAL_COLORS["fort_achat"]
    if score >= 6.5: return SIGNAL_COLORS["achat"]
    if score >= 5.5: return SIGNAL_COLORS["neutre_plus"]
    if score >= 4.5: return SIGNAL_COLORS["neutre"]
    if score >= 3.5: return SIGNAL_COLORS["neutre_moins"]
    if score >= 2.0: return SIGNAL_COLORS["vente"]
    return SIGNAL_COLORS["fort_vente"]


def fmt_score(s) -> str:
    return f"{s:.1f}" if s is not None else "—"


def fmt_pct(v) -> str:
    return f"{v*100:+.2f}%" if v is not None else "—"


def fmt_rate(v) -> str:
    return f"{float(v):.2f}%" if v is not None else "—"


def week_label() -> str:
    now = datetime.now()
    return f"Semaine {now.isocalendar()[1]} — {now.strftime('%d %B %Y')}"


# ── Score gauge (mini drawing) ─────────────────────────────────────────────

def score_gauge(score, size=28) -> Drawing:
    """Cercle coloré avec le score centré."""
    d = Drawing(size, size)
    col = score_color(score)
    d.add(Circle(size / 2, size / 2, size / 2 - 1, fillColor=col, strokeColor=None))
    d.add(String(
        size / 2, size / 2 - 4,
        fmt_score(score),
        fontSize=10 if size >= 28 else 8,
        fillColor=WHITE,
        textAnchor="middle",
        fontName="Helvetica-Bold",
    ))
    return d


# ── Styles ─────────────────────────────────────────────────────────────────

def build_styles():
    base = getSampleStyleSheet()
    styles = {}

    def s(name, **kw):
        styles[name] = ParagraphStyle(name, **kw)

    s("cover_title",
      fontName="Helvetica-Bold", fontSize=32, textColor=WHITE,
      alignment=TA_CENTER, leading=38)
    s("cover_sub",
      fontName="Helvetica", fontSize=14, textColor=colors.HexColor("#94a3b8"),
      alignment=TA_CENTER, leading=20)
    s("cover_date",
      fontName="Helvetica", fontSize=11, textColor=colors.HexColor("#64748b"),
      alignment=TA_CENTER)
    s("section_title",
      fontName="Helvetica-Bold", fontSize=13, textColor=DARK_BLUE,
      spaceBefore=16, spaceAfter=8, leading=16)
    s("subsection",
      fontName="Helvetica-Bold", fontSize=10, textColor=ACCENT,
      spaceBefore=10, spaceAfter=4)
    s("body",
      fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#374151"),
      leading=14, spaceAfter=4)
    s("muted",
      fontName="Helvetica", fontSize=8, textColor=MUTED, leading=12)
    s("disclaimer",
      fontName="Helvetica-Oblique", fontSize=7.5, textColor=MUTED,
      leading=11, spaceBefore=8)
    s("table_header",
      fontName="Helvetica-Bold", fontSize=8, textColor=WHITE, alignment=TA_CENTER)
    s("table_cell",
      fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#1f2937"), leading=11)
    s("table_cell_center",
      fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#1f2937"),
      alignment=TA_CENTER, leading=11)
    s("pick_name",
      fontName="Helvetica-Bold", fontSize=9.5, textColor=DARK_BLUE, leading=12)
    s("pick_cat",
      fontName="Helvetica", fontSize=7.5, textColor=MUTED, leading=10)
    s("pick_expl",
      fontName="Helvetica-Oblique", fontSize=8, textColor=MUTED, leading=11)
    return styles


# ── Cover page ─────────────────────────────────────────────────────────────

def cover_page(styles, date_str: str, week_str: str) -> list:
    story = []

    # Dark header background via a coloured box
    header_bg = Drawing(PAGE_W - 2 * MARGIN, 120)
    header_bg.add(Rect(0, 0, PAGE_W - 2 * MARGIN, 120,
                        fillColor=DARK_BLUE, strokeColor=None, rx=8, ry=8))
    header_bg.add(String(
        (PAGE_W - 2 * MARGIN) / 2, 72,
        "⚡ predict-tempo",
        fontSize=28, fontName="Helvetica-Bold",
        fillColor=WHITE, textAnchor="middle",
    ))
    header_bg.add(String(
        (PAGE_W - 2 * MARGIN) / 2, 48,
        "Rapport hebdomadaire — Analyse prédictive des fonds",
        fontSize=12, fontName="Helvetica",
        fillColor=colors.HexColor("#94a3b8"), textAnchor="middle",
    ))
    header_bg.add(String(
        (PAGE_W - 2 * MARGIN) / 2, 24,
        week_str,
        fontSize=10, fontName="Helvetica",
        fillColor=colors.HexColor("#64748b"), textAnchor="middle",
    ))
    story.append(header_bg)
    story.append(Spacer(1, 0.4 * cm))

    # Metadata line
    story.append(Paragraph(
        f"<font color='#6b7280'>Généré le {date_str} · Modèle : momentum 60% + sentiment LLM 40%</font>",
        styles["muted"],
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=6))
    return story


# ── Macro section ──────────────────────────────────────────────────────────

def macro_section(styles, macro: dict) -> list:
    if not macro or not macro.get("rates"):
        return []

    story = [Paragraph("Contexte Macroéconomique", styles["section_title"])]

    r   = macro.get("rates", {})
    b   = macro.get("bonds", {})
    ix  = macro.get("indices", {})
    ctx = macro.get("context", {})

    # Key rates table
    rate_data = [
        [Paragraph("Indicateur", styles["table_header"]),
         Paragraph("Valeur", styles["table_header"]),
         Paragraph("Indicateur", styles["table_header"]),
         Paragraph("Valeur", styles["table_header"])],
        ["Taux BCE dépôt",  fmt_rate(r.get("ecb_deposit")),
         "Taux Fed (proxy)", fmt_rate(r.get("fed_funds_proxy"))],
        ["Bund 10y",        fmt_rate(b.get("bund_10y")),
         "OAT 10y",         fmt_rate(b.get("oat_10y"))],
        ["VIX",             fmt_score(ix.get("vix")) if ix.get("vix") else "—",
         "CAC 40",          f"{ix.get('cac40', '—')}"],
        ["Spread courbe",   fmt_rate(ctx.get("yield_curve_spread")),
         "Humeur marché",   str(ctx.get("market_mood", "—"))],
    ]

    col_w = [(PAGE_W - 2 * MARGIN) / 4] * 4
    t = Table(rate_data, colWidths=col_w)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK_BLUE),
        ("BACKGROUND", (0, 1), (-1, -1), LIGHT_GREY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GREY]),
        ("FONTNAME",   (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",   (0, 1), (-1, -1), 8.5),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN",      (1, 0), (1, -1), "CENTER"),
        ("ALIGN",      (3, 0), (3, -1), "CENTER"),
        ("FONTNAME",   (1, 1), (1, -1), "Helvetica-Bold"),
        ("FONTNAME",   (3, 1), (3, -1), "Helvetica-Bold"),
        ("TEXTCOLOR",  (1, 1), (1, -1), ACCENT),
        ("TEXTCOLOR",  (3, 1), (3, -1), ACCENT),
        ("GRID",       (0, 0), (-1, -1), 0.5, BORDER),
        ("PADDING",    (0, 0), (-1, -1), 5),
        ("ROWPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)

    if ctx.get("summary"):
        story.append(Spacer(1, 0.25 * cm))
        story.append(Paragraph(
            f"<b>Synthèse macro :</b> {ctx['summary']}",
            styles["body"],
        ))

    story.append(Spacer(1, 0.3 * cm))
    return story


# ── Top picks section ──────────────────────────────────────────────────────

def top_picks_section(styles, top_picks: list, funds: dict) -> list:
    story = [Paragraph("Top 5 — Meilleures Opportunités", styles["section_title"])]

    for i, p in enumerate(top_picks[:5], 1):
        fd  = funds.get(p["isin"], {})
        col = score_color(p.get("score_final"))

        # Left gauge circle
        gauge = score_gauge(p.get("score_final"), size=36)

        # Right text block
        sig_col = signal_color(fd.get("signal_id", "inconnu"))
        sig_label = SIGNAL_LABELS.get(fd.get("signal_id", ""), "—")

        badge_draw = Drawing(80, 16)
        badge_draw.add(Rect(0, 0, 80, 16, fillColor=sig_col, strokeColor=None, rx=8, ry=8))
        badge_draw.add(String(40, 4, sig_label.replace("🚀","").replace("📈","").replace("📉","").strip(),
                               fontSize=7.5, fontName="Helvetica-Bold",
                               fillColor=WHITE, textAnchor="middle"))

        name_para  = Paragraph(f"#{i} — {p['name']}", styles["pick_name"])
        cat_para   = Paragraph(
            f"{CAT_LABELS.get(p.get('cat_id',''),'—')} · ISIN {p['isin']} · SRRI {fd.get('srri','—')}",
            styles["pick_cat"],
        )
        expl_para  = Paragraph(fd.get("explanation", ""), styles["pick_expl"])

        # Sub-scores
        mom  = fd.get("score_momentum")
        sent = fd.get("score_sentiment")
        sub  = f"Momentum : <b>{fmt_score(mom)}/10</b>  |  Sentiment : <b>{fmt_score(sent)}/10</b>"
        sub_para = Paragraph(sub, styles["muted"])

        row_data = [[gauge, [name_para, cat_para, sub_para, badge_draw, expl_para]]]
        t = Table(row_data, colWidths=[42, PAGE_W - 2 * MARGIN - 42])
        t.setStyle(TableStyle([
            ("VALIGN",  (0, 0), (-1, -1), "TOP"),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("BACKGROUND", (0, 0), (-1, -1), WHITE),
            ("BOX",     (0, 0), (-1, -1), 0.5, BORDER),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, BORDER),
            ("LEFTPADDING", (0, 0), (0, -1), 8),
            ("TOPPADDING",  (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(KeepTogether([t, Spacer(1, 0.2 * cm)]))

    return story


# ── Category summary section ───────────────────────────────────────────────

def category_section(styles, cat_summary: dict, sentiment_data: dict) -> list:
    story = [
        PageBreak(),
        Paragraph("Analyse par Catégorie", styles["section_title"]),
    ]

    sent_cats = sentiment_data.get("categories", {})

    header = [
        Paragraph("Catégorie",      styles["table_header"]),
        Paragraph("Score moy.",     styles["table_header"]),
        Paragraph("Signal macro",   styles["table_header"]),
        Paragraph("Score sent.",    styles["table_header"]),
        Paragraph("Nb fonds",       styles["table_header"]),
        Paragraph("Top fonds",      styles["table_header"]),
    ]

    rows = [header]
    for cat_id, cat in cat_summary.items():
        sent_entry = sent_cats.get(cat_id, {})
        sent_signal = sent_entry.get("signal", "—")
        sent_score  = sent_entry.get("score")
        sent_score_10 = round((sent_score + 1) * 5, 1) if sent_score is not None else None

        rows.append([
            Paragraph(CAT_LABELS.get(cat_id, cat_id), styles["table_cell"]),
            Paragraph(fmt_score(cat.get("avg_score")),  styles["table_cell_center"]),
            Paragraph(str(sent_signal), styles["table_cell_center"]),
            Paragraph(fmt_score(sent_score_10), styles["table_cell_center"]),
            Paragraph(str(cat.get("fund_count", "—")), styles["table_cell_center"]),
            Paragraph(str(cat.get("top_fund", "—"))[:40], styles["table_cell"]),
        ])

    col_w = [4.2*cm, 1.6*cm, 2.4*cm, 1.8*cm, 1.4*cm, None]
    remaining = PAGE_W - 2 * MARGIN - sum(w for w in col_w if w)
    col_w[-1] = remaining

    t = Table(rows, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  DARK_BLUE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GREY]),
        ("GRID",         (0, 0), (-1, -1), 0.5, BORDER),
        ("PADDING",      (0, 0), (-1, -1), 5),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",        (1, 1), (4, -1),  "CENTER"),
    ]))

    # Colorize score cells
    for i, (cat_id, cat) in enumerate(cat_summary.items(), 1):
        sc = cat.get("avg_score")
        if sc is not None:
            col = score_color(sc)
            t.setStyle(TableStyle([
                ("TEXTCOLOR",  (1, i), (1, i), col),
                ("FONTNAME",   (1, i), (1, i), "Helvetica-Bold"),
            ]))

    story.append(t)

    # Sentiment details
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("Détail du Sentiment LLM par Catégorie", styles["subsection"]))

    for cat_id, entry in sent_cats.items():
        rationale = entry.get("rationale", "")
        kw        = entry.get("keywords", [])
        if not rationale:
            continue
        story.append(Paragraph(
            f"<b>{CAT_LABELS.get(cat_id, cat_id)}</b> — signal : <i>{entry.get('signal','—')}</i>",
            styles["body"],
        ))
        story.append(Paragraph(rationale[:300] + ("…" if len(rationale) > 300 else ""), styles["muted"]))
        if kw:
            story.append(Paragraph(f"Mots-clés : {', '.join(kw[:8])}", styles["muted"]))
        story.append(Spacer(1, 0.15 * cm))

    return story


# ── Full fund table ────────────────────────────────────────────────────────

def full_fund_table(styles, funds: dict) -> list:
    story = [
        PageBreak(),
        Paragraph("Classement Complet des Fonds", styles["section_title"]),
    ]

    header = [
        Paragraph("Rang",      styles["table_header"]),
        Paragraph("Fonds",     styles["table_header"]),
        Paragraph("Catégorie", styles["table_header"]),
        Paragraph("SRRI",      styles["table_header"]),
        Paragraph("Score",     styles["table_header"]),
        Paragraph("Momentum",  styles["table_header"]),
        Paragraph("Sentiment", styles["table_header"]),
        Paragraph("Signal",    styles["table_header"]),
    ]

    # Sort by rank_global
    sorted_funds = sorted(
        [(isin, fd) for isin, fd in funds.items() if fd.get("rank_global") is not None],
        key=lambda x: x[1]["rank_global"],
    )
    # Append unranked
    sorted_funds += [
        (isin, fd) for isin, fd in funds.items() if fd.get("rank_global") is None
    ]

    rows = [header]
    for isin, fd in sorted_funds:
        sig_col   = signal_color(fd.get("signal_id", "inconnu"))
        sig_label = SIGNAL_LABELS.get(fd.get("signal_id", ""), "—")
        # Strip emoji for PDF
        sig_text  = sig_label.replace("🚀","").replace("📈","").replace("📉","").replace("↗","↗").replace("↘","↘").strip()

        rows.append([
            Paragraph(str(fd.get("rank_global", "—")),  styles["table_cell_center"]),
            Paragraph(f"{fd.get('name','')}\n{isin}",   styles["table_cell"]),
            Paragraph(CAT_LABELS.get(fd.get("cat_id",""),""), styles["table_cell"]),
            Paragraph(str(fd.get("srri","—")),           styles["table_cell_center"]),
            Paragraph(fmt_score(fd.get("score_final")), styles["table_cell_center"]),
            Paragraph(fmt_score(fd.get("score_momentum")), styles["table_cell_center"]),
            Paragraph(fmt_score(fd.get("score_sentiment")), styles["table_cell_center"]),
            Paragraph(sig_text, styles["table_cell_center"]),
        ])

    col_w = [0.9*cm, 5.5*cm, 3.2*cm, 1.0*cm, 1.2*cm, 1.6*cm, 1.6*cm, 2.0*cm]
    t = Table(rows, colWidths=col_w, repeatRows=1)

    ts = TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),   DARK_BLUE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),  [WHITE, LIGHT_GREY]),
        ("GRID",           (0, 0), (-1, -1),  0.3, BORDER),
        ("FONTSIZE",       (0, 0), (-1, -1),  7.5),
        ("PADDING",        (0, 0), (-1, -1),  4),
        ("VALIGN",         (0, 0), (-1, -1),  "MIDDLE"),
        ("ALIGN",          (0, 0), (0, -1),   "CENTER"),
        ("ALIGN",          (3, 0), (-1, -1),  "CENTER"),
    ])

    # Colorize score column
    for i, (isin, fd) in enumerate(sorted_funds, 1):
        sc = fd.get("score_final")
        if sc is not None:
            col = score_color(sc)
            ts.add("TEXTCOLOR",  (4, i), (4, i), col)
            ts.add("FONTNAME",   (4, i), (4, i), "Helvetica-Bold")
        # Signal cell background
        sig = fd.get("signal_id", "inconnu")
        scol = signal_color(sig)
        ts.add("TEXTCOLOR",  (7, i), (7, i), scol)
        ts.add("FONTNAME",   (7, i), (7, i), "Helvetica-Bold")

    t.setStyle(ts)
    story.append(t)
    return story


# ── Disclaimer ─────────────────────────────────────────────────────────────

def disclaimer_section(styles) -> list:
    return [
        Spacer(1, 0.5 * cm),
        HRFlowable(width="100%", thickness=0.5, color=BORDER),
        Paragraph(
            "Les performances passées ne préjugent pas des performances futures. "
            "Ce rapport est généré automatiquement à partir de données publiques (cours, "
            "actualités, données macroéconomiques) et d'un modèle d'analyse basé sur "
            "l'intelligence artificielle. Il ne constitue pas un conseil en investissement. "
            "Les scores et signaux présentés sont des outils d'aide à la décision et non "
            "des recommandations d'achat ou de vente. L'investisseur reste seul responsable "
            "de ses décisions d'investissement.",
            styles["disclaimer"],
        ),
    ]


# ── Page numbering ─────────────────────────────────────────────────────────

class _PageNumCanvas:
    """SimpleDocTemplate canvas wrapper pour numéros de page."""
    def __init__(self, *args, **kwargs):
        from reportlab.pdfgen.canvas import Canvas
        self._canvas = Canvas(*args, **kwargs)
        self._saved_page_states = []

    def __getattr__(self, name):
        return getattr(self._canvas, name)

    def showPage(self):
        self._saved_page_states.append(dict(self._canvas.__dict__))
        self._canvas._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self._canvas.__dict__.update(state)
            self._draw_page_number(num_pages)
            self._canvas.showPage()
        self._canvas.save()

    def _draw_page_number(self, page_count):
        self._canvas.setFont("Helvetica", 7.5)
        self._canvas.setFillColor(MUTED)
        self._canvas.drawRightString(
            PAGE_W - MARGIN, MARGIN * 0.6,
            f"predict-tempo · Page {self._canvas._pageNumber} / {page_count}"
        )


# ── Main builder ───────────────────────────────────────────────────────────

def generate_report(scores: dict, sentiment: dict, macro: dict, out_path: Path) -> None:
    styles  = build_styles()
    funds   = scores.get("funds", {})
    top5    = scores.get("top_picks", [])
    cat_sum = scores.get("category_summary", {})

    now      = datetime.now()
    date_str = now.strftime("%d/%m/%Y à %H:%M")
    week_str = week_label()

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN,  bottomMargin=MARGIN * 1.2,
        title="predict-tempo — Rapport hebdomadaire",
        author="predict-tempo",
    )

    story: list = []

    # 1. Cover
    story += cover_page(styles, date_str, week_str)
    story.append(Spacer(1, 0.3 * cm))

    # 2. Executive summary
    story.append(Paragraph("Résumé Exécutif", styles["section_title"]))
    n_scored = sum(1 for f in funds.values() if f.get("score_final") is not None)
    n_achat  = sum(1 for f in funds.values() if f.get("signal_id") in ("fort_achat", "achat"))
    n_vente  = sum(1 for f in funds.values() if f.get("signal_id") in ("fort_vente", "vente"))
    global_macro_ctx = scores.get("global_macro", macro.get("context", {}))
    mood = global_macro_ctx.get("market_mood", "—")
    weights = scores.get("weights", {})

    story.append(Paragraph(
        f"Cette analyse couvre <b>{n_scored} fonds</b> répartis en {len(cat_sum)} catégories. "
        f"Le modèle combine le momentum historique (<b>{int(weights.get('momentum',0.6)*100)}%</b>) "
        f"et l'analyse LLM macro/news (<b>{int(weights.get('sentiment',0.4)*100)}%</b>). "
        f"<b>{n_achat} fonds</b> affichent un signal d'achat ou fort achat, "
        f"<b>{n_vente} fonds</b> un signal de vente ou fort vente. "
        f"L'humeur générale des marchés est actuellement : <b>{mood}</b>.",
        styles["body"],
    ))

    if global_macro_ctx.get("summary"):
        story.append(Paragraph(global_macro_ctx["summary"], styles["muted"]))

    story.append(Spacer(1, 0.3 * cm))

    # 3. Macro
    macro_data = macro if macro else scores.get("global_macro", {})
    story += macro_section(styles, macro_data)

    # 4. Top picks
    story += top_picks_section(styles, top5, funds)

    # 5. Category breakdown
    story += category_section(styles, cat_sum, sentiment)

    # 6. Full fund table
    story += full_fund_table(styles, funds)

    # 7. Disclaimer
    story += disclaimer_section(styles)

    doc.build(story)
    print(f"✅ Rapport PDF généré : {out_path}")


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Génère le rapport PDF hebdomadaire predict-tempo")
    parser.add_argument("--out", default="", help="Fichier de sortie (défaut : reports/predict_tempo_YYYYMMDD.pdf)")
    parser.add_argument("--open", action="store_true", help="Ouvrir le PDF après génération")
    args = parser.parse_args()

    scores    = load_json(SCORES_PATH)
    sentiment = load_json(SENTIMENT_PATH)
    macro     = load_json(MACRO_PATH)

    if not scores:
        print("❌ data/scores.json introuvable. Lance d'abord scoring/engine.py", file=sys.stderr)
        sys.exit(1)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.out:
        out_path = Path(args.out)
    else:
        date_tag = datetime.now().strftime("%Y%m%d")
        out_path = REPORTS_DIR / f"predict_tempo_{date_tag}.pdf"

    generate_report(scores, sentiment, macro, out_path)

    if args.open:
        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(out_path)])


if __name__ == "__main__":
    main()
