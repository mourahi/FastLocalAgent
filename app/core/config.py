"""
Module de configuration globale pour FastAgent.
Gère les paramètres dynamiques : modèle LLM et outils activés.
"""

class Config:
    """Configuration globale de l'application"""
    
    # Modèle LLM par défaut
    model_name: str = "qwen2.5:3b"
    
    # Température du modèle
    temperature: float = 0.1
    
    # Outils activés par défaut
    enabled_tools: dict = {
        "lister": True,
        "math": True,
        "search": True
    }
    
    # URL of the Ollama server (default http://localhost:11434)
    ollama_base_url: str = "http://localhost:11434"

    # Timeout (seconds) for the search tool to avoid long blocking searches

    # Timeout (seconds) applied to all tools to prevent long blocking operations
    tool_timeout: float = 5.0

    # Flag to request stopping the current model processing
    stop_requested: bool = False
    
    @classmethod
    def get_model_name(cls) -> str:
        """Retourne le nom du modèle configuré"""
        return cls.model_name
    
    @classmethod
    def set_model_name(cls, model: str) -> None:
        """Définit le modèle LLM à utiliser"""
        cls.model_name = model
    
    @classmethod
    def get_temperature(cls) -> float:
        """Retourne la température configurée"""
        return cls.temperature
    
    @classmethod
    def set_temperature(cls, temp: float) -> None:
        """Définit la température du modèle"""
        cls.temperature = temp
    
    @classmethod
    def get_enabled_tools(cls) -> dict:
        """Retourne le dictionnaire des outils activés"""
        return cls.enabled_tools
    
    @classmethod
    def set_enabled_tools(cls, tools: dict) -> None:
        """Définit les outils activés"""
        cls.enabled_tools = tools

    @classmethod
    def request_stop(cls) -> None:
        """Signal to stop the ongoing model streaming"""
        cls.stop_requested = True

    @classmethod
    def clear_stop(cls) -> None:
        """Clear the stop request flag"""
        cls.stop_requested = False
    
    @classmethod
    def is_tool_enabled(cls, tool_name: str) -> bool:
        """Vérifie si un outil spécifique est activé"""
        return cls.enabled_tools.get(tool_name, False)
    
    @classmethod
    def to_dict(cls) -> dict:
        """Retourne la configuration complète sous forme de dictionnaire"""
        return {
            "model_name": cls.model_name,
            "temperature": cls.temperature,
            "enabled_tools": cls.enabled_tools
        }
