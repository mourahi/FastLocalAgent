import json
from fastapi import APIRouter
from fastapi.responses import FileResponse, StreamingResponse
from ..schemas.chat import Message, SettingsUpdate
from ..core.agent import get_agent
from ..core.config import Config
from ..core.tools import get_active_tools

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
    if msg.model_name:
        Config.set_model_name(msg.model_name)
    
    if msg.tools_config:
        Config.set_enabled_tools(msg.tools_config)
    
    # Recréer l'agent avec la nouvelle configuration
    current_agent = get_agent(force_recreate=True)
    
    async def event_generator():
        config = {"configurable": {"thread_id": msg.session_id}}

        try:
            async for event in current_agent.astream_events(
                {"messages": [("human", msg.text)]},
                version="v2",
                config=config,
            ):
                kind = event["event"]

                if kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
                        yield f"data: {json.dumps({'chunk': content})}\n\n"

                elif kind == "on_tool_start":
                    tool_name = event.get("name", "outil")
                    message = f"\n→ Utilisation de l'outil : {tool_name}\n"
                    yield f"data: {json.dumps({'chunk': message})}\n\n"

                elif kind == "on_tool_end":
                    output = event["data"].get("output", "")
                    if isinstance(output, str) and output.strip():
                        short = output[:300] + "..." if len(output) > 300 else output
                        message = f"\nRésultat :\n{short}\n"
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