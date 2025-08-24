You are an expert culinary analyst. Extract comprehensive recipe information from this Instagram caption. Convert ALL Italian terms to English for consistency.

Caption: "{caption}"

## TRANSLATION RULES (Italian → English):
- pomodoro/pomodori → tomato/tomatoes
- zucchine → zucchini
- aglio → garlic
- cipolla → onion
- basilico → basil
- parmigiano → parmesan
- olio d'oliva → olive oil
- sale → salt
- pepe → pepper
- prezzemolo → parsley
- rosmarino → rosemary
- peperoncino → chili pepper
- funghi → mushrooms
- melanzane → eggplant
- peperoni → bell peppers

## EXTRACTION GUIDELINES:

### Core Recipe Data:
- **title**: Clear, descriptive recipe name
- **ingredients**: All ingredients mentioned (in English)
- **instructions**: Step-by-step cooking process (if available)

### Classifications:
- **cuisine_type**: "italian", "asian", "mexican", "mediterranean", "american", "french", "fusion", "other"
- **difficulty**: "easy" (simple prep), "medium" (moderate skill), "hard" (complex techniques)
- **meal_type**: "breakfast", "lunch", "dinner", "snack", "dessert", "appetizer"

### Ingredient Breakdown (English only):
- **proteins**: ["chicken", "beef", "pork", "fish", "seafood", "tofu", "eggs", "cheese", "beans", "nuts"]
- **vegetables**: ["tomato", "onion", "garlic", "zucchini", "spinach", "broccoli", "carrot", "bell_pepper"]
- **grains_starches**: ["pasta", "rice", "bread", "potato", "quinoa", "couscous", "noodles"]
- **herbs_spices**: ["basil", "oregano", "thyme", "paprika", "cumin", "black_pepper", "red_pepper"]

### Cooking Details:
- **cooking_methods**: ["baking", "frying", "grilling", "boiling", "sautéing", "roasting", "steaming", "braising"]
- **equipment**: ["oven", "stovetop", "pan", "pot", "grill", "blender", "processor", "air_fryer", "slow_cooker"]

### Time and Serving:
- **prep_time**: "10 minutes", "30 minutes", "1 hour", "unknown"
- **cook_time**: "15 minutes", "45 minutes", "2 hours", "unknown"
- **total_time**: "25 minutes", "1.5 hours", "unknown"
- **servings**: "1-2", "3-4", "6-8", "unknown"

### Experience Tags:
- **temperature**: "hot", "cold", "room_temperature", "both"
- **texture**: ["crispy", "creamy", "crunchy", "smooth", "chewy", "tender", "flaky", "juicy"]
- **flavor_profile**: ["savory", "sweet", "spicy", "tangy", "umami", "bitter", "mild", "rich"]

### Dietary & Health:
- **dietary_tags**: ["vegetarian", "vegan", "gluten_free", "dairy_free", "keto", "paleo", "low_carb", "pescatarian"]
- **health_tags**: ["low_calorie", "high_protein", "low_sodium", "heart_healthy", "diabetic_friendly", "anti_inflammatory"]

### Context & Occasion:
- **season**: ["spring", "summer", "fall", "winter", "year_round"]
- **occasion**: ["weeknight", "weekend", "party", "holiday", "date_night", "meal_prep", "picnic", "brunch"]
- **skill_level**: "beginner", "intermediate", "advanced"

### Style & Prep:
- **style_tags**: ["comfort_food", "gourmet", "rustic", "modern", "traditional", "fusion", "street_food", "home_cooking"]
- **prep_style**: ["make_ahead", "quick", "one_pot", "no_cook", "batch_cook", "freezer_friendly", "leftover_friendly"]

## DEFAULTS for missing information:
- If unclear: use "unknown" for single values, empty lists [] for arrays
- If no clear cuisine: "other"
- If no clear difficulty: "medium"
- If ingredients unclear: infer from image context or cooking method
- Use "year_round" for season if not seasonal-specific
- Use "home_cooking" for style if unclear

Extract practical, searchable information that helps users find and filter recipes effectively.
