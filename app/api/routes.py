import json
import re
from fastapi import APIRouter
from fastapi.responses import FileResponse, StreamingResponse
from ..schemas.chat import Message, SettingsUpdate
from ..core.agent import get_agent
from ..core.config import Config
from ..core.tools import get_active_tools
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
        Config.clear_stop()
        emitted_texts = set()
        emitted_text = ""
        last_emitted_chunk = ""
        raw_buffer = ""
        streaming_mode = None   # None=indécis, "stream"=direct, "buffer"=appel outil potentiel
        tool_executed = False
        something_emitted = False

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

        def emit(message):
            nonlocal something_emitted
            something_emitted = True
            return f"data: {json.dumps({'message': message})}\n\n"

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

                if Config.stop_requested:
                    yield emit("\n[Processus arrêté par l'utilisateur]\n")
                    break

                kind = event["event"]

                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, 'tool_call_chunks') and chunk.tool_call_chunks:
                        continue
                    content = chunk.content
                    if not content or not isinstance(content, str):
                        continue

                    raw_buffer += content

                    if streaming_mode is None:
                        # Décision dès le 1er caractère non-whitespace
                        stripped = raw_buffer.lstrip()
                        if stripped:
                            if stripped[0] in ('{', '`'):
                                streaming_mode = "buffer"
                            else:
                                streaming_mode = "stream"
                                flushed = should_emit(raw_buffer)
                                if flushed:
                                    yield emit(flushed)
                    elif streaming_mode == "stream":
                        content = should_emit(content)
                        if content:
                            yield emit(content)
                    # "buffer" : on accumule sans émettre

                elif kind == "on_tool_start":
                    tool_input = event["data"].get("input", {})
                    code = tool_input.get("code", "") if isinstance(tool_input, dict) else ""
                    if code:
                        yield emit(f"\n```python\n{code}\n```\n")

                elif kind == "on_tool_end":
                    tool_executed = True
                    output = event["data"].get("output", "")
                    if isinstance(output, str) and output.strip():
                        display_output = output[:500] + "..." if len(output) > 500 else output
                        yield emit(f"\n**Résultat :**\n```\n{display_output}\n```\n")

        except Exception as e:
            print(f"Erreur streaming: {e}")
            yield emit(f"\n\nErreur serveur : {str(e)}")

        # Cas : streaming_mode jamais résolu (réponse vide / whitespace only)
        if streaming_mode is None and raw_buffer.strip():
            flushed = should_emit(raw_buffer)
            if flushed:
                yield emit(flushed)

        # Cas : mode buffer — détecter si appel outil ou texte normal
        if streaming_mode == "buffer" and not tool_executed:
            src = raw_buffer.strip()
            src = re.sub(r'^```[a-zA-Z]*\n?', '', src).strip()
            src = re.sub(r'\n?```$', '', src).strip()

            is_json_tool_call = src.startswith('{') and "executor_python" in src and "code" in src

            if is_json_tool_call:
                code = ""
                try:
                    start_idx = src.find('{')
                    brace_count, end_idx = 0, -1
                    for i, c in enumerate(src[start_idx:], start_idx):
                        if c == '{':
                            brace_count += 1
                        elif c == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_idx = i + 1
                                break
                    if end_idx > start_idx:
                        tool_data = json.loads(src[start_idx:end_idx])
                        if tool_data.get("name") == "executor_python":
                            code = tool_data.get("arguments", {}).get("code", "")
                except Exception:
                    pass

                if not code:
                    m = re.search(r'code["\s:]*(.+?)(?=\s*["\']?\s*timeout|\s*"?\s*}\s*}|$)', src, re.DOTALL)
                    if m:
                        code = m.group(1).strip().rstrip('}"\'} \n\t')

                if code:
                    try:
                        from ..core.tools.python_executor_tool import executor_python as _exec_tool
                        yield emit("```python\n" + code + "\n```\n")
                        result = _exec_tool.invoke({"code": code})
                        yield emit("\n**Résultat :**\n```\n" + result + "\n```\n")
                    except Exception as _e:
                        yield emit("\nErreur exécution : " + str(_e) + "\n")
                else:
                    # Buffer mais pas un appel outil — émettre comme texte
                    flushed = should_emit(raw_buffer)
                    if flushed:
                        yield emit(flushed)
            else:
                # Buffer mais pas un appel outil — émettre comme texte
                flushed = should_emit(raw_buffer)
                if flushed:
                    yield emit(flushed)

        # Filet de sécurité : rien n'a été émis du tout
        if not something_emitted:
            yield f"data: {json.dumps({'message': '[Aucune réponse du modèle]'})}\n\n"

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
