
from .search_tool import search_tool
from .math_tool import math_tool
from .lister_fichiers_tool import lister_fichiers
from ..config import Config

def get_active_tools():
    """
    Retourne la liste des outils activés selon la configuration.
    
    Returns:
        list: Liste des outils activés
    """
    tools_map = {
        "lister": lister_fichiers,
        "math": math_tool,
        "search": search_tool
    }
    
    active_tools = []
    enabled = Config.get_enabled_tools()
    
    for tool_name, tool_func in tools_map.items():
        if enabled.get(tool_name, False):
            active_tools.append(tool_func)
    
    return active_tools

# Outils actifs par défaut
TOOLS = get_active_tools()
