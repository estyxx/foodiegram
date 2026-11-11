SYNONYM_GROUPS: list[frozenset[str]] = [
    frozenset({"zucchini", "courgette", "zucchine", "zucchina"}),
    # NOTE: "zucca" (winter squash/pumpkin) is a different vegetable from
    # "zucchine" above, despite the shared root. Keep the two groups apart.
    frozenset({"zucca", "pumpkin", "squash", "butternut"}),
    frozenset({"eggplant", "aubergine", "melanzana", "melanzane"}),
    # NOTE: "peperoni" (Italian, bell peppers) is a false friend with English
    # "pepperoni" (cured meat sausage). Do NOT merge these into one group —
    # they're unrelated foods that happen to look similar.
    frozenset({"bell pepper", "bell peppers", "capsicum", "peperone", "peperoni"}),
    frozenset({"chili pepper", "peperoncino"}),
    frozenset({"shrimp", "shrimps", "prawn", "prawns", "gamberi", "gamberetti"}),
    frozenset({"cilantro", "coriander", "coriandolo"}),
    frozenset({"arugula", "rocket", "rucola"}),
    frozenset(
        {
            "scallion",
            "scallions",
            "spring onion",
            "spring onions",
            "cipollotto",
            "cipollotti",
        },
    ),
    frozenset({"chickpea", "chickpeas", "garbanzo", "garbanzos", "ceci"}),
    frozenset({"garlic", "aglio"}),
    frozenset({"onion", "cipolla"}),
    frozenset({"basil", "basilico"}),
    frozenset({"parmesan", "parmigiano"}),
    frozenset({"olive oil", "olio d'oliva", "olio di oliva"}),
    frozenset({"parsley", "prezzemolo"}),
    frozenset({"rosemary", "rosmarino"}),
    frozenset({"mushroom", "mushrooms", "funghi", "fungo"}),
    frozenset({"tomato", "tomatoes", "pomodoro", "pomodori"}),
    # Common cross-language pantry/ingredient pairs (15.5). Kept word-boundary
    # safe: no member is a substring trap (e.g. "noce" is omitted — it also means
    # a knob of butter and starts "noce moscata"/nutmeg; only "noci" is grouped).
    frozenset({"egg", "eggs", "uovo", "uova"}),
    frozenset({"flour", "farina"}),
    frozenset({"sugar", "zucchero"}),
    frozenset({"salt", "sale"}),
    frozenset({"black pepper", "pepe nero", "pepe"}),
    frozenset({"butter", "burro"}),
    frozenset({"milk", "latte"}),
    frozenset({"cream", "panna"}),
    frozenset({"water", "acqua"}),
    frozenset({"bread", "pane"}),
    frozenset({"rice", "riso"}),
    frozenset({"potato", "potatoes", "patata", "patate"}),
    frozenset({"carrot", "carrots", "carota", "carote"}),
    frozenset({"celery", "sedano"}),
    frozenset({"lemon", "lemons", "limone", "limoni"}),
    frozenset({"spinach", "spinaci"}),
    frozenset({"pea", "peas", "pisello", "piselli"}),
    frozenset({"bean", "beans", "fagiolo", "fagioli"}),
    frozenset({"lentil", "lentils", "lenticchia", "lenticchie"}),
    frozenset({"tuna", "tonno"}),
    frozenset({"salmon", "salmone"}),
    frozenset({"anchovy", "anchovies", "acciuga", "acciughe", "alici"}),
    frozenset({"chicken", "pollo"}),
    frozenset({"beef", "manzo"}),
    frozenset({"pork", "maiale"}),
    frozenset({"sausage", "salsiccia", "salsicce"}),
    frozenset({"honey", "miele"}),
    frozenset({"vinegar", "aceto"}),
    frozenset({"wine", "vino"}),
    frozenset({"walnut", "walnuts", "noci"}),
    frozenset({"almond", "almonds", "mandorla", "mandorle"}),
]

# Case-insensitive lookup: normalised term -> its full synonym group (including itself).
_LOOKUP: dict[str, frozenset[str]] = {
    term.lower(): group for group in SYNONYM_GROUPS for term in group
}

# Case-insensitive lookup: normalised term -> a stable canonical representative
# (the alphabetically-first member of its group) so synonyms dedupe to one key.
_CANONICAL: dict[str, str] = {
    term.lower(): min(group) for group in SYNONYM_GROUPS for term in group
}


def expand_term(term: str) -> set[str]:
    """Return term plus all known synonyms, case-insensitive."""
    return set(_LOOKUP.get(term.lower(), frozenset({term})))


def canonical_term(term: str) -> str:
    """Return a stable canonical name for term's synonym group, else term itself."""
    return _CANONICAL.get(term.lower(), term.lower())
