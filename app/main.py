from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio

from .api.routes import router
from .core.llm import initialize_default_model
from .core.config import Config

app = FastAPI(
    title="Agent Local",
    # Optimisations des performances
    docs_url=None,  # Désactive la documentation Swagger pour économiser les ressources
    redoc_url=None,  # Désactive la documentation ReDoc pour économiser les ressources
)

# Monter les fichiers statiques
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configurer CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],  # Restreindre aux origines locales
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialise le premier modèle disponible au démarrage du serveur et précharge le modèle dans la mémoire"""
    print("🚀 Démarrage de l'application Agent Local...")

    # Initialiser le modèle par défaut
    if Config.enable_model_check:
        await initialize_default_model()

    # Précharger l'agent complet avant d'accepter les requêtes
    if Config.enable_model_preloading:
        await preload_agent_async()
        print("🔄 Préchargement de l'agent terminé avant le démarrage du serveur")
    else:
        print("ℹ️ Préchargement de l'agent désactivé (démarrage rapide)")

    print("🎉 Application prête à recevoir des requêtes !")


async def preload_agent_async():
    """Précharge l'agent complet (modèle + LangGraph) de manière asynchrone"""
    try:
        from .core.agent import get_agent

        print(f"⏳ Préchargement de l'agent...")
        
        # Créer l'agent (cela chargera le modèle et initialisera LangGraph)
        start_time = asyncio.get_event_loop().time()
        agent = get_agent(force_recreate=True)
        agent_time = asyncio.get_event_loop().time() - start_time
        
        # Faire une requête de test pour s'assurer que tout fonctionne
        test_start = asyncio.get_event_loop().time()
        # On ne fait pas de requête réelle pour éviter de consommer des ressources
        # Juste l'initialisation
        test_time = asyncio.get_event_loop().time() - test_start
        
        print(f"✅ Agent préchargé avec succès en arrière-plan (agent: {agent_time:.2f}s, test: {test_time:.2f}s)")
        
    except Exception as e:
        print(f"⚠️ Erreur lors du préchargement de l'agent: {e}")
app.include_router(router)
