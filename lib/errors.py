class OrganizerError(Exception):
    """Base exception for paper-organizer."""


class ExtractorError(OrganizerError):
    """Metadata extraction failed."""


class LLMError(OrganizerError):
    """LLM request or parsing failed."""


class RenamerError(OrganizerError):
    """Rename operation failed."""


class IndexWriterError(OrganizerError):
    """Index write operation failed."""
