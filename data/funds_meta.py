"""
predict-tempo — Référentiel centralisé des fonds
Utilisé par tous les modules (scrapers, scoring, dashboard).

Structure par fonds :
  isin     : str   — code ISIN
  bid      : str   — identifiant Boursorama (ex: "0P0001CB5C")
  name     : str   — nom du fonds
  mgr      : str   — société de gestion
  cat_id   : str   — identifiant catégorie (ex: "monetaire")
  cat_label: str   — libellé catégorie (ex: "Monétaire / Oblig. CT")
  srri     : int   — niveau de risque 1-7
"""

CATEGORIES = [
    {"id": "monetaire",    "label": "Monétaire / Oblig. CT",   "color": "#2a5298"},
    {"id": "oblig_lt",     "label": "Obligataire LT",          "color": "#2a5298"},
    {"id": "oblig_horizon","label": "Oblig. à Horizon",        "color": "#1a3a6b"},
    {"id": "mixtes_oblig", "label": "Mixtes Obligataires",     "color": "#0d6efd"},
    {"id": "actions_fr",   "label": "Actions Françaises",      "color": "#198754"},
    {"id": "actions_eu",   "label": "Actions Européennes",     "color": "#20c997"},
    {"id": "actions_int",  "label": "Actions Internationales", "color": "#fd7e14"},
    {"id": "flexibles",    "label": "Flexibles",               "color": "#6f42c1"},
]

