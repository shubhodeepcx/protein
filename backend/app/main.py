from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import import_, proteins, search

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

app = FastAPI(title="ProteoLens API", version="0.1.0")
app.openapi_tags = [
    {"name": "proteins", "description": "Protein upload, metadata, and structure files."},
    {"name": "search", "description": "Public protein database search."},
    {"name": "import", "description": "Public database structure imports."},
]

_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

app.include_router(proteins.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(import_.router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "protein-backend", "version": "0.1.0"}


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "ProteoLens API", "docs": "/docs"}
