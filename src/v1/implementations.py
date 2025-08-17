"""Concrete implementations for Instagram recipe extraction"""

import json
import re
import time
from pathlib import Path
from typing import Any

import instaloader
import openai
import requests
from recipe_extractor import (
    ContentParser,
    DataExtractor,
    Difficulty,
    DishType,
    MealType,
    Recipe,
    RecipeClassifier,
)


class InstaloaderExtractor(DataExtractor):
    """Instagram data extraction using instaloader"""

    def __init__(self, username: str, session_file: str | None = None):
        self.username = username
        self.loader = instaloader.Instaloader()

        # Login (you can use session file to avoid repeated logins)
        if session_file and Path(session_file).exists():
            self.loader.load_session_from_file(username, session_file)
        else:
            # You'll need to login interactively first time
            self.loader.login(username, input("Password: "))
            if session_file:
                self.loader.save_session_to_file(session_file)

    def extract_saved_posts(self) -> list[dict[str, Any]]:
        """Extract saved posts using instaloader"""
        profile = instaloader.Profile.from_username(self.loader.context, self.username)

        saved_posts = []
        for post in profile.get_saved_posts():
            post_data = {
                "id": post.mediaid,
                "shortcode": post.shortcode,
                "caption": post.caption or "",
                "owner_username": post.owner_username,
                "url": f"https://instagram.com/p/{post.shortcode}/",
                "image_urls": [post.url]
                if not post.typename == "GraphSidecar"
                else [node.display_url for node in post.get_sidecar_nodes()],
                "likes": post.likes,
                "date": post.date_utc.isoformat(),
                "location": post.location.name if post.location else None,
                "hashtags": list(post.caption_hashtags) if post.caption_hashtags else [],
                "raw_post": post,  # Keep reference for additional data if needed
            }
            saved_posts.append(post_data)

            # Rate limiting
            time.sleep(1)

        return saved_posts

    def download_images(self, post: dict[str, Any], output_dir: Path) -> list[str]:
        """Download images for a post"""
        output_dir.mkdir(exist_ok=True)
        downloaded_files = []

        for i, img_url in enumerate(post["image_urls"]):
            filename = f"{post['shortcode']}_{i}.jpg"
            filepath = output_dir / filename

            try:
                response = requests.get(img_url, stream=True)
                response.raise_for_status()

                with open(filepath, "wb") as f:
                    f.writelines(response.iter_content(chunk_size=8192))

                downloaded_files.append(str(filepath))
            except Exception as e:
                print(f"Failed to download {img_url}: {e}")

        return downloaded_files


