# FastAgent - SKILLS.MD

## 🎯 Vue d'Ensemble

**FastAgent** est un agent conversationnel IA local qui tourne avec **Ollama** et **Qwen2.5-3B**. Il fournit une interface chat web moderne pour interagir avec un agent LangGraph ReAct équipé d'outils personnalisés.

### Stack Technique
- **Backend** : FastAPI + Uvicorn
- **Agent Framework** : LangGraph (ReAct Agent)
- **LLM** : Qwen2.5-3B via Ollama
- **Frontend** : HTML + Tailwind CSS + JavaScript
- **Streaming** : Server-Sent Events (SSE)

---

## 📁 Structure du Projet

```
FastAgent/
├── run.py                          # Lanceur : uvicorn.run("app.main:app", port=8000)
├── app/
│   ├── main.py                     # App FastAPI + CORS + Static Files
│   ├── api/
│   │   └── routes.py               # Routes: GET /, POST /chat (streaming)
│   ├── core/
│   │   ├── agent.py                # create_react_agent() avec mémoire
│   │   ├── llm.py                  # ChatOllama(model="qwen2.5:3b")
│   │   ├── prompt.py               # SYSTEM_PROMPT (identité agent)
│   │   └── tools/
│   │       ├── __init__.py         # TOOLS = [search_tool, math_tool, lister_fichiers]
│   │       ├── lister_fichiers_tool.py
│   │       ├── math_tool.py
│   │       └── search_tool.py
│   └── schemas/
│       └── chat.py                 # Message(text: str, session_id: str)
├── static/
│   ├── index.html                  # UI Chat + Tailwind + Marked.js
│   └── css/
│       └── style.css               # Styles bulles de chat
└── images/                         # Assets statiques
```

---

## 🔧 Composants Principaux

### 1. Point d'Entrée (`run.py`)
```python
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
```

**Usage** : `python run.py`

---

### 2. Configuration FastAPI (`app/main.py`)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .api.routes import router

app = FastAPI(title="Agent Local")

# CORS - Toutes origines autorisées
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")

# Routes
app.include_router(router)
```

---

### 3. Agent LangGraph (`app/core/agent.py`)

```python
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from .llm import get_llm
from .tools import get_active_tools
from .prompt import SYSTEM_PROMPT
from .config import Config

memory = MemorySaver()

# Cache pour éviter de recréer l'agent
_agent_cache = None
_config_cache = None

def get_agent(force_recreate: bool = False):
    """
    Crée et retourne l'agent IA avec caching.
    
    Args:
        force_recreate: Force la recréation si la config a changé
    """
    global _agent_cache, _config_cache
    
    current_config = Config.to_dict()
    
    if _agent_cache and not force_recreate and _config_cache == current_config:
        return _agent_cache
    
    llm = get_llm()
    active_tools = get_active_tools()
    
    _agent_cache = create_react_agent(
        model=llm,
        tools=active_tools,
        checkpointer=memory,
        prompt=SYSTEM_PROMPT
    )
    
    _config_cache = current_config
    return _agent_cache
```

**Points Clés** :
- Utilise `create_react_agent` de LangGraph
- Mémoire persistante avec `MemorySaver`
- Thread ID pour séparer les conversations
- **Cache intelligent** : Recrée l'agent seulement si la configuration change
- **Support dynamique** : Permet de changer de modèle et d'outils à la volée

---

### 5. Configuration LLM (`app/core/llm.py`)

```python
from langchain_ollama import ChatOllama
from .config import Config

def get_llm(model_name: str = None, temperature: float = None):
    """
    Retourne le modèle LLM configuré.
    
    Args:
        model_name: Nom du modèle (optionnel, utilise Config sinon)
        temperature: Température (optionnel, utilise Config sinon)
    """
    model = model_name or Config.get_model_name()
    temp = temperature if temperature is not None else Config.get_temperature()
    
    return ChatOllama(
        model=model,
        temperature=temp,
        streaming=True
    )
```

**Configuration** :
- Modèle : Dynamique via `Config` (défaut: `qwen2.5:3b`)
- Température : Dynamique via `Config` (défaut: 0.1)
- Streaming activé
- **Supporte le changement dynamique de modèle**

---

### 5. Prompt Système (`app/core/prompt.py`)

```python
SYSTEM_PROMPT = """Tu es un assistant local simple, utile et direct nommé "Agent Local".

Tu n'es PAS Claude, tu n'es pas fait par Anthropic. 
Tu es un petit modèle Qwen2.5-3B qui tourne en local avec Ollama.

Règles importantes :
- Réponds toujours en français.
- Sois court, clair et direct.
- Si l'utilisateur demande de lister des fichiers ou voir le contenu d'un dossier, utilise l'outil "lister_fichiers".
- Sinon, réponds directement sans outil.
- Ne dis jamais que tu es Claude ou que tu es créé par Anthropic."""
```

---

### 6. Configuration (`app/core/config.py`)

```python
class Config:
    """Configuration globale de l'application"""
    
    model_name: str = "qwen2.5:3b"
    temperature: float = 0.1
    enabled_tools: dict = {
        "lister": True,
        "math": True,
        "search": True
    }
    
    @classmethod
    def get_model_name(cls) -> str: ...
    
    @classmethod
    def set_model_name(cls, model: str) -> None: ...
    
    @classmethod
    def get_enabled_tools(cls) -> dict: ...
    
    @classmethod
    def set_enabled_tools(cls, tools: dict) -> None: ...
    
    @classmethod
    def is_tool_enabled(cls, tool_name: str) -> bool: ...
    
    @classmethod
    def to_dict(cls) -> dict: ...
