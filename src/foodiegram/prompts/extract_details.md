Extract recipe information from this caption.

Caption: "{caption}"

REQUIRED OUTPUT: Provide ALL fields, even if some information is missing or unclear.

For missing information, use these defaults:
- title: "Recipe" if no clear title
- ingredients: [] if no ingredients found
- instructions: [] if no steps found
- cuisine_type: "other" if unclear ("italian", "asian", "mexican", "other")
- difficulty: "medium" if unclear ("easy", "medium", "hard")
- proteins: "none" if unclear ("chicken", "beef", "fish", "cheese", "eggs", "vegetarian", "none")
- cooking_method: "other" if unclear ("baking", "frying", "boiling", "grilling", "other")
- is_recipe: false if this is not actually a recipe
- confidence_score: your confidence from 0.0 to 1.0


Extract clear, practical information suitable for cooking.
