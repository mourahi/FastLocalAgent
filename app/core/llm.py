from langchain_ollama import ChatOllama
from .config import Config

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
        base_url=Config.ollama_base_url
    )