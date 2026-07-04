class FoodiegramError(Exception):
    """Base class for all Foodiegram errors."""


class InstagramFetchError(FoodiegramError):
    """Raised when fetching data from Instagram fails."""


class ExtractionError(FoodiegramError):
    """Raised when LLM recipe extraction fails or returns invalid data."""


class PromptTemplateError(FoodiegramError):
    """Raised when a prompt template lacks exactly one caption marker."""


class StorageError(FoodiegramError):
    """Raised when reading or writing persisted recipes fails."""
