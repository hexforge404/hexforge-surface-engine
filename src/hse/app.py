from fastapi import FastAPI
from hse.routes.jobs import router as jobs_router

def create_app() -> FastAPI:
    app = FastAPI(title="HexForge Surface Engine", version="0.1.0")
    app.include_router(jobs_router)
    return app

app = create_app()
