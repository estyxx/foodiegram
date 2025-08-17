"""Complete usage example for Instagram recipe extraction"""

import os
from pathlib import Path

import pandas as pd
from implementations import create_extractor


def main():
    # Configuration
    INSTAGRAM_USERNAME = "your_username"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Set this in your environment
    SESSION_FILE = "instagram_session"
    OUTPUT_DIR = Path("./extracted_recipes")

    # Create the extractor
    recipe_extractor = create_extractor(
        username=INSTAGRAM_USERNAME,
        openai_api_key=OPENAI_API_KEY,
        use_local_llm=False,  # Set to True for Ollama
        session_file=SESSION_FILE,
    )

    # Extract all recipes
    print("Starting recipe extraction...")
    recipes = recipe_extractor.extract_all_recipes()

    # Analysis examples
    analyze_recipes(recipes)


def analyze_recipes(recipes):
    """Example analysis of extracted recipes"""
    # Convert to DataFrame for analysis
    df_data = []
    for recipe in recipes:
        df_data.append(
            {
                "title": recipe.title,
                "username": recipe.username,
                "main_protein": recipe.main_protein,
                "dish_type": recipe.dish_type.value if recipe.dish_type else None,
                "meal_type": recipe.meal_type.value if recipe.meal_type else None,
                "difficulty": recipe.difficulty.value if recipe.difficulty else None,
                "cooking_time": recipe.cooking_time,
                "ingredient_count": len(recipe.ingredients),
                "step_count": len(recipe.steps),
                "hashtag_count": len(recipe.tags),
            }
        )

    df = pd.DataFrame(df_data)

    print(f"\n📊 RECIPE ANALYSIS ({len(recipes)} recipes)")
    print("=" * 50)

    # Protein distribution
    print("\n🥩 Main Protein Distribution:")
    protein_counts = df["main_protein"].value_counts()
    for protein, count in protein_counts.head(10).items():
        print(f"  {protein}: {count}")

    # Dish type distribution
    print("\n🍝 Dish Type Distribution:")
    dish_counts = df["dish_type"].value_counts()
    for dish, count in dish_counts.head(10).items():
        print(f"  {dish}: {count}")

    # Meal type distribution
    print("\n🕐 Meal Type Distribution:")
    meal_counts = df["meal_type"].value_counts()
    for meal, count in meal_counts.items():
        print(f"  {meal}: {count}")

    # Difficulty distribution
    print("\n⭐ Difficulty Distribution:")
    diff_counts = df["difficulty"].value_counts()
    for diff, count in diff_counts.items():
        print(f"  {diff}: {count}")

    # Top recipe sources
    print("\n👨‍🍳 Top Recipe Sources:")
    source_counts = df["username"].value_counts()
    for source, count in source_counts.head(10).items():
        print(f"  @{source}: {count}")

    # Quick recipes (easy + short time)
    easy_recipes = df[
        (df["difficulty"] == "easy")
        & (df["cooking_time"].str.contains("15|20|30", na=False))
    ]
    print(f"\n⚡ Quick & Easy Recipes: {len(easy_recipes)}")
    if len(easy_recipes) > 0:
        for _, recipe in easy_recipes.head(5).iterrows():
            print(f"  - {recipe['title']} ({recipe['cooking_time']})")


# Advanced analysis functions
def find_recipes_by_criteria(recipes, **criteria):
    """Find recipes matching specific criteria"""
    matching = []

    for recipe in recipes:
        matches = True

        if "protein" in criteria:
            if recipe.main_protein != criteria["protein"]:
                matches = False

        if "dish_type" in criteria:
            if recipe.dish_type != criteria["dish_type"]:
                matches = False

        if "difficulty" in criteria:
            if recipe.difficulty != criteria["difficulty"]:
                matches = False

        if "max_ingredients" in criteria:
            if len(recipe.ingredients) > criteria["max_ingredients"]:
                matches = False

        if matches:
            matching.append(recipe)

    return matching


def export_meal_plan(recipes, output_file="meal_plan.json"):
    """Export a weekly meal plan based on recipes"""
    import json
    import random
    from collections import defaultdict

    # Group by meal type
    by_meal = defaultdict(list)
    for recipe in recipes:
        if recipe.meal_type:
            by_meal[recipe.meal_type.value].append(recipe)

    # Create 7-day meal plan
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    meal_plan = {}

    for day in days:
        day_meals = {}

        # Breakfast
        if by_meal["breakfast"]:
            breakfast = random.choice(by_meal["breakfast"])
            day_meals["breakfast"] = {
                "title": breakfast.title,
                "url": breakfast.source_url,
                "difficulty": breakfast.difficulty.value
                if breakfast.difficulty
                else "unknown",
            }

        # Lunch
        if by_meal["lunch"]:
            lunch = random.choice(by_meal["lunch"])
            day_meals["lunch"] = {
                "title": lunch.title,
                "url": lunch.source_url,
                "difficulty": lunch.difficulty.value if lunch.difficulty else "unknown",
            }

        # Dinner
        if by_meal["dinner"]:
            dinner = random.choice(by_meal["dinner"])
            day_meals["dinner"] = {
                "title": dinner.title,
                "url": dinner.source_url,
                "difficulty": dinner.difficulty.value
                if dinner.difficulty
                else "unknown",
            }

        meal_plan[day] = day_meals

    with open(output_file, "w") as f:
        json.dump(meal_plan, f, indent=2)

    print(f"📅 Meal plan exported to {output_file}")


if __name__ == "__main__":
    main()

    # Example: Find specific recipes
    # pasta_recipes = find_recipes_by_criteria(
    #     recipes,
    #     dish_type=DishType.PASTA,
    #     difficulty=Difficulty.EASY
    # )
    # print(f"Found {len(pasta_recipes)} easy pasta recipes")
