"""
FastAPI Application for ClinRESET Web Interface.
Serves report simplification endpoints, model methodology settings,
and static single-page frontend.
"""

from __future__ import annotations

import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .routes import methodologies, reports

logger = logging.getLogger("web.app")

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = FastAPI(
    title="ClinRESET — Clinical Report Simplification Platform",
    description="Deterministic Medical Report Parsing, Terminology Normalization, and Patient Explanation",
    version="2.0.0",
)

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(reports.router)
app.include_router(methodologies.router)

# Mount static assets
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/api/health")
def health_check():
    """Health status endpoint."""
    return {"status": "ok", "app": "ClinRESET", "version": "2.0.0"}


@app.get("/")
def serve_index():
    """Serves the single-page application frontend."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "message": "ClinRESET Web API is running. Static frontend not yet compiled.",
        "docs_url": "/docs",
    }
