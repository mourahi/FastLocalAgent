"""
Script de préchargement avancé pour le modèle Ollama.
Ce script précharge le modèle en mémoire pour réduire le temps de réponse au premier appel.
"""
import asyncio
import httpx
from app.core.config import Config

async def preload_model():
    """Précharge le modèle en mémoire avec plusieurs requêtes successives"""
    model_name = Config.get_model_name()
    base_url = Config.ollama_base_url

    print(f"🚀 Préchargement du modèle {model_name}...")

    # Vérifier si le modèle est disponible
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{base_url}/api/tags", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                models = [model["name"] for model in data.get("models", [])]

                if model_name not in models:
                    print(f"❌ Modèle {model_name} non trouvé dans Ollama")
                    return False
            else:
                print(f"❌ Erreur lors de la vérification des modèles: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Erreur lors de la connexion à Ollama: {e}")
            return False

    # Précharger le modèle avec plusieurs requêtes
    test_prompts = [
        "Hi",
        "Test",
        "Ready",
        "Hello",
        "Start"
    ]

    for i, prompt in enumerate(test_prompts, 1):
        try:
            print(f"  ⏳ Préchargement {i}/{len(test_prompts)}: '{prompt}'")

            payload = {
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 10,  # Réduit la longueur de réponse pour le préchargement
                    "temperature": 0.1   # Température basse pour des réponses prévisibles
                }
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{base_url}/api/generate",
                    json=payload,
                    timeout=60.0
                )

                if response.status_code == 200:
                    print(f"  ✅ Préchargement {i}/{len(test_prompts)} terminé")
                else:
                    print(f"  ⚠️ Erreur lors du préchargement {i}: {response.status_code}")

        except Exception as e:
            print(f"  ❌ Erreur lors du préchargement {i}: {e}")
            return False

    print(f"✅ Modèle {model_name} préchargé avec succès !")
    return True

if __name__ == "__main__":
    asyncio.run(preload_model())
