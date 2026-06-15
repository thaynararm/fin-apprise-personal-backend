# src/core/exceptions/handlers.py

from fastapi import Request, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from src.core.exceptions.domain import DomainException


def register_exception_handlers(app: FastAPI):

    @app.exception_handler(DomainException)
    async def domain_exception_handler(request: Request, exc: DomainException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.error, "message": exc.message},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        errors = []

        for err in exc.errors():
            field = err["loc"][-1]
            message = err["msg"]

            errors.append({"field": field, "message": message})

        return JSONResponse(
            status_code=422,
            content={"error": "Validation error", "details": errors},
        )
