import os
import tempfile
import subprocess
import time
from ..config import Config
from langchain_core.tools import tool

@tool
def executor_python(code: str, timeout: float = None) -> str:
    """Exécute du code Python pour récupérer des informations système (heure, date, fichiers locaux) ou effectuer des calculs complexes.
    ATTENTION: Cette fonction exécute du code Python arbitraire. Utilisez uniquement pour des opérations de confiance.

    Args:
        code (str): Le code Python complet à exécuter (ex: import datetime; print(datetime.datetime.now()))
        timeout (float, optional): Temps maximum d'exécution en secondes.
                                  Par défaut, utilise Config.tool_timeout.

    Returns:
        str: Le résultat de l'exécution du code ou un message d'erreur.
    """
    if timeout is None:
        timeout = Config.tool_timeout

    # Sécurité basique : vérifier que le code ne contient pas d'imports dangereux
    dangerous_imports = ['os.system', 'subprocess', 'sys.exit', 'eval', 'exec', '__import__']
    for dangerous in dangerous_imports:
        if dangerous in code:
            return f"Erreur de sécurité : Import ou fonction dangereux détecté : {dangerous}"

    # Limiter la longueur du code
    if len(code) > 1000:
        return "Erreur : Code trop long (maximum 1000 caractères)"

    try:
        # Créer un fichier temporaire pour le code Python
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name

        try:
            # Exécuter le fichier Python avec un timeout et restrictions
            start_time = time.time()
            result = subprocess.run(
                ['python', temp_file],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tempfile.gettempdir()  # Exécuter dans un répertoire temporaire
            )
            execution_time = time.time() - start_time

            # Préparer le résultat - renvoyer uniquement la sortie standard
            if result.stdout:
                return result.stdout.strip()
            elif result.stderr:
                return f"Erreur: {result.stderr.strip()}"
            else:
                return "Code exécuté avec succès mais aucune sortie"
        finally:
            # Supprimer le fichier temporaire
            try:
                os.unlink(temp_file)
            except:
                pass
    except subprocess.TimeoutExpired:
        return f"Erreur: Timeout après {timeout} secondes"
    except Exception as e:
        return f"Erreur d'exécution: {str(e)}"
