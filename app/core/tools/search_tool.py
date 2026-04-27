from ..config import Config

def search_tool(query: str, timeout: float = None, max_depth: int = 3) -> str:
    """Chercher le nom d'un fichier ou d'un répertoire avec limite de temps et de profondeur.

    Le *query* est interprété comme un chemin relatif ou absolu. La fonction
    vérifie d'abord si le chemin correspond à un fichier ou répertoire. Si le
    chemin n'existe pas, elle parcourt récursivement le répertoire de travail
    actuel à la recherche d'un fichier ou dossier dont le nom contient la
    chaîne fournie (insensible à la casse).

    Un **timeout** (en secondes) empêche la recherche de bloquer indéfiniment :
    si la durée dépasse la valeur fournie, la fonction renvoie un message
    d'avertissement.
    
    Le **max_depth** (par défaut 3) limite la profondeur de recherche pour accélérer
    le processus.
    """
    import os
    import time
    from pathlib import Path

    # Utiliser le timeout configuré si aucun n'est fourni
    if timeout is None:
        timeout = Config.tool_timeout

    start = time.time()

    # Normaliser le chemin fourni
    path = Path(query).expanduser().resolve()

    # 1. Vérifier l'existence exacte du chemin
    if path.is_file():
        return f"Fichier trouvé : {path}"
    if path.is_dir():
        return f"Répertoire trouvé : {path}"

    # 2. Recherche récursive dans le répertoire de travail actuel avec limite de profondeur
    cwd = Path.cwd()
    lowered = query.lower()
    
    # Utiliser os.walk avec une limite de profondeur
    for root, dirs, files in os.walk(cwd):
        # Vérifier le temps écoulé à chaque itération
        if time.time() - start > timeout:
            return f"Recherche interrompue après {timeout}s : aucun résultat trouvé rapidement."
        
        # Calculer la profondeur actuelle
        current_depth = root.relative_to(cwd).parts.__len__()
        
        # Si on dépasse la profondeur maximale, on arrête d'explorer ce sous-répertoire
        if current_depth > max_depth:
            dirs.clear()  # Ne pas explorer les sous-dossiers
            continue
        
        # Recherche dans les dossiers (optimisée avec une compréhension de liste)
        matching_dirs = [d for d in dirs if lowered in d.lower()]
        if matching_dirs:
            return f"Répertoire trouvé : {Path(root) / matching_dirs[0]}"
        
        # Recherche dans les fichiers (optimisée avec une compréhension de liste)
        matching_files = [f for f in files if lowered in f.lower()]
        if matching_files:
            return f"Fichier trouvé : {Path(root) / matching_files[0]}"

    return f"Aucun fichier ou répertoire correspondant à '{query}' n'a été trouvé (profondeur max: {max_depth})."