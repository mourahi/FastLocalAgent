from ..config import Config

def search_tool(query: str, timeout: float = None) -> str:
    """Chercher le nom d'un fichier ou d'un répertoire avec limite de temps.

    Le *query* est interprété comme un chemin relatif ou absolu. La fonction
    vérifie d'abord si le chemin correspond à un fichier ou répertoire. Si le
    chemin n'existe pas, elle parcourt récursivement le répertoire de travail
    actuel à la recherche d'un fichier ou dossier dont le nom contient la
    chaîne fournie (insensible à la casse).

    Un **timeout** (en secondes) empêche la recherche de bloquer indéfiniment :
    si la durée dépasse la valeur fournie, la fonction renvoie un message
    d'avertissement.
    """
    import os
    import time
    from pathlib import Path

    # Utiliser le timeout configuré si aucun n'est fourni
    if timeout is None:
        timeout = Config.search_timeout

    start = time.time()

    # Normaliser le chemin fourni
    path = Path(query).expanduser().resolve()

    # 1. Vérifier l'existence exacte du chemin
    if path.is_file():
        return f"Fichier trouvé : {path}"
    if path.is_dir():
        return f"Répertoire trouvé : {path}"

    # 2. Recherche récursive dans le répertoire de travail actuel
    cwd = Path.cwd()
    lowered = query.lower()
    for root, dirs, files in os.walk(cwd):
        # Vérifier le temps écoulé à chaque itération
        if time.time() - start > timeout:
            return f"Recherche interrompue après {timeout}s : aucun résultat trouvé rapidement."
        # Recherche dans les dossiers
        for d in dirs:
            if lowered in d.lower():
                return f"Répertoire trouvé : {Path(root) / d}"
        # Recherche dans les fichiers
        for f in files:
            if lowered in f.lower():
                return f"Fichier trouvé : {Path(root) / f}"

    return f"Aucun fichier ou répertoire correspondant à '{query}' n'a été trouvé."