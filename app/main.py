from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import asyncio
import httpx

from .api.routes import router
from .core.llm import initialize_default_model, get_llm
from .core.config import Config

app = FastAPI(
    title="Agent Local",
    # Optimisations des performances
    docs_url=None,  # Désactive la documentation Swagger pour économiser les ressources
    redoc_url=None,  # Désactive la documentation ReDoc pour économiser les ressources
)

@app.on_event("startup")
async def startup_event():
    """Initialise le premier modèle disponible au démarrage du serveur et précharge le modèle dans la mémoire"""
    print("🚀 Démarrage de l'application Agent Local...")

    # Initialiser le modèle par défaut
    await initialize_default_model()

    # Précharger le modèle dans la mémoire avec une méthode plus efficace
    try:
        model_name = Config.get_model_name()
        print(f"⏳ Préchargement du modèle {model_name} dans la mémoire...")
        
        # Précharger le modèle avec plusieurs requêtes courtes via l'API Ollama directe
        test_prompts = ["Hi", "Test", "Ready", "Hello", "Start"]
        
        for i, prompt in enumerate(test_prompts, 1):
            try:
                print(f"  ⏳ Préchargement {i}/{len(test_prompts)}: '{prompt}'")
                
                payload = {
                    "model": model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": 10,  # Réduit la longueur de réponse pour le préchargement
                        "temperature": 0.1   # Température basse pour des réponses prévisibles
                    }
                }
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{Config.ollama_base_url}/api/generate",
                        json=payload,
                        timeout=60.0
                    )
                    
                    if response.status_code == 200:
                        print(f"  ✅ Préchargement {i}/{len(test_prompts)} terminé")
                    else:
                        print(f"  ⚠️ Erreur lors du préchargement {i}: {response.status_code}")
                        
            except Exception as e:
                print(f"  ❌ Erreur lors du préchargement {i}: {e}")
                continue
        
        print(f"✅ Modèle {model_name} préchargé avec succès !")
    except Exception as e:
        print(f"⚠️ Erreur lors du préchargement du modèle: {e}")

    print("🎉 Application prête à recevoir des requêtes !")

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
