from dispensa.domain.synonyms import canonical_term

# A starter aisle map keyed by readable ingredient words (any synonym member or
# language). It is normalised through canonical_term() at module load, so the
# keys line up with the canonical names the shopping list produces. Aisle names
# are Italian, to match the "altro" fallback and the Italian ingredient lines.
# The owner refines it from the real library (an optional data/aisles.json is
# overlaid on top); this only needs to cut "altro" down, not be exhaustive.
_ORTOFRUTTA = "ortofrutta"
_LATTICINI = "latticini"
_CARNE = "carne"
_SALUMI = "salumi"
_PESCE = "pescheria"
_DISPENSA = "dispensa"
_SPEZIE = "spezie"
_PANETTERIA = "panetteria"

_RAW_AISLES: dict[str, str] = {
    # ── Ortofrutta (produce) ──
    "pomodoro": _ORTOFRUTTA,
    "cipolla": _ORTOFRUTTA,
    "aglio": _ORTOFRUTTA,
    "basilico": _ORTOFRUTTA,
    "prezzemolo": _ORTOFRUTTA,
    "rucola": _ORTOFRUTTA,
    "zucchine": _ORTOFRUTTA,
    "melanzane": _ORTOFRUTTA,
    "peperone": _ORTOFRUTTA,
    "zucca": _ORTOFRUTTA,
    "funghi": _ORTOFRUTTA,
    "patate": _ORTOFRUTTA,
    "carote": _ORTOFRUTTA,
    "sedano": _ORTOFRUTTA,
    "limone": _ORTOFRUTTA,
    "spinaci": _ORTOFRUTTA,
    "insalata": _ORTOFRUTTA,
    "rosmarino": _ORTOFRUTTA,
    "scallion": _ORTOFRUTTA,
    "peperoncino": _ORTOFRUTTA,
    "finocchio": _ORTOFRUTTA,
    "broccoli": _ORTOFRUTTA,
    "cavolfiore": _ORTOFRUTTA,
    "cavolo": _ORTOFRUTTA,
    "mais": _ORTOFRUTTA,
    "avocado": _ORTOFRUTTA,
    "cilantro": _ORTOFRUTTA,
    # ── Latticini (dairy & eggs) ──
    "parmigiano": _LATTICINI,
    "mozzarella": _LATTICINI,
    "ricotta": _LATTICINI,
    "burrata": _LATTICINI,
    "latte": _LATTICINI,
    "panna": _LATTICINI,
    "burro": _LATTICINI,
    "yogurt": _LATTICINI,
    "mascarpone": _LATTICINI,
    "gorgonzola": _LATTICINI,
    "pecorino": _LATTICINI,
    "uova": _LATTICINI,
    # ── Carne / Salumi ──
    "pollo": _CARNE,
    "manzo": _CARNE,
    "maiale": _CARNE,
    "salsiccia": _CARNE,
    "tacchino": _CARNE,
    "agnello": _CARNE,
    "vitello": _CARNE,
    "guanciale": _SALUMI,
    "pancetta": _SALUMI,
    "prosciutto": _SALUMI,
    "speck": _SALUMI,
    "salame": _SALUMI,
    "mortadella": _SALUMI,
    "bresaola": _SALUMI,
    # ── Pescheria ──
    "salmone": _PESCE,
    "tonno": _PESCE,
    "acciughe": _PESCE,
    "gamberi": _PESCE,
    "vongole": _PESCE,
    "calamari": _PESCE,
    "merluzzo": _PESCE,
    "branzino": _PESCE,
    "sgombro": _PESCE,
    "sarde": _PESCE,
    # ── Dispensa (dry goods, tins, oils) ──
    "pasta": _DISPENSA,
    "riso": _DISPENSA,
    "farina": _DISPENSA,
    "zucchero": _DISPENSA,
    "sale": _DISPENSA,
    "olio d'oliva": _DISPENSA,
    "lenticchie": _DISPENSA,
    "ceci": _DISPENSA,
    "fagioli": _DISPENSA,
    "piselli": _DISPENSA,
    "aceto": _DISPENSA,
    "miele": _DISPENSA,
    "noci": _DISPENSA,
    "mandorle": _DISPENSA,
    "pinoli": _DISPENSA,
    "capperi": _DISPENSA,
    "olive": _DISPENSA,
    "lievito": _DISPENSA,
    "brodo": _DISPENSA,
    "passata": _DISPENSA,
    "pelati": _DISPENSA,
    "vino": _DISPENSA,
    "polenta": _DISPENSA,
    "couscous": _DISPENSA,
    # ── Spezie (spices & herbs on the shelf) ──
    "black pepper": _SPEZIE,
    "origano": _SPEZIE,
    "cannella": _SPEZIE,
    "noce moscata": _SPEZIE,
    "curcuma": _SPEZIE,
    "zafferano": _SPEZIE,
    "cumino": _SPEZIE,
    "paprika": _SPEZIE,
    "alloro": _SPEZIE,
    "timo": _SPEZIE,
    "salvia": _SPEZIE,
    # ── Panetteria ──
    "pane": _PANETTERIA,
    "pangrattato": _PANETTERIA,
}

# Normalise keys to the canonical names the shopping list produces.
DEFAULT_AISLES: dict[str, str] = {
    canonical_term(name): aisle for name, aisle in _RAW_AISLES.items()
}
