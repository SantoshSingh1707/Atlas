from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_mistralai import ChatMistralAI
from langchain_openai import ChatOpenAI

from app.config.settings import Settings


class ConfigError(Exception):
    """
    Raised when provider configuration is missing or invalid
    """
    
def get_llm(settings:Settings)->BaseChatModel:
    provider = settings.llm_provider
    
    if provider=="local":
        return ChatOpenAI(
            model=settings.local_llm_model,
            base_url=settings.local_llm_base_url,
            api_key="not-needed",
            temperature=0.2,
        )
    
    if provider=="openai":
        if not settings.openai_api_key:
            raise ConfigError("OPENAI_API_KEY is required for openAI.")
        
        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.2,
        )
    
    if provider == "mistral":
        if not settings.mistral_api_key:
            raise ConfigError("MISTRAL_API_KEY is required for mistral")
        
        return ChatMistralAI(
            model = settings.mistral_model,
            api_key=settings.mistral_api_key,
            temperature=0.2
        )
    
    raise ConfigError(f"unknown LLM_PROVIDER : {provider!r}")