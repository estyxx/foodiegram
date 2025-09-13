from foodiegram import env
from foodiegram.cache_manager import CacheManager
from foodiegram.instageram_extractor import load_or_fetch_collection
from foodiegram.recipe_extractor import RecipeExtractor

environment = env.Env.get_env()

cache = CacheManager()
collection = load_or_fetch_collection(
    environment,
    collection_id=environment.INSTAGRAM_COLLECTION_ID,
    limit=4,
)
posts = [cache.get_post(post_id) for post_id in collection.post_pks[:4]]

extractor = RecipeExtractor(api_key=environment.OPENAI_API_KEY, model="gpt-4.1")
recipes = extractor.parse_results(posts)
extractor.save_analysis(recipes)
batch_id = "batch_68ab3084fd8c8190a8d2c03b8f5f0a60"
