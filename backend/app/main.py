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
    {"name": "search", "description": "Full-text search across RCSB PDB, AlphaFold DB, and UniProt."},
    {"name": "import", "description": "One-click import of a public structure into local storage."},
]

# CORS_ORIGINS is required — leave unset to deny all origins (deploy-time loud failure).
# See backend/.env.example for the local-dev value.
_cors_origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# `import_` is registered before `proteins` so POST /api/proteins/import can
# never be shadowed by a future POST /api/proteins/{uid} route.
app.include_router(import_.router, prefix="/api")
app.include_router(proteins.router, prefix="/api")
app.include_router(search.router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "protein-backend", "version": "0.1.0"}


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "ProteoLens API", "docs": "/docs"}
