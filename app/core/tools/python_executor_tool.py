import os
import re
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

    # Valider la syntaxe — si invalide, tenter un fallback basé sur l'intention
    try:
        compile(code, '<string>', 'exec')
    except SyntaxError:
        import platform
        if 'disk_usage' in code or 'statvfs' in code:
            drive = 'C:\\\\' if platform.system() == 'Windows' else '/'
            code = (
                "import shutil\n"
                "du = shutil.disk_usage('" + drive + "')\n"
                "print(f'Libre : {du.free/1024**3:.1f} Go  |  Utilisé : {du.used/1024**3:.1f} Go  |  Total : {du.total/1024**3:.1f} Go')"
            )
        elif 'virtual_memory' in code or 'ram' in code.lower() or 'memory' in code.lower():
            code = (
                "import psutil\n"
                "m = psutil.virtual_memory()\n"
                "print(f'Disponible : {m.available/1024**3:.1f} Go  |  Utilisé : {m.used/1024**3:.1f} Go  |  Total : {m.total/1024**3:.1f} Go')"
            )
        elif 'cpu' in code.lower():
            code = (
                "import psutil\n"
                "print(f'CPU : {psutil.cpu_percent(interval=1)}%')"
            )

    # Adapter le code pour Windows si nécessaire
    import platform
    if platform.system() == 'Windows':
        # Injecter un shim os.statvfs compatible Windows
        if 'os.statvfs' in code:
            statvfs_shim = (
                "import shutil as _shutil, os as _os\n"
                "class _StatvfsResult:\n"
                "    def __init__(self, path):\n"
                "        du = _shutil.disk_usage('C:\\\\')\n"
                "        self.f_frsize = 4096; self.f_bsize = 4096\n"
                "        self.f_blocks = du.total // 4096\n"
                "        self.f_bfree = du.free // 4096\n"
                "        self.f_bavail = du.free // 4096\n"
                "        self.f_files = 0; self.f_ffree = 0\n"
                "_os.statvfs = _StatvfsResult\n"
                "_stat = _os.statvfs('/')\n"
                "_frsize = _stat.f_frsize\n"
                "_blocks = _stat.f_blocks\n"
                "_bfree = _stat.f_bfree\n"
                "_bavail = _stat.f_bavail\n"
            )
            code = statvfs_shim + code

        # Corriger les alias psutil (ex: import psutil utilisé comme ps)
        if 'psutil' in code:
            code = re.sub(r'\bps\.disk_usage\b', 'psutil.disk_usage', code)
            code = re.sub(r"psutil\.disk_usage\s*\(\s*['\"/]\s*'\s*\)", "psutil.disk_usage('C:\\\\')", code)
            code = re.sub(r'psutil\.disk_usage\s*\(\s*"/"\s*\)', "psutil.disk_usage('C:\\\\')", code)

    def _run_code(code: str, timeout: float) -> subprocess.CompletedProcess:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file = f.name
        try:
            return subprocess.run(
                ['python', temp_file],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tempfile.gettempdir()
            ), temp_file
        finally:
            try:
                os.unlink(temp_file)
            except:
                pass

    try:
        result, _ = _run_code(code, timeout)

        # Auto-install si ModuleNotFoundError détecté
        install_notice = ""
        if result.returncode != 0 and 'ModuleNotFoundError' in result.stderr:
            match = re.search(r"No module named '([^']+)'", result.stderr)
            if match:
                module = match.group(1).split('.')[0]
                install_notice = f"📦 Installation de {module} en cours...\n"
                install = subprocess.run(
                    ['pip', 'install', module],
                    capture_output=True, text=True, timeout=60
                )
                if install.returncode == 0:
                    install_notice += f"✅ {module} installé avec succès.\n\n"
                    result, _ = _run_code(code, timeout)
                else:
                    return install_notice + "❌ Échec installation " + module + " : " + install.stderr.strip()

        if result.stdout:
            return install_notice + result.stdout.strip()
        elif result.stderr:
            return install_notice + "Erreur: " + result.stderr.strip()
        else:
            return install_notice + "Code exécuté avec succès mais aucune sortie"

    except subprocess.TimeoutExpired:
        return f"Erreur: Timeout après {timeout} secondes"
    except Exception as e:
        return f"Erreur d'exécution: {str(e)}"
