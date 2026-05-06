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
        streaming_mode = "buffer"  # Forcer le mode buffer pour réflexion complète
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
                    print(
                        f"⏱️ Temps avant le premier événement: {first_event_time:.2f}s"
                    )
                    print(
                        f"⏱️ Temps total depuis le début de la requête: {time.time() - start_time:.2f}s"
                    )

                if Config.stop_requested:
                    yield emit("\n[Processus arrêté par l'utilisateur]\n")
                    break

                kind = event["event"]

                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                        continue
                    content = chunk.content
                    if not content or not isinstance(content, str):
                        continue

                    raw_buffer += content

                    if streaming_mode is None:
                        # Vérifier si [PENSÉE] apparaît dans le buffer
                        if "[PENSÉE]" in raw_buffer:
                            streaming_mode = "buffer"
                        else:
                            # Décision dès le 1er caractère non-whitespace
                            stripped = raw_buffer.lstrip()
                            if stripped:
                                if stripped[0] in ("{", "`"):
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
                    code = (
                        tool_input.get("code", "")
                        if isinstance(tool_input, dict)
                        else ""
                    )
                    if code:
                        yield emit(f"\n<div class='code-block'>{code}</div>\n")

                elif kind == "on_tool_end":
                    tool_executed = True
                    output = event["data"].get("output", "")
                    if isinstance(output, str) and output.strip():
                        display_output = (
                            output[:500] + "..." if len(output) > 500 else output
                        )
                        yield emit(
                            f"\n**Résultat :**\n<div class='code-result'>{display_output}</div>\n"
                        )

        except Exception as e:
            print(f"Erreur streaming: {e}")
            yield emit(f"\n\nErreur serveur : {str(e)}")

        # Cas : streaming_mode jamais résolu (réponse vide / whitespace only)
        if streaming_mode is None and raw_buffer.strip():
            flushed = should_emit(raw_buffer)
            if flushed:
                yield emit(flushed)

        def extract_executor_python_call(buffer_text: str):
            """Recherche un appel JSON executor_python/executor_cmd/executor dans le texte et renvoie le préfixe et l'objet JSON."""

            def normalize_name(name_value: str):
                if not isinstance(name_value, str):
                    return None
                name_value = name_value.strip().lower()
                if name_value in ("executor_python", "executor"):
                    return "executor_python"
                if name_value in ("executor_cmd", "cmd", "executor_windows"):
                    return "executor_cmd"
                return None

            def fix_malformed_json(text):
                text = text.replace('"executor"', '"executor_python"')
                text = text.replace('"executor_cmd"', '"executor_cmd"')
                text = re.sub(
                    r",\s*arguments\s*{", ', "arguments": {', text, flags=re.IGNORECASE
                )
                text = re.sub(
                    r",\s*arguments\s*=\s*{",
                    ', "arguments": {',
                    text,
                    flags=re.IGNORECASE,
                )
                text = re.sub(
                    r'{(\s*)"code"(\s*)(?:[:,=])?\s*"?(?:import|import)',
                    r'{"\1code\1": "import',
                    text,
                )
                text = re.sub(r'{(\s*)"?code"?(\s*)(?!:)', r'{"code": ', text)
                text = re.sub(r'(.{3,5})"\)(\s*)(timeout)', r'\1"},"timeout"', text)
                text = re.sub(r'(.{3,5}")(\s*)(timeout)', r'\1,"timeout"', text)
                text = re.sub(r"timeout\s*[:=]?\s*5(?![\d])", '"timeout": 5', text)
                text = re.sub(r"timeout\s*[:=]?\s*2(?![\d])", '"timeout": 2', text)
                text = text.replace('""code":', '"code":')
                text = text.replace('"executor_python",', '"executor_python",')
                text = text.replace("stat =.disk_usage", "stat = shutil.disk_usage")
                text = text.replace('f"{.free', 'f"{stat.free')
                text = text.replace(":.f}", ":.2f}")
                text = text.replace('f"{.used', 'f"{stat.used')
                text = text.replace('f"{.total', 'f"{stat.total')
                return text

            start_idx = 0
            while True:
                start_idx = buffer_text.find("{", start_idx)
                if start_idx == -1:
                    break
                brace_count = 0
                for i, c in enumerate(buffer_text[start_idx:], start_idx):
                    if c == "{":
                        brace_count += 1
                    elif c == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            candidate = buffer_text[start_idx : i + 1]
                            try:
                                tool_data = json.loads(candidate)
                                normalized = normalize_name(tool_data.get("name"))
                                if normalized:
                                    tool_data["name"] = normalized
                                    prefix = buffer_text[:start_idx]
                                    return prefix, candidate, tool_data
                            except Exception:
                                fixed_candidate = fix_malformed_json(candidate)
                                try:
                                    tool_data = json.loads(fixed_candidate)
                                    normalized = normalize_name(tool_data.get("name"))
                                    if normalized:
                                        tool_data["name"] = normalized
                                        prefix = buffer_text[:start_idx]
                                        return prefix, fixed_candidate, tool_data
                                except Exception:
                                    pass
                            break
                start_idx += 1

            name_match = re.search(
                r'"?name"?\s*[:=]?\s*["\']?(executor_python|executor|executor_cmd|cmd|executor_windows)["\']?',
                buffer_text,
                re.IGNORECASE,
            )
            if name_match:
                prefix = buffer_text[: name_match.start()]
                code_match = re.search(
                    r'(?:code|command)(?:\s*[:=]\s*|)(.+?)(?=\s*timeout\s*[:=]?\s*[0-9]+|\s*["\']?\s*\}|$)',
                    buffer_text,
                    re.IGNORECASE | re.DOTALL,
                )
                timeout_match = re.search(
                    r"timeout\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)",
                    buffer_text,
                    re.IGNORECASE,
                )
                if code_match:
                    code = code_match.group(1).strip()
                    if code.endswith('"') or code.endswith("'"):
                        code = code[:-1].rstrip()
                    timeout = float(timeout_match.group(1)) if timeout_match else None
                    normalized = normalize_name(name_match.group(1))
                    tool_data = {"name": normalized, "arguments": {}}
                    arg_name = "code" if normalized == "executor_python" else "command"
                    tool_data["arguments"][arg_name] = code
                    if timeout is not None:
                        tool_data["arguments"]["timeout"] = timeout
                    return prefix, buffer_text, tool_data
            return None, None, None

        # Cas : mode buffer — détecter si appel outil ou texte normal
        if streaming_mode == "buffer" and not tool_executed:
            prefix, src, tool_data = extract_executor_python_call(raw_buffer)

            if src and tool_data:
                if prefix and prefix.strip():
                    thought = prefix.strip()
                    if not thought.startswith("[PENSÉE]"):
                        thought = "[PENSÉE] " + thought
                    yield emit(f"<div class=\"process\">{thought}</div>")

                tool_name = tool_data.get("name")
                command_text = tool_data.get("arguments", {}).get("code", "")
                payload_arg = "code"
                if tool_name == "executor_cmd":
                    command_text = tool_data.get("arguments", {}).get("command", "")
                    payload_arg = "command"
                timeout = tool_data.get("arguments", {}).get("timeout", None)
                if not command_text:
                    src_clean = re.sub(r"^```[a-zA-Z]*\n?", "", src).strip()
                    src_clean = re.sub(r"\n?```$", "", src_clean).strip()
                    m = re.search(
                        r'(?:code|command)["\s:]*(.+?)(?=\s*["\']?\s*timeout|\s*"?\s*}\s*}|$)',
                        src_clean,
                        re.DOTALL,
                    )
                    if m:
                        command_text = m.group(1).strip().rstrip("}\"'} \n\t")

                if command_text:
                    try:
                        if tool_name == "executor_cmd":
                            from ..core.tools.windows_command_tool import executor_cmd as _exec_tool
                            label = "commande"
                        else:
                            from ..core.tools.python_executor_tool import executor_python as _exec_tool
                            label = "code"

                        yield emit(
                            "<div class=\"process\">⚙️ **Exécution en cours...**\n<div class='code-block'>"
                            + command_text
                            + "</div>\n</div>"
                        )
                        invoke_payload = {payload_arg: command_text}
                        if timeout is not None:
                            invoke_payload["timeout"] = timeout
                        result = _exec_tool.invoke(invoke_payload)
                        yield emit(
                            "\n✅ **Résultat :**\n<div class='code-result'>"
                            + result
                            + "</div>\n"
                        )
                    except Exception as _e:
                        yield emit(
                            "<div class=\"process\">❌ Erreur détectée, tentative de correction...\nErreur: "
                            + str(_e)
                            + "</div>"
                        )
                        correction_input = {
                            "messages": [
                                (
                                    "human",
                                    f"Le {label} suivant a échoué avec l'erreur: {str(_e)}\nOriginal:\n{command_text}\n\nCorrige la commande ou le code en utilisant les imports nécessaires si besoin, puis exécute-le pour obtenir le résultat.",
                                )
                            ]
                        }
                        correction_config = {"configurable": {"thread_id": msg.session_id}}
                        corrected_executed = False
                        try:
                            async for correction_event in current_agent.astream_events(
                                correction_input, version="v2", config=correction_config
                            ):
                                if correction_event["event"] == "on_tool_start":
                                    tool_input = correction_event["data"].get("input", {})
                                    corrected_command = (
                                        tool_input.get("command", "")
                                        if isinstance(tool_input, dict)
                                        else ""
                                    )
                                    corrected_code = (
                                        tool_input.get("code", "")
                                        if isinstance(tool_input, dict)
                                        else ""
                                    )
                                    corrected_value = corrected_command or corrected_code
                                    if corrected_value:
                                        yield emit(
                                            "<div class=\"process\">🔧 Corrected input:\n<div class='code-block'>"
                                            + corrected_value
                                            + "</div>\n</div>"
                                        )
                                elif correction_event["event"] == "on_tool_end":
                                    corrected_result = correction_event["data"].get("output", "")
                                    if isinstance(corrected_result, str) and corrected_result.strip():
                                        display_result = (
                                            corrected_result[:500] + "..."
                                            if len(corrected_result) > 500
                                            else corrected_result
                                        )
                                        yield emit(
                                            "\n✅ **Résultat corrigé :**\n<div class='code-result'>"
                                            + display_result
                                            + "</div>\n"
                                        )
                                        corrected_executed = True
                        except Exception:
                            pass

                        if not corrected_executed:
                            yield emit(
                                "\n❌ **Erreur finale (correction échouée) :** " + str(_e) + "\n"
                            )
                else:
                    flushed = should_emit(raw_buffer)
                    if flushed:
                        yield emit(flushed)
            else:
                flushed = should_emit(raw_buffer)
                if flushed:
                    yield emit(flushed)

        # Filet de sécurité : rien n'a été émis du tout
        if not something_emitted:
            yield f"data: {json.dumps({'message': '[Aucune réponse du modèle]'})}\n\n"

        total_time = time.time() - start_time
        print(f"⏱️ Temps total de traitement: {total_time:.2f}s")
        print(f"⏱️ Nombre d'événements traités: {event_count}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/settings")
async def get_settings():
    """Retourne la configuration actuelle"""
    return Config.to_dict()


@router.get("/models")
async def get_models():
    """Récupère la liste des modèles disponibles depuis Ollama"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{Config.ollama_base_url}/api/tags", timeout=5.0
            )
            if response.status_code == 200:
                data = response.json()
                # Filtrer les modèles qui ne supportent pas les outils
                models_not_supporting_tools = ["gemma:7b", "phi3:mini"]
                models = [
                    model["name"]
                    for model in data.get("models", [])
                    if model["name"] not in models_not_supporting_tools
                ]
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
        with open(file_path, "w", encoding="utf-8") as f:
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
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        else:
            return {"messages": []}
    except Exception as e:
        return {"messages": [], "error": str(e)}
