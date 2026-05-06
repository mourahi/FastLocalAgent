import re
import subprocess
import platform
from ..config import Config
from langchain_core.tools import tool

@tool
def executor_cmd(command: str, timeout: float = None) -> str:
    """Exécute une commande Windows via cmd.exe et retourne la sortie.

    Args:
        command (str): La commande Windows à exécuter.
        timeout (float, optional): Temps d'exécution maximum en secondes.

    Returns:
        str: La sortie standard ou l'erreur de la commande.
    """
    if timeout is None:
        timeout = Config.tool_timeout

    if platform.system().lower() != "windows":
        return "Erreur: cet outil est conçu pour Windows uniquement."

    if not isinstance(command, str) or not command.strip():
        return "Erreur: commande vide."

    if len(command) > 300:
        return "Erreur: commande trop longue."

    # Éviter les commandes potentiellement destructrices ou les opérateurs shell.
    dangerous_patterns = [
        r"\b(del|erase|format|shutdown|restart|reboot|taskkill|rmdir|rd|move|copy|xcopy|net user|net localgroup|sc |reg |setx|powershell|pwsh|curl|wget|python|pip|npm|yarn|bash|mklink|cipher|diskpart|mountvol)\b",
        r"[|&;<>()$`{}]",
        r"\n",
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return "Erreur de sécurité : opérateur ou commande potentiellement dangereuse détectée."

    try:
        result = subprocess.run(
            ["cmd", "/c", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if result.returncode != 0:
            return f"Erreur: code de sortie {result.returncode}\n{stderr or stdout}"
        return stdout or "Commande exécutée sans sortie."
    except subprocess.TimeoutExpired:
        return f"Erreur: timeout après {timeout} secondes"
    except Exception as e:
        return f"Erreur d'exécution: {str(e)}"
