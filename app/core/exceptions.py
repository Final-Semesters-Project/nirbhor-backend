# app/core/exceptions.py
class DomainIntegrityError(Exception):
    def __init__(self, error_message: str, raw_error: str | None = None):
        self.error_message = error_message
        self.raw_error = raw_error
        super().__init__(error_message)

    def __str__(self) -> str:
        return self.error_message
