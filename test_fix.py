import re

def _fix_common_errors(code: str) -> str:
    print('Original code:', repr(code))

    # Corriger les f-strings avec des formats invalides
    code = re.sub(r'\{([^}]+):\.f\}', r'{\1:.2f}', code)
    print('After f-string fix:', repr(code))

    # Corriger les appels de méthodes incomplets
    if 'disk_usage' in code:
        code = re.sub(r'(\w+)\s*=\s*\.disk_usage', r'\1 = shutil.disk_usage', code)
        code = re.sub(r'stat\s*=\s*\.disk_usage', r'stat = shutil.disk_usage', code)
    print('After disk_usage fix:', repr(code))

    # Corriger les références de variables manquantes dans les f-strings
    if 'disk_usage' in code and re.search(r'\{(\.|\s*\.)', code):
        code = re.sub(r'\{(\.|\s*\.)free', r'{stat.free', code)
        code = re.sub(r'\{(\.|\s*\.)used', r'{stat.used', code)
        code = re.sub(r'\{(\.|\s*\.)total', r'{stat.total', code)
    print('After variable fix:', repr(code))

    # Corriger les imports manquants
    if 'shutil.disk_usage' in code and 'import shutil' not in code:
        code = 'import shutil\n' + code
    print('After import fix:', repr(code))

    return code

test_code = "import shutil\nstat = .disk_usage('C:/')\nprint(f\"{.free / (1024**3):.f} GB\")"
result = _fix_common_errors(test_code)
print('Final result:', repr(result))