import os
import time
from ..config import Config
from langchain_core.tools import tool

@tool
def lister_fichiers(path: str, timeout: float = None, max_files: int = 20) -> str:
    """Liste les fichiers d'un répertoire donné (maximum 20 fichiers par défaut).

    Un *timeout* (en secondes) empêche l'opération de bloquer trop longtemps.
    Si le temps d'exécution dépasse la limite, la fonction renvoie un message
    d'avertissement.
    
    Le *max_files* (par défaut 20) limite le nombre de fichiers affichés pour
    accélérer le traitement.
    """
    if timeout is None:
        timeout = Config.tool_timeout

    start = time.time()
    try:
        # Normaliser le chemin Windows pour gérer les backslashes simples
        normalized_path = path.replace('\\', os.sep)
        abs_path = os.path.abspath(normalized_path)
        
        # Vérifier si le chemin existe avant de lister
        if not os.path.exists(abs_path):
            return f"Erreur : le chemin '{abs_path}' n'existe pas."
        
        if not os.path.isdir(abs_path):
            return f"Erreur : '{abs_path}' n'est pas un répertoire."
        
        # Vérifier le timeout avant de lister
        if time.time() - start > timeout:
            return f"Liste interrompue après {timeout}s : accès trop lent."
        
        files = os.listdir(abs_path)
        
        # Vérifier le temps écoulé après la liste
        if time.time() - start > timeout:
            return f"Liste interrompue après {timeout}s : trop de fichiers ou accès lent."
        
        # Limiter le nombre de fichiers et optimiser l'affichage
        result = files[:max_files]
        
        # Ajouter un message si tous les fichiers ne sont pas affichés
        if len(files) > max_files:
            return "\n".join(result) + f"\n... et {len(files) - max_files} autres fichiers (non affichés)"
        
        return "\n".join(result)
    except Exception as e:
        return f"Erreur lors de l'accès au dossier : {str(e)}"
