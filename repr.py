from foodiegram.cache_manager import CacheManager
from foodiegram.instageram_extractor import load_or_fetch_collection
from foodiegram.recipe_extractor import RecipeExtractor
from foodiegram.settings import Settings

environment = Settings()

cache = CacheManager()
collection = load_or_fetch_collection(
    environment,
    collection_id=environment.instagram_collection_id,
    limit=4,
)
posts = [cache.get_post(post_id) for post_id in collection.post_pks[:4]]

batch_id = "batch_68ab3084fd8c8190a8d2c03b8f5f0a60"
extractor = RecipeExtractor(api_key=environment.openai_api_key, model="gpt-4.1")
recipes = extractor.parse_results(posts, batch_id)
extractor.save_analysis(recipes)
