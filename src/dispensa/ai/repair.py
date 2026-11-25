import logging
import re
from pathlib import Path
from typing import Final

from openai import OpenAIError
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

from dispensa.ai.batch import render_prompt
from dispensa.domain.errors import ExtractionError
from dispensa.domain.models import ExtractedCategoryServing, ExtractedRecipe

# Pin the same snapshot the batch path uses so interactive repairs match it.
MODEL = "gpt-5.4-mini-2026-03-17"
REASONING_EFFORT: Final = "low"
PROMPT_PATH = Path(__file__).parent / "prompts" / "extract_recipe_details.txt"
_CATEGORY_HEADING = "### Mediterranean categories (English values only):"
_COURSE_HEADING = "### Course (Italian meal structure, English field name):"
_PROCESSED_MEAT_PATTERN = re.compile(r'\*([^*→]+)→\s*"processed_meat"')
_PARENTHETICAL = re.compile(r"\(.*?\)")

_SYSTEM_PROMPT = """\
You classify a recipe caption (Italian or English) into Mediterranean-diet
categories. Return only the mediterranean_categories list: objects of
{{category, servings, is_oily_fish}}. Apply these rules exactly and return an
empty list when no tracked category is substantial:

{rules}
"""

logger = logging.getLogger(__name__)


def _slice_category_rules(prompt: str) -> str:
    """Return the Mediterranean-categories block between its heading and Course."""
    start = prompt.index(_CATEGORY_HEADING)
    end = prompt.index(_COURSE_HEADING, start)
    return prompt[start:end].strip()


def _extract_processed_meat_keywords(rules: str) -> frozenset[str]:
    """Parse the Italian processed-meat terms out of the categories rules block."""
    match = _PROCESSED_MEAT_PATTERN.search(rules.replace("\n", " "))
    if match is None:
        return frozenset()
    terms = (
        _PARENTHETICAL.sub("", raw).strip().lower() for raw in match.group(1).split(",")
    )
    return frozenset(term for term in terms if term)


def load_category_rules() -> str:
    """Load and slice the Mediterranean-categories rules from the prompt file."""
    return _slice_category_rules(PROMPT_PATH.read_text(encoding="utf-8"))


def load_processed_meat_keywords() -> frozenset[str]:
    """Load the Italian processed-meat keywords from the prompt's mapping."""
    return _extract_processed_meat_keywords(load_category_rules())


def build_category_agent(*, api_key: str) -> Agent[None, list[ExtractedCategoryServing]]:
    """Build the categories-only pydantic-ai agent (reasoning effort low)."""
    model = OpenAIResponsesModel(MODEL, provider=OpenAIProvider(api_key=api_key))
    return Agent(
        model,
        output_type=list[ExtractedCategoryServing],
        system_prompt=_SYSTEM_PROMPT.format(rules=load_category_rules()),
        model_settings=OpenAIResponsesModelSettings(
            openai_reasoning_effort=REASONING_EFFORT,
        ),
    )


def propose_categories(
    agent: Agent[None, list[ExtractedCategoryServing]],
    caption: str,
) -> list[ExtractedCategoryServing]:
    """Run the agent on a caption and return its proposed categories."""
    return agent.run_sync(caption).output


def build_extraction_agent(*, api_key: str) -> Agent[None, ExtractedRecipe]:
    """Build the full-recipe agent: the batch's model, prompt and output shape.

    One recipe at a time, for a re-extraction the owner is waiting on. The
    prompt is the same file the batch renders, so a re-extraction and a batch
    extraction of the same caption ask the same question.
    """
    model = OpenAIResponsesModel(MODEL, provider=OpenAIProvider(api_key=api_key))
    return Agent(
        model,
        output_type=ExtractedRecipe,
        model_settings=OpenAIResponsesModelSettings(
            openai_reasoning_effort=REASONING_EFFORT,
        ),
    )


def extract_recipe(
    agent: Agent[None, ExtractedRecipe],
    caption: str,
) -> ExtractedRecipe:
    """Extract one recipe from caption; raise ExtractionError if the call fails."""
    prompt = render_prompt(
        template=PROMPT_PATH.read_text(encoding="utf-8"), caption=caption
    )
    try:
        return agent.run_sync(prompt).output
    except (UnexpectedModelBehavior, ModelHTTPError, OpenAIError) as exc:
        logger.warning("Re-extraction failed: %s", type(exc).__name__)
        msg = "The extraction did not come back. Try again in a moment."
        raise ExtractionError(msg) from exc
