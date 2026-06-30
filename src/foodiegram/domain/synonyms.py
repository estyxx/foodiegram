SYNONYM_GROUPS: list[frozenset[str]] = [
    frozenset({"zucchini", "courgette", "zucchine", "zucchina"}),
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
]

# Case-insensitive lookup: normalised term -> its full synonym group (including itself).
_LOOKUP: dict[str, frozenset[str]] = {
    term.lower(): group for group in SYNONYM_GROUPS for term in group
}


def expand_term(term: str) -> set[str]:
    """Return term plus all known synonyms, case-insensitive."""
    return set(_LOOKUP.get(term.lower(), frozenset({term})))