```

**Usage** : Permet de modifier dynamiquement le modèle et les outils activés.

---

### 7. Outils (`app/core/tools/`)

#### `lister_fichiers_tool.py`
```python
import os
from langchain_core.tools import tool

@tool
def lister_fichiers(path: str) -> str:
    """Liste les fichiers d'un répertoire donné (maximum 20 fichiers)."""
    try:
        abs_path = os.path.abspath(path)
        files = os.listdir(abs_path)
        return "\n".join(files[:20])
    except Exception as e:
        return f"Erreur lors de l'accès au dossier : {str(e)}"
```

#### `math_tool.py`
```python
def math_tool(expression: str) -> str:
    """Exemple d'outil de calcul mathématique."""
    try:
        result = eval(expression)
        return f"Résultat : {result}"
    except Exception as e:
        return f"Erreur de calcul : {e}"
```

#### `search_tool.py`
```python
def search_tool(query: str) -> str:
    """Exemple d'outil de recherche simple."""
    return f"Résultat de la recherche pour : {query}"
```

#### `__init__.py`
```python
from .search_tool import search_tool
from .math_tool import math_tool
from .lister_fichiers_tool import lister_fichiers
from ..config import Config

def get_active_tools():
    """Retourne la liste des outils activés selon la configuration."""
    tools_map = {
        "lister": lister_fichiers,
        "math": math_tool,
        "search": search_tool
    }
    
    active_tools = []
    enabled = Config.get_enabled_tools()
    
    for tool_name, tool_func in tools_map.items():
        if enabled.get(tool_name, False):
            active_tools.append(tool_func)
    
    return active_tools

# Outils actifs par défaut
TOOLS = get_active_tools()
```

**Fonctionnalité clé** : Filtrage dynamique des outils selon la configuration utilisateur.

---

### 4. Configuration LLM (`app/core/llm.py`)

```python
from fastapi import APIRouter
from fastapi.responses import FileResponse, StreamingResponse
from ..schemas.chat import Message
from ..core.agent import get_agent
import json

router = APIRouter()
agent = get_agent()  # Singleton

@router.get("/")
async def home():
    return FileResponse("static/index.html")

