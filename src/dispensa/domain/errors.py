class DispensaError(Exception):
    """Base class for all Dispensa errors."""


class InstagramFetchError(DispensaError):
    """Raised when fetching data from Instagram fails."""


class ExtractionError(DispensaError):
    """Raised when LLM recipe extraction fails or returns invalid data."""


class PromptTemplateError(DispensaError):
    """Raised when a prompt template lacks exactly one caption marker."""


class StorageError(DispensaError):
    """Raised when reading or writing persisted recipes fails."""


class ImageUploadError(DispensaError):
    """Raised when hosting a durable image copy (Cloudinary) fails."""


class ConfigurationError(DispensaError):
    """Raised when a required setting is missing for the requested operation."""
