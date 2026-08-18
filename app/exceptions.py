"""Custom exceptions for the recruitment sourcing pipeline."""


class AppError(Exception):
    """Base application error with a user-facing message."""

    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class DocumentExtractionError(AppError):
    def __init__(self, message: str):
        super().__init__(message, status_code=400)


class PDFExtractionError(DocumentExtractionError):
    pass


class JDExtractionError(AppError):
    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message, status_code=status_code)


class SearchError(AppError):
    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message, status_code=status_code)


class QuotaExceededError(SearchError):
    def __init__(self, message: str = "SerpApi quota or rate limit exceeded."):
        super().__init__(message, status_code=429)
