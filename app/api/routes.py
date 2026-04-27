import json
from fastapi import APIRouter
from fastapi.responses import FileResponse, StreamingResponse
from ..schemas.chat import Message, SettingsUpdate
from ..core.agent import get_agent
from ..core.config import Config
from ..core.tools import get_active_tools
import os
import httpx
from pathlib import Path

router = APIRouter()

# Agent initial
agent = get_agent()


@router.get("/")
async def home():
    return FileResponse("static/index.html")


@router.post("/chat")
async def chat(msg: Message):
    """
    Endpoint de chat avec support du streaming.
    Permet de surcharger le modèle et les outils pour cette requête.
    """
    # Mettre à jour la configuration si fournie dans le message
    config_changed = False
    if msg.model_name and msg.model_name != Config.get_model_name():
        Config.set_model_name(msg.model_name)
        config_changed = True

    if msg.tools_config and msg.tools_config != Config.get_enabled_tools():
        Config.set_enabled_tools(msg.tools_config)
        config_changed = True

    # Recréer l'agent uniquement si la configuration a changé
    current_agent = get_agent(force_recreate=config_changed)

    async def event_generator():
        config = {"configurable": {"thread_id": msg.session_id}}

        try:
            async for event in current_agent.astream_events(
                {"messages": [("human", msg.text)]},
                version="v2",
                config=config,
            ):
                # Check if a stop has been requested
                if Config.stop_requested:
                    # Reset flag but continue streaming so new messages can be processed
                    Config.clear_stop()
                    stop_msg = "\n[Processus arrêté par l'utilisateur]\n"
                    yield f"data: {json.dumps({'chunk': stop_msg})}\n\n"
                    # Continue to listen for new messages instead of ending the stream
                kind = event["event"]

                if kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
                        # Filtrer tous les messages JSON et les appels d'outils
                        try:
                            # Vérifier si le contenu contient des motifs d'appel d'outil
                            if '"name"' in content and '"arguments"' in content:
                                # Ignorer les messages JSON d'appel d'outil
                                continue
                            # Essayer de parser comme JSON
                            content_dict = json.loads(content)
                            if isinstance(content_dict, dict):
                                # Ignorer tous les dictionnaires JSON (appels d'outils)
                                continue
                        except (json.JSONDecodeError, TypeError):
                            # Ce n'est pas du JSON valide, on l'affiche normalement
                            pass
                        yield f"data: {json.dumps({'chunk': content})}\n\n"

                elif kind == "on_tool_start":
                    tool_name = event.get("name", "outil")
                    message = f"\n→ Utilisation de l'outil : {tool_name}\n"
                    yield f"data: {json.dumps({'chunk': message})}\n\n"

                elif kind == "on_tool_end":
                    output = event["data"].get("output", "")
                    if isinstance(output, str) and output.strip():
                        # Afficher le résultat directement sans troncation excessive
                        message = f"\nRésultat :\n{output}\n"
                        yield f"data: {json.dumps({'chunk': message})}\n\n"

        except Exception as e:
            print(f"Erreur streaming: {e}")
            error_message = f"\n\nErreur serveur : {str(e)}"
            yield f"data: {json.dumps({'chunk': error_message})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@router.get("/settings")
async def get_settings():
    """Retourne la configuration actuelle"""
    return Config.to_dict()


@router.get("/models")
async def get_models():
    """Récupère la liste des modèles disponibles depuis Ollama"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{Config.ollama_base_url}/api/tags", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                # Filtrer les modèles qui ne supportent pas les outils
                models_not_supporting_tools = ["gemma:7b", "phi3:mini"]
                models = [model["name"] for model in data.get("models", []) 
                         if model["name"] not in models_not_supporting_tools]
                return {"models": models}
            else:
                return {"models": [], "error": f"Erreur Ollama: {response.status_code}"}
    except Exception as e:
        return {"models": [], "error": str(e)}


@router.post("/settings")
async def update_settings(settings: SettingsUpdate):
    """
    Met à jour la configuration globale.

    Args:
        settings: Nouveaux paramètres (model_name, temperature, enabled_tools)

    Returns:
        dict: Configuration mise à jour
    """
    global agent

    if settings.model_name:
        Config.set_model_name(settings.model_name)

    if settings.temperature is not None:
        Config.set_temperature(settings.temperature)

    if settings.enabled_tools:
        Config.set_enabled_tools(settings.enabled_tools)

    # Recréer l'agent avec la nouvelle configuration
    agent = get_agent(force_recreate=True)

    return Config.to_dict()

# Endpoint to request stopping the current model processing
@router.post("/stop")
async def stop_processing():
    """Signal the backend to stop the ongoing streaming response."""
    Config.request_stop()
    return {"status": "stop_requested"}

# Endpoint to clear the conversation history (reset thread)
@router.post("/clear")
async def clear_conversation():
    """Reset the thread ID by returning a new empty configuration.
    The frontend should create a new session_id for subsequent chats.
    """
    # No persistent storage of history, just acknowledge
    return {"status": "conversation_cleared"}


# Endpoints pour sauvegarder/charger la conversation
CONVERSATIONS_DIR = Path("conversations")
CONVERSATIONS_DIR.mkdir(exist_ok=True)


@router.post("/conversation/save")
async def save_conversation(data: dict):
    """
    Sauvegarde la conversation sur le serveur.

    Args:
        data: {
            "session_id": "default",
            "messages": [{"isUser": bool, "content": str}, ...]
        }

    Returns:
        dict: Statut de la sauvegarde
    """
    try:
        session_id = data.get("session_id", "default")
        messages = data.get("messages", [])

        # Créer le fichier de conversation
        file_path = CONVERSATIONS_DIR / f"{session_id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({"messages": messages}, f, ensure_ascii=False, indent=2)

        return {"status": "saved", "session_id": session_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/conversation/load")
async def load_conversation(session_id: str = "default"):
    """
    Charge la conversation depuis le serveur.

    Args:
        session_id: ID de la session

    Returns:
        dict: {
            "messages": [{"isUser": bool, "content": str}, ...]
        }
    """
    try:
        file_path = CONVERSATIONS_DIR / f"{session_id}.json"

        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        else:
            return {"messages": []}
    except Exception as e:
        return {"messages": [], "error": str(e)}
