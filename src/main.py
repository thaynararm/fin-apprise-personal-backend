# src/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routers import api_router
from src.core.config import settings
from src.core.logging.config import setup_logging
from src.core.exceptions.handlers import register_exception_handlers

app = FastAPI(title="Finance API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def normalize_trailing_slash(request, call_next):
    # Accept both /path and /path/ without triggering 307 redirects.
    path = request.scope.get("path", "")
    if path != "/" and path.endswith("/"):
        request.scope["path"] = path.rstrip("/")
    return await call_next(request)


setup_logging()

register_exception_handlers(app)

app.include_router(api_router)
