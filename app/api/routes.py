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
    # Servir le fichier index.html depuis le dossier static
    static_dir = Path(__file__).parent.parent.parent / "static"
    index_path = static_dir / "index.html"
    return FileResponse(index_path, media_type="text/html")


@router.post("/chat")
async def chat(msg: Message):
    """
    Endpoint de chat avec support du streaming.
    Permet de surcharger le modèle et les outils pour cette requête.
    """
    import time
    start_time = time.time()

    # Mettre à jour la configuration si fournie dans le message
    config_changed = False
    if msg.model_name and msg.model_name != Config.get_model_name():
        Config.set_model_name(msg.model_name)
        config_changed = True

    if msg.tools_config and msg.tools_config != Config.get_enabled_tools():
        Config.set_enabled_tools(msg.tools_config)
        config_changed = True

    # Recréer l'agent uniquement si la configuration a changé
    agent_start_time = time.time()
    current_agent = get_agent(force_recreate=config_changed)
    agent_time = time.time() - agent_start_time
    print(f"⏱️ Temps de récupération/création de l'agent: {agent_time:.2f}s")

    async def event_generator():
        config = {"configurable": {"thread_id": msg.session_id}}
        stream_start_time = time.time()
        event_count = 0
        first_event_time = None

        emitted_texts = set()
        chain_stream_seen = False
        emitted_text = ""
        last_emitted_chunk = ""

        def normalize_content(value):
            return str(value).replace("\r", "")

        def should_emit(content):
            nonlocal emitted_text, last_emitted_chunk
            content = normalize_content(content)
            if not content.strip():
                return None
            if content == last_emitted_chunk:
                return None
            if content in emitted_texts:
                return None
            if emitted_text.endswith(content):
                return None
            if len(content) > 40 and content in emitted_text:
                return None
            
            emitted_texts.add(content)
            emitted_text += content
            last_emitted_chunk = content
            return content

        try:
            async for event in current_agent.astream_events(
                {"messages": [("human", msg.text)]},
                version="v2",
                config=config,
            ):
                event_count += 1
                if first_event_time is None:
                    first_event_time = time.time() - stream_start_time
                    print(f"⏱️ Temps avant le premier événement: {first_event_time:.2f}s")
                    print(f"⏱️ Temps total depuis le début de la requête: {time.time() - start_time:.2f}s")
                # Check if a stop has been requested
                if Config.stop_requested:
                    stop_msg = "\n[Processus arrêté par l'utilisateur]\n"
                    yield f"data: {json.dumps({'message': stop_msg})}\n\n"
                    continue
                kind = event["event"]

                if kind == "on_chain_stream":
                    chain_stream_seen = True
                    chunk = event["data"].get("chunk", {})
                    messages = []
                    if isinstance(chunk, dict):
                        messages = chunk.get("messages", [])
                    elif hasattr(chunk, "messages"):
                        messages = chunk.messages
                    for message in messages:
                        content = getattr(message, "content", None) or (message.get("content") if isinstance(message, dict) else None)
                        content = should_emit(content)
                        if content:
                            yield f"data: {json.dumps({'message': content})}\n\n"

                elif kind == "on_chain_end" and not chain_stream_seen:
                    output = event["data"].get("output")
                    if isinstance(output, dict) and "messages" in output:
                        for message in output["messages"]:
                            content = getattr(message, "content", None) or (message.get("content") if isinstance(message, dict) else None)
                            # Filter tool calls
                            is_tool_call = False
                            stripped = content.strip() if content else ""
                            if stripped.startswith("Action:") or "Action:" in stripped:
                                is_tool_call = True
                            elif stripped.startswith("{") and stripped.endswith("}"):
                                try:
                                    parsed = json.loads(stripped)
                                    if isinstance(parsed, dict) and ("name" in parsed or "arguments" in parsed):
                                        is_tool_call = True
                                except:
                                    pass
                            
                            if not is_tool_call:
                                content = should_emit(content)
                                if content:
                                    yield f"data: {json.dumps({'message': content})}\n\n"

                elif kind == "on_chat_model_stream" and not chain_stream_seen:
                    content = event["data"]["chunk"].content
                    if content and isinstance(content, str):
                        # Skip tool calls - don't emit them
                        stripped = content.strip()
                        is_tool_output = False
                        
                        # Check for tool call patterns
                        if "Action:" in content or "Action Input:" in content or \
                           (stripped.startswith("{") and "name" in content):
                            is_tool_output = True
                        
                        if not is_tool_output:
                            content = should_emit(content)
                            if content:
                                yield f"data: {json.dumps({'message': content})}\n\n"

                elif kind == "on_chat_model_end" and not chain_stream_seen:
                    output = event["data"].get("output")
                    content = getattr(output, "content", None) or (output.get("content") if isinstance(output, dict) else None)
                    
                    # Check if the content contains a tool call
                    tool_result = None
                    is_tool_call = False
                    
                    if content:
                        # Check if this is a tool call
                        stripped = content.strip()
                        print(f"DEBUG on_chat_model_end: stripped={repr(stripped[:100])}")
                        if stripped.startswith("Action:") and "Action Input:" in stripped:
                            is_tool_call = True
                            print(f"DEBUG: Detected ReAct tool call")
                        elif stripped.startswith("{") and stripped.endswith("}"):
                            try:
                                parsed = json.loads(stripped)
                                if isinstance(parsed, dict) and ("name" in parsed or "arguments" in parsed):
                                    is_tool_call = True
                                    print(f"DEBUG: Detected JSON tool call")
                            except:
                                pass
                        
                        print(f"DEBUG: is_tool_call={is_tool_call}")
                        
                        # If it's a tool call, execute it
                        if is_tool_call:
                            try:
                                # Check for ReAct format
                                if "Action:" in content and "Action Input:" in content:
                                    action_part = content.split("Action:")[1].split("Action Input:")[0].strip()
                                    input_part = content.split("Action Input:", 1)[1].strip()
                                    
                                    tool_name = action_part.strip()
                                    tool_args = input_part.strip()
                                    
                                    print(f"DEBUG: tool_name={tool_name}, tool_args={repr(tool_args[:100])}")
                                    
                                    if tool_name == "executor_python" and tool_args.startswith("{") and tool_args.endswith("}"):
                                        args_dict = json.loads(tool_args)
                                        code = args_dict.get("code", "")
                                        
                                        if code:
                                            from ..core.tools.python_executor_tool import executor_python
                                            result = executor_python.invoke({"code": code})
                                            tool_result = f"\n→ Exécution de l'outil : {tool_name}\n\nRésultat :\n{result}\n"
                                            print(f"DEBUG: Tool executed, result={repr(tool_result[:100])}")
                            except Exception as e:
                                print(f"Erreur lors de l'exécution de l'outil dans on_chat_model_end: {e}")
                        else:
                            # Not a tool call, emit the content
                            print(f"DEBUG: Not a tool call, emitting content")
                            content = should_emit(content)
                            if content:
                                yield f"data: {json.dumps({'message': content})}\n\n"
                    
                    if tool_result:
                        # Emit the tool result
                        print(f"DEBUG: Emitting tool result")
                        yield f"data: {json.dumps({'message': tool_result})}\n\n"
                    
                    # Clear the buffer since we're done with this message
                    stream_buffer = ""

                elif kind == "on_tool_start":
                    tool_name = event.get("name", "outil")
                    message = f"\n→ Utilisation de l'outil : {tool_name}\n"
                    message = should_emit(message)
                    if message:
                        yield f"data: {json.dumps({'message': message})}\n\n"

                elif kind == "on_tool_end":
                    output = event["data"].get("output", "")
                    if isinstance(output, str) and output.strip():
                        message = f"\nRésultat :\n{output}\n"
                        message = should_emit(message)
                        if message:
                            yield f"data: {json.dumps({'message': message})}\n\n"
                        # Ajouter le résultat à l'historique des messages pour que le modèle puisse y répondre

        except Exception as e:
            print(f"Erreur streaming: {e}")
            error_message = f"\n\nErreur serveur : {str(e)}"
            yield f"data: {json.dumps({'message': error_message})}\n\n"

        total_time = time.time() - start_time
        print(f"⏱️ Temps total de traitement: {total_time:.2f}s")
        print(f"⏱️ Nombre d'événements traités: {event_count}")

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
        settings: Nouveaux paramètres (model_name, temperature, enabled_tools, performance options)

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
    
    if settings.enable_model_preloading is not None:
        Config.set_enable_model_preloading(settings.enable_model_preloading)
    
    if settings.enable_model_check is not None:
        Config.set_enable_model_check(settings.enable_model_check)

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