FUNDS = [
    # ── Monétaire / Oblig. CT ──────────────────────────────────────────────
    {"isin":"FR0013287315","bid":"0P0001CB5C","name":"Palatine Monétaire Court Terme (R)","mgr":"Palatine AM","cat_id":"monetaire","srri":1},
    {"isin":"FR0011461326","bid":"0P0000ZL7Q","name":"Conservateur Oblig. CT (C)","mgr":"Conservateur Gestion Valor","cat_id":"monetaire","srri":1},
    {"isin":"LU1585265066","bid":"0P0001KJDD","name":"TF - Tikehau Short Duration (R)","mgr":"Tikehau IM","cat_id":"monetaire","srri":1},

    # ── Obligataire LT ─────────────────────────────────────────────────────
    {"isin":"LU1694790202","bid":"0P0001CH1A","name":"DNCA INVEST Flex Inflation","mgr":"DNCA Finance","cat_id":"oblig_lt","srri":3},
    {"isin":"FR0010915314","bid":"MP-805617", "name":"LF Obligations Carbon Impact C","mgr":"La Française AM Int.","cat_id":"oblig_lt","srri":3},
    {"isin":"FR0010564328","bid":"MP-460761", "name":"Conservateur Oblig. MT (C)","mgr":"Conservateur Gestion Valor","cat_id":"oblig_lt","srri":3},
    {"isin":"LU1752460292","bid":"0P0001EITS","name":"Oddo Sustainable Credit Optn CR","mgr":"Oddo AM","cat_id":"oblig_lt","srri":3},
    {"isin":"FR0013505450","bid":"0P0001KE62","name":"Tikehau 2027 (R-Acc-EUR)","mgr":"Tikehau IM","cat_id":"oblig_lt","srri":2},
    {"isin":"FR001400K2B5","bid":"0P0001S8T9","name":"Tikehau 2029 (R-Acc-EUR)","mgr":"Tikehau IM","cat_id":"oblig_lt","srri":2},

    # ── Oblig. à Horizon ───────────────────────────────────────────────────
    {"isin":"FR0013398294","bid":"0P0001HS9U","name":"Conservateur Horizon 2027 (I)","mgr":"Conservateur Gestion Valor","cat_id":"oblig_horizon","srri":2},
    {"isin":"FR0013426657","bid":"0P0001IFLQ","name":"Oddo BHF Global Target 2026 (CR)","mgr":"Oddo AM","cat_id":"oblig_horizon","srri":2},
    {"isin":"FR0013398302","bid":"0P0001HS9V","name":"Conservateur Horizon 2027 (C)","mgr":"Conservateur Gestion Valor","cat_id":"oblig_horizon","srri":2},
    {"isin":"FR001400PKZ3","bid":"0P0001UGT4","name":"Conservateur Horizon 2031 (I)","mgr":"Conservateur Gestion Valor","cat_id":"oblig_horizon","srri":2},
    {"isin":"FR001400PL02","bid":"0P0001UGT3","name":"Conservateur Horizon 2031 (C)","mgr":"Conservateur Gestion Valor","cat_id":"oblig_horizon","srri":2},

    # ── Mixtes Obligataires ────────────────────────────────────────────────
    {"isin":"LU0512124107","bid":"0P0000P3DN","name":"DNCA Invest - Convertibles (B)","mgr":"DNCA Finance","cat_id":"mixtes_oblig","srri":4},
    {"isin":"FR0010135103","bid":"MP-829413", "name":"Carmignac Patrimoine (A)","mgr":"Carmignac Gestion","cat_id":"mixtes_oblig","srri":4},
    {"isin":"FR0010564336","bid":"MP-495318", "name":"Conservateur Diversifié (C)","mgr":"Conservateur Gestion Valor","cat_id":"mixtes_oblig","srri":4},
    {"isin":"LU0284394235","bid":"0P0000NHMO","name":"DNCA Invest - Eurose (A)","mgr":"DNCA Finance","cat_id":"mixtes_oblig","srri":3},
    {"isin":"FR0011199314","bid":"0P0000VYE0","name":"Conservateur Immo-Or (C)","mgr":"Conservateur Gestion Valor","cat_id":"mixtes_oblig","srri":4},
    {"isin":"FR0010489542","bid":"MP-514618", "name":"Conservateur Diversifié Réactif (C)","mgr":"Conservateur Gestion Valor","cat_id":"mixtes_oblig","srri":4},
    {"isin":"FR0007439666","bid":"0P00005VUH","name":"Congrégation Investissement (C)","mgr":"Conservateur Gestion Valor","cat_id":"mixtes_oblig","srri":4},
    {"isin":"FR001400UAZ4","bid":"0P0001XK54","name":"Congrégation Investissement (R)","mgr":"Conservateur Gestion Valor","cat_id":"mixtes_oblig","srri":4},
    {"isin":"FR0013087152","bid":"0P00019OMO","name":"Conservateur Rendement Flexible (C)","mgr":"Conservateur Gestion Valor","cat_id":"mixtes_oblig","srri":4},
    {"isin":"LU1694789451","bid":"0P0001CH1D","name":"DNCA Invest Alpha Bonds (A)","mgr":"DNCA Finance","cat_id":"mixtes_oblig","srri":3},

    # ── Actions Françaises ─────────────────────────────────────────────────
    {"isin":"FR0007076930","bid":"MP-805274", "name":"Centifolia (C)","mgr":"DNCA Finance","cat_id":"actions_fr","srri":6},
    {"isin":"FR001400U512","bid":"0P0001UVBG","name":"Conservateur Investissement Proximité (C)","mgr":"Conservateur Gestion Valor","cat_id":"actions_fr","srri":6},
    {"isin":"FR0000989899","bid":"MP-802731", "name":"Oddo BHF Avenir (CR)","mgr":"Oddo AM","cat_id":"actions_fr","srri":6},
    {"isin":"FR0010547869","bid":"MP-928594", "name":"SEXTANT PME-A","mgr":"Amiral Gestion","cat_id":"actions_fr","srri":6},
    {"isin":"FR0000978439","bid":"MP-800357", "name":"Palatine France Small Cap (I)","mgr":"Palatine AM","cat_id":"actions_fr","srri":6},
    {"isin":"FR0010574434","bid":"MP-828166", "name":"Oddo BHF Génération (CR)","mgr":"Oddo AM","cat_id":"actions_fr","srri":6},

    # ── Actions Européennes ────────────────────────────────────────────────
    {"isin":"FR0010321810","bid":"MP-805948", "name":"Echiquier Agenor Mid Cap Europe (A)","mgr":"Financière de l'Echiquier","cat_id":"actions_eu","srri":6},
    {"isin":"FR0010106500","bid":"MP-420630", "name":"Echiquier Excelsior A","mgr":"Financière de l'Echiquier","cat_id":"actions_eu","srri":6},
    {"isin":"FR0000983819","bid":"MP-805200", "name":"OFI Croiss Durable & Solidaire C","mgr":"OFI AM","cat_id":"actions_eu","srri":6},
    {"isin":"FR0014008EH4","bid":"0P0001P8TC","name":"Conservateur Actions Euro (I)","mgr":"Conservateur Gestion Valor","cat_id":"actions_eu","srri":6},
    {"isin":"FR0011606268","bid":"0P00011IDZ","name":"Oddo BHF Active SMALL CAP (CR)","mgr":"Oddo AM","cat_id":"actions_eu","srri":6},
    {"isin":"FR0014008EI2","bid":"0P0001P8TA","name":"Conservateur Actions Euro (C)","mgr":"Conservateur Gestion Valor","cat_id":"actions_eu","srri":6},
    {"isin":"FR0010321802","bid":"MP-800952", "name":"Echiquier Agressor (A)","mgr":"Financière de l'Echiquier","cat_id":"actions_eu","srri":6},
    {"isin":"FR0000989915","bid":"MP-800743", "name":"Oddo BHF Immobilier (CR)","mgr":"Oddo AM","cat_id":"actions_eu","srri":5},
    {"isin":"FR0010298596","bid":"MP-807288", "name":"Moneta Multi Caps (C)","mgr":"Moneta AM","cat_id":"actions_eu","srri":6},
    {"isin":"FR0013256930","bid":"0P0001HI3U","name":"Conservateur Actions Flexibles (C)","mgr":"Conservateur Gestion Valor","cat_id":"actions_eu","srri":5},
    {"isin":"LU0870553020","bid":"0P0000XTFD","name":"DNCA Invest SRI Europe Growth (A)","mgr":"DNCA Finance","cat_id":"actions_eu","srri":6},
    {"isin":"FR0010149179","bid":"MP-802605", "name":"Carmignac Absolute Return Europe (A)","mgr":"Carmignac Gestion","cat_id":"actions_eu","srri":5},
    {"isin":"FR0010038257","bid":"MP-806670", "name":"Conservateur Emploi Durable (C)","mgr":"Palatine AM","cat_id":"actions_eu","srri":6},
    {"isin":"LU1490785091","bid":"0P000195NQ","name":"DNCA Invest SRI Norden Europe A","mgr":"DNCA Finance","cat_id":"actions_eu","srri":6},

    # ── Actions Internationales ────────────────────────────────────────────
    {"isin":"LU0280435388","bid":"MP-990541", "name":"Pictet - Clean Energy Transition (P)","mgr":"Pictet AM Europe","cat_id":"actions_int","srri":7},
    {"isin":"FR0000292278","bid":"MP-829227", "name":"Magellan (C)","mgr":"Comgest AM","cat_id":"actions_int","srri":6},
    {"isin":"FR0010649079","bid":"MP-534378", "name":"Palatine Planète (R)","mgr":"Palatine AM","cat_id":"actions_int","srri":6},
    {"isin":"LU0115768185","bid":"MP-356085", "name":"FF - Sustainable Asia Equity Fund (E)","mgr":"Fidelity AM","cat_id":"actions_int","srri":6},
    {"isin":"LU1744646933","bid":"0P0001DK5M","name":"LF IP Carbon Impact Global R","mgr":"La Française AM Int.","cat_id":"actions_int","srri":6},
    {"isin":"LU1819480192","bid":"0P0001DYQM","name":"Echiquier Artificial Intelligence (B)","mgr":"Financière de l'Echiquier","cat_id":"actions_int","srri":7},
    {"isin":"LU0592698954","bid":"0P0000TIYB","name":"Carmignac Portf. Emerging Patrimoine (A)","mgr":"Carmignac Gestion","cat_id":"actions_int","srri":6},
    {"isin":"LU0592699093","bid":"0P0000TIYE","name":"Carmignac Portf. Emerging Patrimoine (E)","mgr":"Carmignac Gestion","cat_id":"actions_int","srri":6},
    {"isin":"LU2254337392","bid":"0P0001LOB8","name":"DNCA INVEST - Beyond Climate (A)","mgr":"DNCA Finance","cat_id":"actions_int","srri":6},
    {"isin":"FR0010148981","bid":"MP-800128", "name":"Carmignac Investissement (A)","mgr":"Carmignac Gestion","cat_id":"actions_int","srri":6},
    {"isin":"FR0010863688","bid":"MP-664642", "name":"Echiquier Positive Impact (A)","mgr":"Financière de l'Echiquier","cat_id":"actions_int","srri":6},
    {"isin":"LU1261432659","bid":"0P00016FY4","name":"FF - World Fund (A)","mgr":"Fidelity AM","cat_id":"actions_int","srri":6},
    {"isin":"LU1902443420","bid":"0P0001FLNU","name":"CPR Invest Climate Action (A)","mgr":"CPR AM","cat_id":"actions_int","srri":6},
    {"isin":"FR0010564229","bid":"MP-460332", "name":"Conservateur Actions Monde (C)","mgr":"Conservateur Gestion Valor","cat_id":"actions_int","srri":6},
    {"isin":"LU1103305709","bid":"0P000172SH","name":"EdR Fund - Us Value (R)","mgr":"Edmond de Rothschild AM","cat_id":"actions_int","srri":6},
    {"isin":"LU1244893696","bid":"0P00016P7T","name":"EdR Fund - Big Data (A)","mgr":"Edmond de Rothschild AM","cat_id":"actions_int","srri":6},
    {"isin":"LU1120766388","bid":"0P00016ALF","name":"Candriam Equities L Biotechnology (C)","mgr":"Candriam Lux","cat_id":"actions_int","srri":7},
    {"isin":"FR0000974149","bid":"MP-803486", "name":"Oddo BHF Avenir Europe (CR)","mgr":"Oddo AM","cat_id":"actions_int","srri":6},
    {"isin":"LU0528228074","bid":"0P0000VTJH","name":"FF - Sustainable Demographics Fund (A)","mgr":"Fidelity AM","cat_id":"actions_int","srri":6},
    {"isin":"LU1892829828","bid":"0P0001EVSZ","name":"FF - Sustainable Water & Waste Fund (A)","mgr":"Fidelity AM","cat_id":"actions_int","srri":6},
    {"isin":"LU1653748860","bid":"0P0001BOX5","name":"CPR Invest - Food For Generations (A)","mgr":"CPR AM","cat_id":"actions_int","srri":6},
    {"isin":"FR0012844140","bid":"0P00016HZ8","name":"CPR Global Silver Age (E)","mgr":"CPR AM","cat_id":"actions_int","srri":6},
    {"isin":"LU1160365091","bid":"0P00016716","name":"EdR Fund - China (A)","mgr":"Edmond de Rothschild AM","cat_id":"actions_int","srri":7},
    {"isin":"LU0366534344","bid":"MP-521217", "name":"Pictet - Nutrition (P)","mgr":"Pictet AM Europe","cat_id":"actions_int","srri":6},
    {"isin":"FR0000295230","bid":"MP-829523", "name":"Comgest Renaissance Europe (C)","mgr":"Comgest AM","cat_id":"actions_int","srri":6},
    {"isin":"LU0217139020","bid":"MP-119337", "name":"Pictet - Premium Brands (P)","mgr":"Pictet AM Europe","cat_id":"actions_int","srri":5},
    {"isin":"FR0010479931","bid":"MP-806384", "name":"EdR India (A)","mgr":"Edmond de Rothschild AM","cat_id":"actions_int","srri":7},

    # ── Flexibles ──────────────────────────────────────────────────────────
    {"isin":"FR0010097683","bid":"MP-802713", "name":"CPR Croissance Réactive (P)","mgr":"CPR AM","cat_id":"flexibles","srri":4},
    {"isin":"LU2147879543","bid":"0P0001L9PD","name":"Tikehau International Cross Assets (R)","mgr":"Tikehau IM","cat_id":"flexibles","srri":4},
    {"isin":"FR0011175652","bid":"0P00015XU2","name":"Conservateur Reverso (C)","mgr":"Conservateur Gestion Valor","cat_id":"flexibles","srri":4},
    {"isin":"FR0010286013","bid":"MP-805700", "name":"Sextant Grand Large (A)","mgr":"Amiral Gestion","cat_id":"flexibles","srri":4},
    {"isin":"FR0011253624","bid":"0P00017T6E","name":"R-co Valor (C)","mgr":"Rothschild et Cie Gestion","cat_id":"flexibles","srri":5},
]

# Index rapide par ISIN
FUNDS_BY_ISIN: dict = {f["isin"]: f for f in FUNDS}

# Labels catégorie par id
CAT_LABELS: dict = {c["id"]: c["label"] for c in CATEGORIES}

def get_fund(isin: str) -> dict | None:
    return FUNDS_BY_ISIN.get(isin)

def get_cat_label(cat_id: str) -> str:
    return CAT_LABELS.get(cat_id, cat_id)
