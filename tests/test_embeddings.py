from dataclasses import dataclass, field
from typing import cast

from openai import OpenAI

from foodiegram.ai.embeddings import EMBEDDING_MODEL, embed_texts, recipe_document
from foodiegram.domain.enums import CuisineType, DishType, MealType
from foodiegram.domain.models import Recipe


def _recipe(**overrides: object) -> Recipe:
    """Build a minimal Recipe, overriding only the fields a test cares about."""
    base: dict[str, object] = {
        "code": "ABC",
        "pk": "1",
        "post_url": None,
        "caption": None,
        "title": "Pasta al pomodoro",
        "ingredients": ["pasta", "pomodori", "basilico"],
        "instructions": ["cuoci"],
        "dish_type": DishType.PASTA,
        "meal_type": MealType.DINNER,
        "cuisine_type": CuisineType.ITALIAN,
        "proteins": ["uova"],
    }
    base.update(overrides)
    return Recipe.model_validate(base)


def test_recipe_document_includes_title_classifications_proteins_ingredients() -> None:
    """The document carries title, taxonomy, proteins, and ingredients."""
    document = recipe_document(_recipe())

    assert "Pasta al pomodoro" in document
    assert "pasta dinner italian" in document
    assert "uova" in document
    assert "pasta" in document
    assert "pomodori" in document
    assert "basilico" in document


def test_recipe_document_omits_empty_proteins() -> None:
    """Empty protein tags produce no protein line and no blank lines."""
    document = recipe_document(_recipe(proteins=[]))

    assert document.splitlines() == [
        "Pasta al pomodoro",
        "pasta dinner italian",
        "pasta pomodori basilico",
    ]


def test_recipe_document_without_title_still_returns_useful_text() -> None:
    """Other fields still embed when the title is missing."""
    document = recipe_document(_recipe(title=None))

    assert "Pasta al pomodoro" not in document
    assert "pasta dinner italian" in document
    assert "uova" in document
    assert "pasta pomodori basilico" in document


@dataclass
class _FakeEmbeddingItem:
    index: int
    embedding: list[float]


@dataclass
class _FakeEmbeddingResponse:
    data: list[_FakeEmbeddingItem]


@dataclass
class _FakeEmbeddings:
    calls: list[dict[str, object]] = field(default_factory=list)

    def create(
        self,
        *,
        input: list[str],  # noqa: A002
        model: str,
    ) -> _FakeEmbeddingResponse:
        self.calls.append({"input": input, "model": model})
        return _FakeEmbeddingResponse(
            data=[
                _FakeEmbeddingItem(index=index, embedding=[float(index), 0.5])
                for index, _text in enumerate(input)
            ],
        )


@dataclass
class _FakeOpenAI:
    embeddings: _FakeEmbeddings = field(default_factory=_FakeEmbeddings)


def test_embed_texts_returns_vectors_in_input_order_with_one_call() -> None:
    """Vectors match input order and the client is called exactly once."""
    fake = _FakeOpenAI()
    client = cast("OpenAI", fake)

    vectors = embed_texts(["alpha", "beta", "gamma"], client=client)

    assert vectors == [[0.0, 0.5], [1.0, 0.5], [2.0, 0.5]]
    assert len(fake.embeddings.calls) == 1
    assert fake.embeddings.calls[0]["input"] == ["alpha", "beta", "gamma"]


def test_embed_texts_uses_default_model_and_honours_override() -> None:
    """Default model is EMBEDDING_MODEL; callers may override it."""
    fake = _FakeOpenAI()
    client = cast("OpenAI", fake)

    embed_texts(["one"], client=client)
    embed_texts(["two"], client=client, model="text-embedding-3-large")

    assert fake.embeddings.calls[0]["model"] == EMBEDDING_MODEL
    assert fake.embeddings.calls[1]["model"] == "text-embedding-3-large"
