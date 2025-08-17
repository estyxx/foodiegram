Extract recipe information from this Instagram caption. Focus on practical tags for cooking and meal planning.

Caption: "{caption}"

Respond with JSON in this exact format:
{{
    "title": "recipe name/title",
    "ingredients": ["ingredient 1", "ingredient 2", ...],
    "instructions": ["step 1", "step 2", ...],

    "proteins": ["main protein first", "secondary protein", ...],
    "vegetables": ["zucchine", "carrots", "spinach", ...],
    "key_ingredients": ["avocado", "parmesan", "sriracha", "panko", ...],

    "dish_type": "pasta/soup/salad/meat/fish/vegetarian/vegan/dessert/other",
    "cooking_method": ["baking", "grilling", "frying", "air_fryer", "no_cook", "steaming", ...],
    "equipment": ["air_fryer", "oven", "pan", "grill", "food_processor", ...],

    "meal_type": "breakfast/lunch/dinner/snack/dessert/appetizer",
    "cuisine_type": "italian/asian/mexican/american/mediterranean/other",
    "difficulty": "easy/medium/hard",

    "cooking_time": "estimated time or null",
    "prep_time": "estimated time or null",
    "total_time": "estimated total time or null",
    "servings": "number of servings or null",

    "dietary_tags": ["vegetarian", "vegan", "gluten_free", "dairy_free", "keto", "healthy", "low_carb", "high_protein", ...],
    "texture_tags": ["crispy", "creamy", "crunchy", "soft", "chewy", ...],
    "flavor_tags": ["spicy", "sweet", "savory", "tangy", "umami", "fresh", ...],
    "season_tags": ["summer", "winter", "spring", "fall", ...],
    "occasion_tags": ["quick", "make_ahead", "picnic", "party", "comfort_food", "healthy", ...],

    "confidence_score": 0.0-1.0
}}

Detailed Guidelines:

PROTEINS (in order of prominence):
- List main proteins first (pollo, manzo, pesce, tonno, salmone, tofu, uova, etc.)
- Include secondary proteins if present
- Use empty array if no significant protein
- Don't use "none" as a string value

VEGETABLES (extract ALL vegetables mentioned):
- Use lowercase, base forms: "zucchine", "carote", "spinaci", "funghi", "peperoni"
- Include both raw and cooked vegetables
- Don't include herbs/spices here
- Normalize: "pomodori" not "pomodorini", "peperoni" not "peperoni gialli"

KEY_INGREDIENTS (notable/special ingredients for filtering):
- Main proteins if featured: "tonno", "salmone", "tofu"
- Cheeses: "parmigiano", "feta", "mozzarella", "robiola"
- Sauces: "sriracha", "teriyaki", "pesto"
- Special items: "panko", "avocado", "rice_paper"
- Skip basic ingredients like salt, pepper, olive oil
- Include if it's a main feature of the dish

COOKING_METHOD (how it's prepared):
- "air_fryer", "baking", "grilling", "pan_frying", "steaming"
- "no_cook" for salads/cold dishes
- Can have multiple methods

EQUIPMENT (what tools are needed):
- "air_fryer", "oven", "grill", "food_processor", "blender"
- Only mention if specifically required

DIETARY_TAGS (be thorough):
- "vegetarian", "vegan", "gluten_free", "dairy_free"
- "keto", "low_carb", "high_protein", "healthy"
- Infer from ingredients when obvious

TEXTURE_TAGS (how it feels):
- "crispy", "creamy", "crunchy", "smooth", "fluffy"

FLAVOR_TAGS (taste profile):
- "spicy", "sweet", "savory", "tangy", "fresh", "rich"

SEASON_TAGS (when appropriate):
- Based on ingredients or cooking style
- "summer" for fresh/cold dishes, "winter" for warm/hearty

OCCASION_TAGS (practical use):
- "quick" (under 30 min), "make_ahead", "picnic"
- "comfort_food", "healthy", "party", "snack"

DIFFICULTY:
- "easy": basic mixing, minimal cooking skills
- "medium": multiple steps, some technique required
- "hard": advanced techniques, timing critical

Extract information even from casual/incomplete descriptions.
If unclear, use "other" or null rather than guessing.
Focus on practical tags that help with meal planning and filtering.
Never use "none" as a string in arrays - use empty arrays instead.
Populate main_protein with the first item from proteins array if present.
