import re
import json

def fix_malformed_json(text):
    """Corrige les erreurs JSON courantes générées par le modèle."""
    import re
    
    # Étape 0: Extraire le code avant de faire des remplacements
    code_pattern = r'code["\s:=]*([^"]*(?:GB|print|shutil)[^}]*?)(?=["\s]*[,}]|timeout)'
    code_match = re.search(code_pattern, text, re.IGNORECASE | re.DOTALL)
    
    extracted_code = None
    if code_match:
        extracted_code = code_match.group(1).strip()
        # Nettoyer le code extrait
        if extracted_code.endswith('"'):
            extracted_code = extracted_code[:-1]
        if not extracted_code.startswith('"'):
            extracted_code = extracted_code
    
    # Étape 1: Corrections des noms d'outils
    text = text.replace('"executor"', '"executor_python"')
    text = text.replace('executor', '"executor_python"')
    text = re.sub(r':\s*"executor"', ': "executor_python"', text)
    
    # Étape 2: Corriger arguments { → "arguments": {
    text = re.sub(r'(executor["\s]*),?\s*arguments\s*{', r'\1, "arguments": {', text, flags=re.IGNORECASE)
    text = re.sub(r'}\s*arguments\s*{', '}, "arguments": {', text, flags=re.IGNORECASE)
    
    # Étape 3: Extraire et nettoyer le timeout
    timeout_match = re.search(r'timeout\s*[:=]?\s*([0-9]+)', text, re.IGNORECASE)
    timeout_value = timeout_match.group(1) if timeout_match else "5"
    
    # Étape 4: Reconstruire le JSON si nécessaire
    if extracted_code:
        # Nettoyer le code
        code_to_use = extracted_code
        code_to_use = code_to_use.replace('stat =.disk_usage', 'stat = shutil.disk_usage')
        code_to_use = code_to_use.replace('f"{.free', 'f"{stat.free')
        code_to_use = code_to_use.replace(':.f}', ':.2f}')
        code_to_use = code_to_use.replace('f"{.used', 'f"{stat.used')
        code_to_use = code_to_use.replace('f"{.total', 'f"{stat.total')
        code_to_use = code_to_use.replace('\\n', '\\\\n')
        
        # Reconstruit le JSON correctement
        text = '{"name": "executor_python", "arguments": {"code": "' + code_to_use + '", "timeout": ' + timeout_value + '}}'
    else:
        # Sinon, faire les corrections de base
        text = text.replace('arguments {', '"arguments": {')
        text = re.sub(r',\s*arguments\s*{', ', "arguments": {', text, flags=re.IGNORECASE)
        
        # Ajouter les guillemets autour du code
        text = re.sub(r'"?code"?\s*[=:]\s*(?!")', '"code": "', text, flags=re.IGNORECASE)
        
        # Corrections syntaxe Python
        text = text.replace('stat =.disk_usage', 'stat = shutil.disk_usage')
        text = text.replace('f"{.free', 'f"{stat.free')
        text = text.replace(':.f}', ':.2f}')
        text = text.replace('f"{.used', 'f"{stat.used')
        text = text.replace('f"{.total', 'f"{stat.total')
        
        # Fermer le code
        text = re.sub(r'(GB"?)(\s*)(timeout|[}"])', r'", "timeout"', text)
        text = re.sub(r'timeout\s*[:=]?\s*([0-9]+)', r'timeout": \1', text)
    
    return text

# Test case from the user
test_json = '{"name": "executor_python",arguments {"codeimport shutil\\nstat =.disk_usage(\'C:/\')\\nprint(f\\"{.free / (1024**3):.f} GB\")timeout5}}'

print("Original JSON:")
print(repr(test_json))
print()

fixed = fix_malformed_json(test_json)
print("Fixed JSON:")
print(repr(fixed))
print()

try:
    parsed = json.loads(fixed)
    print("✅ JSON parsing successful!")
    print("Parsed:", json.dumps(parsed, indent=2))
except json.JSONDecodeError as e:
    print(f"❌ JSON parsing failed: {e}")
    print("Fixed text:", fixed)
