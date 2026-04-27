def math_tool(expression: str) -> str:
    """Exemple d'outil de calcul mathématique."""
    try:
        result = eval(expression)
        return f"Résultat : {result}"
    except Exception as e:
        return f"Erreur de calcul : {e}"