class LLMContentParser(ContentParser):
    """Parse recipe content using regex and basic NLP"""

    def parse_recipe(self, post_data: dict[str, Any]) -> Recipe:
        """Parse Instagram post into Recipe object"""
        caption = post_data.get("caption", "")

        return Recipe(
            id=post_data["shortcode"],
            title=self._extract_title(caption),
            caption=caption,
            image_urls=post_data["image_urls"],
            source_url=post_data["url"],
            username=post_data["owner_username"],
            ingredients=self.extract_ingredients(caption),
            steps=self.extract_steps(caption),
            tags=post_data.get("hashtags", []),
            raw_data=post_data,
        )

    def _extract_title(self, caption: str) -> str:
        """Extract title from caption (first line or sentence)"""
        lines = caption.split("\n")
        if lines:
            first_line = lines[0].strip()
            # Remove hashtags and mentions from title
            title = re.sub(r"[#@]\w+", "", first_line).strip()
            return title[:100] if title else "Untitled Recipe"
        return "Untitled Recipe"

    def extract_ingredients(self, text: str) -> list[str]:
        """Extract ingredients using regex patterns"""
        ingredients = []

        # Common ingredient patterns
        patterns = [
            r"(?:^|\n)[-•*]\s*([^\n]+(?:cup|tbsp|tsp|oz|lb|kg|g|ml|l|clove|bunch)\b[^\n]*)",
            r"(?:^|\n)(\d+[^\n]*(?:cup|tbsp|tsp|oz|lb|kg|g|ml|l|clove|bunch)\b[^\n]*)",
            r"(?:ingredients?:?\s*\n)((?:[-•*\d][^\n]+\n?)*)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match[0] else match[1] if len(match) > 1 else ""

                # Split multi-line ingredient lists
                if "\n" in match:
                    ingredients.extend(
                        [ing.strip("•*- ") for ing in match.split("\n") if ing.strip()]
                    )
                else:
                    ingredients.append(match.strip("•*- "))

        # Clean and deduplicate
        ingredients = [
            ing.strip() for ing in ingredients if ing.strip() and len(ing) > 3
        ]
        return list(
            dict.fromkeys(ingredients)
        )  # Remove duplicates while preserving order

    def extract_steps(self, text: str) -> list[str]:
        """Extract cooking steps using regex patterns"""
        steps = []

        # Step patterns
        patterns = [
            r"(?:^|\n)(\d+\.\s*[^\n]+)",  # Numbered steps
            r"(?:instructions?:?\s*\n)((?:\d+\.?[^\n]+\n?)*)",  # Instruction block
            r"(?:^|\n)[-•*]\s*([A-Z][^\n]+[.!])",  # Bullet points that look like instructions
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match[0] else match[1] if len(match) > 1 else ""

                if "\n" in match:
                    steps.extend(
                        [
                            step.strip("•*- 0123456789.")
                            for step in match.split("\n")
                            if step.strip()
                        ]
                    )
                else:
                    steps.append(match.strip("•*- 0123456789."))

        # Clean and filter
        steps = [step.strip() for step in steps if step.strip() and len(step) > 10]
        return list(dict.fromkeys(steps))


class OpenAIClassifier(RecipeClassifier):
    """Classify recipes using OpenAI API"""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

    def classify_recipe(self, recipe: Recipe) -> Recipe:
        """Classify recipe using GPT"""
        prompt = self._build_classification_prompt(recipe)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a expert chef and recipe analyzer. Analyze recipes and provide structured classifications.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )

            result = response.choices[0].message.content
            return self._parse_classification_result(recipe, result)

        except Exception as e:
            print(f"Classification failed for {recipe.id}: {e}")
            return recipe

    def _build_classification_prompt(self, recipe: Recipe) -> str:
        """Build prompt for recipe classification"""
        return f"""
Analyze this recipe and provide a JSON response with the following classifications:

RECIPE DATA:
Title: {recipe.title}
Ingredients: {", ".join(recipe.ingredients[:10])}  # First 10 ingredients
Steps: {". ".join(recipe.steps[:3])}  # First 3 steps
Caption: {recipe.caption[:500]}...  # Truncated

Please respond with JSON in this exact format:
{{
    "main_protein": "chicken|beef|pork|fish|seafood|eggs|tofu|beans|nuts|none",
    "dish_type": "pasta|risotto|soup|salad|bread|meat|fish|vegetarian|dessert|snack|other",
    "meal_type": "breakfast|lunch|dinner|snack|dessert",
    "difficulty": "easy|medium|hard",
    "cooking_time": "estimated time like '30 minutes' or 'unknown'",
    "cuisine_type": "italian|asian|mexican|indian|american|mediterranean|other",
    "dietary_tags": ["vegetarian", "vegan", "gluten-free", "dairy-free", "keto", "low-carb", "healthy"],
    "confidence": 0.9
}}

Base your analysis on the ingredients and cooking methods described.
"""

    def _parse_classification_result(self, recipe: Recipe, result: str) -> Recipe:
        """Parse GPT response and update recipe"""
        try:
            # Extract JSON from response
            json_match = re.search(r"\{.*\}", result, re.DOTALL)
            if not json_match:
                return recipe

            classification = json.loads(json_match.group())

            # Map string values to enums
            if classification.get("dish_type"):
                try:
                    recipe.dish_type = DishType(classification["dish_type"])
                except ValueError:
                    pass

            if classification.get("meal_type"):
                try:
                    recipe.meal_type = MealType(classification["meal_type"])
                except ValueError:
                    pass

            if classification.get("difficulty"):
                try:
                    recipe.difficulty = Difficulty(classification["difficulty"])
                except ValueError:
                    pass

            # Direct assignments
            recipe.main_protein = classification.get("main_protein")
            recipe.cooking_time = classification.get("cooking_time")

            # Add dietary tags to existing tags
            dietary_tags = classification.get("dietary_tags", [])
            recipe.tags.extend(dietary_tags)

            return recipe

        except Exception as e:
            print(f"Failed to parse classification for {recipe.id}: {e}")
            return recipe


# Alternative classifier using local models
class LocalLLMClassifier(RecipeClassifier):
    """Classify recipes using local LLM (e.g., Ollama)"""

    def __init__(
        self, model_name: str = "llama3.1:8b", base_url: str = "http://localhost:11434"
    ):
        self.model_name = model_name
        self.base_url = base_url

    def classify_recipe(self, recipe: Recipe) -> Recipe:
        """Classify using local Ollama instance"""
        # Implementation would call Ollama API
        # Similar to OpenAI but using local endpoint


# Factory function for easy setup
def create_extractor(
    username: str,
    openai_api_key: str,
    use_local_llm: bool = False,
    session_file: str = None,
) -> "RecipeExtractor":
    """Factory function to create configured extractor"""
    extractor = InstaloaderExtractor(username, session_file)
    parser = LLMContentParser()

    if use_local_llm:
        classifier = LocalLLMClassifier()
    else:
        classifier = OpenAIClassifier(openai_api_key)

    from recipe_extractor import RecipeExtractor

    return RecipeExtractor(extractor, parser, classifier)
