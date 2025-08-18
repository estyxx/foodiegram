# Foodiegram - Instagram Recipe Extractor



A clean, pythonic tool to extract and analyze recipes from your saved Instagram posts using AI.

## 🍳 What it does

Foodiegram extracts your saved Instagram posts from specific collections and uses OpenAI's GPT to analyze the captions, identifying recipes and extracting structured information like:

- **Ingredients** and **cooking steps**
- **Dish type** (pasta, soup, salad, etc.)
- **Meal type** (breakfast, lunch, dinner)
- **Main protein** and **cuisine type**
- **Difficulty level** and **cooking time**
- **Dietary tags** (vegetarian, vegan, gluten-free, etc.)

## 🚀 Quick Start

### 1. Installation

```bash
# Clone or create the project
git clone <your-repo> foodiegram
cd foodiegram

# Install dependencies
uv sync --all-extras --dev

# Start a local server
python -m http.server 8000

# Open in browser
open http://localhost:8000/ui
```

### 2. Environment Setup

Create a `.env` file in the project root:

```bash
# .env
INSTAGRAM_USERNAME=your_instagram_username
INSTAGRAM_PASSWORD=your_instagram_password
OPENAI_API_KEY=your_openai_api_key
```

### 3. Find Your Collection ID

To extract from a specific saved collection, you need the collection ID:

1. Open Instagram in your browser
2. Go to your saved posts
3. Click on a collection (e.g., "Recipes")
4. Look at the URL: `instagram.com/username/saved/collection/17854976980356429/`
5. The number at the end is your collection ID

### 4. Extract Recipes

```python
from recipe_analyzer import analyze_collection_recipes

# Extract and analyze 20 posts from your collection
recipes = analyze_collection_recipes(
    collection_id=12345678910111213,  # Your collection ID
    limit=20
)
```

Or run directly:

```python
# main.py
from recipe_analyzer import analyze_collection_recipes

if __name__ == "__main__":
    recipes = analyze_collection_recipes(
        collection_id=12345678910111213,
        limit=50  # Adjust as needed
    )
```

