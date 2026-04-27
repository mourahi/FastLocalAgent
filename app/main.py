from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from .api.routes import router

app = FastAPI(title="Agent Local")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Monter le dossier static pour servir index.html
app.mount("/static", StaticFiles(directory="static"), name="static")

# Monter le dossier images
IMAGE_DIR = os.path.abspath("images")
app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")

# Inclure les routes
app.include_router(router)