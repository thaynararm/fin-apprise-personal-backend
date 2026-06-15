class DomainException(Exception):
    def __init__(self, message: str, *, status_code: int, error: str):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error = error


class ValidationDomainError(DomainException):
    def __init__(self, message: str):
        super().__init__(message, status_code=400, error="Validation error")


class ConflictDomainError(DomainException):
    def __init__(self, message: str):
        super().__init__(message, status_code=409, error="Conflict")