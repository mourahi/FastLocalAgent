import os
import time
from ..config import Config
from langchain_core.tools import tool

@tool
def lister_fichiers(path: str, timeout: float = None) -> str:
    """Liste les fichiers d'un répertoire donné (maximum 20 fichiers).

    Un *timeout* (en secondes) empêche l'opération de bloquer trop longtemps.
    Si le temps d'exécution dépasse la limite, la fonction renvoie un message
    d'avertissement.
    """
    if timeout is None:
        timeout = Config.tool_timeout

    start = time.time()
    try:
        abs_path = os.path.abspath(path)
        files = os.listdir(abs_path)
        # Vérifier le temps écoulé avant de retourner le résultat
        if time.time() - start > timeout:
            return f"Liste interrompue après {timeout}s : trop de fichiers ou accès lent."
        return "\n".join(files[:20])
    except Exception as e:
        return f"Erreur lors de l'accès au dossier : {str(e)}"
