from langchain_ollama import ChatOllama
from .config import Config
import httpx

async def initialize_default_model():
    """
    Initialise le premier modèle disponible comme modèle par défaut
    si le modèle configuré n'est pas disponible.
    Version optimisée pour le démarrage rapide.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{Config.ollama_base_url}/api/tags", timeout=2.0)
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                if models:
                    # Vérifier si le modèle par défaut existe
                    default_model = Config.get_model_name()
                    model_names = [model["name"] for model in models]
                    
                    if default_model not in model_names:
                        # Utiliser le premier modèle disponible
                        first_model = models[0]["name"]
                        Config.set_model_name(first_model)
                        print(f"ℹ️ Modèle par défaut changé vers: {first_model}")
                    else:
                        print(f"ℹ️ Modèle {default_model} vérifié et disponible")
    except Exception as e:
        print(f"⚠️ Impossible de vérifier les modèles Ollama: {e}")
        print("ℹ️ Utilisation du modèle configuré par défaut")

def get_llm(model_name: str = None, temperature: float = None):
    """
    Retourne le modèle LLM configuré.
    """
    model = model_name or Config.get_model_name()
    temp = temperature if temperature is not None else Config.get_temperature()
    
    return ChatOllama(
        model=model,
        temperature=temp,
        streaming=True,
        base_url=Config.ollama_base_url,
    )