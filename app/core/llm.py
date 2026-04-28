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
    
    Args:
        model_name: Nom du modèle à utiliser (optionnel, utilise Config sinon)
        temperature: Température du modèle (optionnel, utilise Config sinon)
    
    Returns:
        ChatOllama: Instance du modèle LLM configuré
    """
    model = model_name or Config.get_model_name()
    temp = temperature if temperature is not None else Config.get_temperature()
    
    return ChatOllama(
        model=model,
        temperature=temp,
        streaming=True,
        base_url=Config.ollama_base_url,
        # Paramètres d'optimisation pour qwen2.5-coder:3b
        num_ctx=2048,  # Taille du contexte optimisée pour la vitesse
        num_predict=512,  # Longueur de réponse équilibrée
        top_k=20,  # Réduit le nombre de tokens pour accélérer
        top_p=0.85,  # Contrôle la diversité
        repeat_penalty=1.15,  # Évite les répétitions
        num_gpu=1,  # Utilise le GPU si disponible
        num_thread=4,  # Utilise 4 threads pour le traitement parallèle
        mirostat=2,  # Améliore la qualité des réponses
        mirostat_tau=5.0,  # Contrôle la diversité des réponses
        mirostat_eta=0.1,  # Ajuste la vitesse d'adaptation
        keep_alive=-1,  # Garder le modèle en mémoire
    )