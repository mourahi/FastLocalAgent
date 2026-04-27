from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Literal

class Message(BaseModel):
    text: str = Field(..., min_length=1, max_length=4096, description="Message de l'utilisateur")
    session_id: str = Field(default="default", min_length=1, max_length=100, description="Identifiant de session")
    model_name: Optional[str] = Field(default=None, max_length=100, description="Nom du modèle à utiliser")
    tools_config: Optional[Dict[str, bool]] = Field(default=None, description="Configuration des outils activés")
    
    @field_validator('text')
    @classmethod
    def text_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Le message ne peut pas être vide')
        return v.strip()


class SettingsUpdate(BaseModel):
    """Schéma pour la mise à jour des paramètres"""
    model_name: Optional[str] = Field(default=None, max_length=100, description="Nom du modèle à utiliser")
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0, description="Température du modèle (0.0-2.0)")
    enabled_tools: Optional[Dict[str, bool]] = Field(default=None, description="Outils activés")
    
    @field_validator('temperature')
    @classmethod
    def temperature_must_be_valid(cls, v):
        if v is not None and (v < 0.0 or v > 2.0):
            raise ValueError('La température doit être entre 0.0 et 2.0')
        return v