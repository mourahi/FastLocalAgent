"""
Module de configuration globale pour FastAgent.
Gère les paramètres dynamiques : modèle LLM et outils activés.
"""

class Config:
    """Configuration globale de l'application"""
    
    # Modèle LLM par défaut (qwen2.5-coder:3b est rapide et compatible avec les outils)
    model_name: str = "qwen2.5-coder:3b"
    
    # Température du modèle (ajustée pour un bon équilibre entre qualité et vitesse)
    temperature: float = 0.7
    
    # Outils activés par défaut
    enabled_tools: dict = {
        "lister": False,  # Désactivé car redondant avec executor_python
        "search": False,  # Désactivé car redondant avec executor_python
        "executor_python": True,
        "executor_cmd": True,
    }
    
    # URL of the Ollama server (default http://localhost:11434)
    ollama_base_url: str = "http://localhost:11434"

    # Timeout (seconds) for the search tool to avoid long blocking searches

    # Timeout (seconds) applied to all tools to prevent long blocking operations (réduit pour plus de réactivité)
    tool_timeout: float = 3.0

    # Flag to request stopping the current model processing
    stop_requested: bool = False
    
    # Performance settings
    enable_model_preloading: bool = True  # Activé par défaut pour éviter la latence de la première requête
    enable_model_check: bool = True  # Vérifier la disponibilité des modèles au démarrage
    
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
    def get_enable_model_preloading(cls) -> bool:
        """Retourne si le préchargement du modèle est activé"""
        return cls.enable_model_preloading
    
    @classmethod
    def set_enable_model_preloading(cls, enabled: bool) -> None:
        """Active/désactive le préchargement du modèle"""
        cls.enable_model_preloading = enabled
    
    @classmethod
    def get_enable_model_check(cls) -> bool:
        """Retourne si la vérification des modèles est activée"""
        return cls.enable_model_check
    
    @classmethod
    def set_enable_model_check(cls, enabled: bool) -> None:
        """Active/désactive la vérification des modèles au démarrage"""
        cls.enable_model_check = enabled
    
    @classmethod
    def to_dict(cls) -> dict:
        """Retourne la configuration complète sous forme de dictionnaire"""
        return {
            "model_name": cls.model_name,
            "temperature": cls.temperature,
            "enabled_tools": cls.enabled_tools,
            "enable_model_preloading": cls.enable_model_preloading,
            "enable_model_check": cls.enable_model_check
        }
