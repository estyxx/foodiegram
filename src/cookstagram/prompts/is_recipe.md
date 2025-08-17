Analyze this Instagram caption and determine if it contains a recipe or cooking instructions.

Caption: "{caption}"

Respond with JSON in this exact format:
{{
    "is_recipe": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}

Consider it a recipe if it has:
- Ingredient lists (even informal ones)
- Cooking steps/instructions/method descriptions
- Food preparation techniques
- Recipe-related action words (cook, bake, mix, sauté, etc.)
- Measurements or quantities
- Cooking times or temperatures
- Even basic assembly instructions

Don't require perfect formatting - Instagram posts are often casual.
