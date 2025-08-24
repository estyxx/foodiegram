import json
import logging
import time
from pathlib import Path

from openai import OpenAI
from openai.types import Batch
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from foodiegram.types import Media, Recipe

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RecipeExtractor:
    """Class for extracting recipes from posts using Responses API."""

    model_name: str = "gpt-4o-mini"

    def __init__(self, api_key: str) -> None:
        """Initialize the extractor with OpenAI API key."""
        self._openai_client = OpenAI(api_key=api_key)
        provider = OpenAIProvider(api_key=api_key)
        self.model = OpenAIResponsesModel(self.model_name, provider=provider)
        self._client = OpenAI(api_key=api_key)

    @property
    def tasks_path(self) -> Path:
        """Path to the tasks JSONL file."""
        return Path("data/tasks.jsonl")

    def build_tasks_jsonl(self, posts: list[Media]) -> None:
        """Build tasks JSONL from media posts."""
        out_path = self.tasks_path
        instruction = Path("src/foodiegram/prompts/extract_details.md").read_text()

        # Generate schema with strict mode compatibility
        schema = Recipe.model_json_schema_strict()

        with out_path.open("w", encoding="utf-8") as f:
            for post in posts:
                if not post.caption_text:
                    continue

                body = {
                    "model": self.model_name,
                    "input": instruction.format(caption=post.caption_text),
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": "RecipeExtraction",
                            "schema": schema,
                            "strict": True,
                        },
                    },
                }

                line = {
                    "custom_id": f"recipe-{post.id}",
                    "method": "POST",
                    "url": "/v1/responses",
                    "body": body,
                }
                f.write(json.dumps(line, ensure_ascii=False) + "\n")

    def create_batch(self, posts: list[Media]) -> str:
        """Create a batch for /v1/responses using Media posts."""
        self.build_tasks_jsonl(posts)

        with self.tasks_path.open("rb") as f:
            upload = self._client.files.create(file=f, purpose="batch")

        batch = self._client.batches.create(
            input_file_id=upload.id,
            endpoint="/v1/responses",
            completion_window="24h",
        )
        return batch.id

    def wait_for_batch(self, batch_id: str) -> Batch:
        """Poll the batch status until completion."""
        start_time = time.time()
        while True:
            batch = self._client.batches.retrieve(batch_id)
            if batch.status in {"completed", "failed", "cancelled", "expired"}:
                elapsed = time.time() - start_time
                print(f"Batch {batch_id} {batch.status} in {elapsed:.1f}s")
                return batch
            time.sleep(8)

    def download_results(self, batch: Batch) -> None:
        """Download batch results to local files."""
        if batch.error_file_id:
            content = self._client.files.content(batch.error_file_id).text
            Path("data/errors_recipes.jsonl").write_text(content, encoding="utf-8")

        if batch.output_file_id:
            content = self._client.files.content(batch.output_file_id).text
            Path("data/extracted_recipes.jsonl").write_text(content, encoding="utf-8")

    def parse_results(self, posts: list[Media]) -> list[Recipe]:
        """Parse results into Recipe objects."""
        results_path = Path("data/extracted_recipes.jsonl")
        if not results_path.exists():
            return []

        # Create post lookup
        post_lookup = {f"recipe-{post.id}": post for post in posts}
        recipes = []

        for line in results_path.read_text().splitlines():
            if not line:
                continue

            result = json.loads(line)
            custom_id = result["custom_id"]

            if custom_id not in post_lookup:
                continue

            post = post_lookup[custom_id]

            try:
                # Extract the recipe data from response
                output_data = result["response"]["body"]["output"][0]["content"][0][
                    "text"
                ]

                recipe_data = json.loads(output_data)

                # Create Recipe object
                recipe = Recipe(**recipe_data)
                recipes.append(recipe)

            except Exception as e:
                print(f"Error parsing {custom_id}: {e}")

        return recipes