@router.post("/chat")
async def chat(msg: Message):
    async def event_generator():
        config = {"configurable": {"thread_id": msg.session_id}}
        
        async for event in agent.astream_events(
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
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**Événements streamés** :
- `on_chat_model_stream` : Contenu du LLM
- `on_tool_start` : Début d'exécution d'outil
- `on_tool_end` : Résultat de l'outil

**Nouveaux endpoints** :
- `GET /settings` : Récupère la configuration actuelle
- `POST /settings` : Met à jour la configuration globale (modèle, température, outils)

---

### 8. Schémas Pydantic (`app/schemas/chat.py`)

```python
from pydantic import BaseModel
from typing import Optional, Dict

class Message(BaseModel):
    text: str
    session_id: str = "default"
    model_name: Optional[str] = None        # Surcharge du modèle pour cette requête
    tools_config: Optional[Dict[str, bool]] = None  # Configuration des outils

class SettingsUpdate(BaseModel):
    """Schéma pour la mise à jour des paramètres"""
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    enabled_tools: Optional[Dict[str, bool]] = None
```

**Fonctionnalité** : Permet de transmettre les préférences utilisateur (modèle, outils) depuis le frontend.

---

### 9. Interface Utilisateur (`static/index.html`)

**Fonctionnalités** :
- Chat en temps réel avec streaming SSE
- Support Markdown avec Marked.js
- Tailwind CSS pour le styling
- Gestion de session avec thread_id
- Animations CSS (fade-in)
- **Paramètres utilisateur** avec modale :
  - Sélection du modèle LLM (Qwen2.5, Llama, Mistral, Gemma)
  - Thème light/dark avec persistance localStorage
  - Activation/désactivation des outils (lister, math, search)
- Notifications de confirmation
- Support Ctrl+Enter pour envoyer

**Structure** :
```html
<header>
    Logo + Status "En ligne • Ollama 3B"
    Bouton "Paramètres" → Ouvre modale
</header>
<main id="chat">Bulles de messages</main>
<footer>
    <input id="input" placeholder="Posez votre question...">
    <button onclick="send()">Envoyer</button>
</footer>

<!-- Modale Paramètres -->
<div id="settings-modal">
    - Sélection du modèle (8 options)
    - Thème (light/dark)
    - Toggle outils (3 checkboxes)
    - Boutons Annuler/Enregistrer
</div>
```

**JavaScript** :
- `send()` : Envoie POST /chat avec EventSource
- `createMessageBubble()` : Crée les bulles utilisateur/IA
- `toggleSettings()` : Ouvre/ferme la modale
- `setTheme()` : Applique le thème light/dark
- `saveSettings()` : Sauvegarde dans localStorage
- `loadSettings()` : Charge les paramètres au démarrage
- Parse le streaming SSE et affiche chunk par chunk

**Paramètres persistants** (localStorage) :
```javascript
{
    model: 'qwen2.5:3b',
    theme: 'light' | 'dark',
    tools: {
        lister: true,
        math: true,
        search: true
    }
}
```

---

### 10. Styles CSS (`static/css/style.css`)

```css
.chat-container {
    height: calc(100vh - 180px);
    padding-bottom: 90px;
}

.message-bubble {
    max-width: 85%;
    border-radius: 20px;
    padding: 14px 18px;
}

.user-bubble {
    background: linear-gradient(135deg, #4f46e5, #6366f1);
    color: white;
}

.ai-bubble {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
}

/* Thème sombre - body.bg-gray-900 */
body.bg-gray-900 header {
    background-color: #1f2937;
    border-color: #374151;
}

body.bg-gray-900 .ai-bubble {
    background: #1f2937;
    border-color: #374151;
    color: #e5e7eb;
}

body.bg-gray-900 footer {
    background-color: #1f2937;
    border-color: #374151;
}

body.bg-gray-900 #input {
    background-color: #374151;
    border-color: #4b5563;
    color: #f9fafb;
}
```

**Support complet des deux thèmes** avec des sélecteurs CSS basés sur la classe `body.bg-gray-900` pour le thème sombre.

---

## 🔄 Flux de Données

```
Utilisateur → Input UI
    ↓
POST /chat (text + session_id)
    ↓
routes.py → agent.astream_events()
    ↓
LangGraph Agent (ReAct)
    ├─→ LLM (qwen2.5:3b)
    └─→ Tools (si nécessaire)
    ↓
Streaming SSE (chunks JSON)
    ↓
EventSource UI → Affichage temps réel
```

---

## 🚀 Commandes d'Exécution

### Démarrer le serveur
```bash
python run.py
```

### Accéder à l'interface
```
http://127.0.0.1:8000
```

### Prérequis
```bash
# Installer Ollama
# Télécharger le modèle
ollama pull qwen2.5:3b

# Installer les dépendances Python
pip install fastapi uvicorn langgraph langchain-ollama pydantic
```

---

## 🛠️ Bonnes Pratiques et Conventions

### Architecture
- **Modulaire** : Séparation claire core/api/tools/schemas
- **Singleton** : L'agent est créé une fois au démarrage
- **Streaming** : Toutes les réponses sont streamées
- **Mémoire** : Conversations persistantes par thread_id

### Code Style
- **Typage** : Utilise Pydantic pour la validation
- **Async** : Toutes les routes sont async
- **Français** : L'agent répond toujours en français
- **Court** : Réponses directes et concises

### Sécurité
- **CORS** : Ouvert en local (à restreindre en prod)
- **eval()** : math_tool utilise eval (dangerous, à améliorer)
- **Local** : Tourne uniquement sur 127.0.0.1

---

## 📦 Dépendances Principales

```
fastapi
uvicorn
langgraph
langchain-ollama
pydantic
```

---

## 🎯 Extensions Possibles

### Ajouter un Nouvel Outil
1. Créer `app/core/tools/nouvel_outil.py`
2. Décorer avec `@tool` de langchain_core.tools
3. Exporter dans `app/core/tools/__init__.py`
4. Redémarrer le serveur

### Améliorer le Frontend
- ✅ **Thèmes sombre/clair** - Implémenté
- ✅ **Sélection du modèle** - Implémenté (8 modèles disponibles)
- ✅ **Gestion des outils** - Activation/désactivation implémentée
- Ajouter historique des conversations
- Support des pièces jointes
- Export des conversations

### Améliorer le Backend
- Base de données pour l'historique
- Authentification
- Rate limiting
- Logs détaillés

---

## ⚠️ Limitations Connues

1. **Modèle 3B** : Capacités limitées vs modèles plus gros
2. **eval()** : Risque de sécurité dans math_tool
3. **CORS ouvert** : À restreindre en production
4. **Pas de BDD** : Mémoire uniquement en RAM
5. **search_tool** : Placeholder, pas implémenté

---

## 📝 Résumé pour IA

**FastAgent** = FastAPI + LangGraph ReAct Agent + Ollama Qwen2.5-3B + UI Tailwind

**Flow** : User → POST /chat → LangGraph → LLM + Tools → SSE Stream → UI

**Outils** : lister_fichiers, math_tool, search_tool

**Mémoire** : MemorySaver avec thread_id par session

**Langue** : Français uniquement

**Architecture** : Modulaire, async, streaming

---

*Document généré pour aider les modèles IA à comprendre rapidement le projet FastAgent.*
