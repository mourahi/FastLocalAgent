from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from .llm import get_llm
from .tools import get_active_tools
from .prompt import SYSTEM_PROMPT
from .config import Config

memory = MemorySaver()

# Cache pour l'agent
_agent_cache = None
_config_cache = None

def get_agent(force_recreate: bool = False):
    """
    Crée et retourne l'agent IA.
    Utilise un cache pour éviter de recréer l'agent à chaque fois.
    
    Args:
        force_recreate: Force la recréation de l'agent (utile après changement de config)
    
    Returns:
        Agent: Instance de l'agent ReAct
    """
    global _agent_cache, _config_cache
    
    # Vérifier si la configuration a changé
    current_config = Config.to_dict()
    
    if _agent_cache is not None and not force_recreate:
        # Vérifier si la config n'a pas changé
        if _config_cache == current_config:
            return _agent_cache
    
    # Recréer l'agent avec la configuration actuelle
    llm = get_llm()
    active_tools = get_active_tools()
    
    _agent_cache = create_react_agent(
        model=llm,
        tools=active_tools,
        checkpointer=memory,
        prompt=SYSTEM_PROMPT
    )
    
    _config_cache = current_config
    
    return _agent_cache