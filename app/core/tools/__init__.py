from .python_executor_tool import executor_python
from .windows_command_tool import executor_cmd
from ..config import Config

def get_active_tools():
    """
    Retourne la liste des outils activés selon la configuration.

    Returns:
        list: Liste des outils activés
    """
    tools_map = {
        "executor_python": executor_python,
        "executor_cmd": executor_cmd,
    }

    active_tools = []
    enabled = Config.get_enabled_tools()

    for tool_name, tool_func in tools_map.items():
        if enabled.get(tool_name, False):
            active_tools.append(tool_func)

    return active_tools

# Outils actifs par défaut
TOOLS = get_active_tools()
