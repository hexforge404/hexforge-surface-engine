from __future__ import annotations

import os
from fastapi import FastAPI

ROOT_PATH = os.getenv("ROOT_PATH", "/api/surface")

app = FastAPI(title="HexForge GlyphEngine", version="contracts-v1")


@app.get(f"{ROOT_PATH}/health")
def health():
    return {"ok": True, "service": "hexforge-glyphengine"}


# Mount job routes (contracts-v1)
from hse.routes.jobs import router as jobs_router  # noqa: E402

app.include_router(jobs_router, prefix=ROOT_PATH)
