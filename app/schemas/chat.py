from pydantic import BaseModel
from typing import Optional, Dict

class Message(BaseModel):
    text: str
    session_id: str = "default"
    model_name: Optional[str] = None
    tools_config: Optional[Dict[str, bool]] = None


class SettingsUpdate(BaseModel):
    """Schéma pour la mise à jour des paramètres"""
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    enabled_tools: Optional[Dict[str, bool]] = None