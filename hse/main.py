from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hse.api.routes import router as surface_router

app = FastAPI(title="Hexforge-Glyphengine", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"] ,
    allow_headers=["*"] ,
)

app.include_router(surface_router)
