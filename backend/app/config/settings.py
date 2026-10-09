from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env",extra="ignore")
    
    #--- LLM ---
    llm_provider : str = "local"
    local_llm_base_url : str = "http://localhost:1234/v1"
    local_llm_model : str = "local-model"
    openai_api_key : str | None = None
    openai_model : str = "gpt-4o-mini"
    mistral_api_key : str | None=None
    mistral_model : str = "mistral-large-latest"
    
    #--- search ---
    search_providers : Annotated[list[str], NoDecode] = ["tavily","duckduckgo"]
    tavily_api_key : str | None = None
    
    #--- Run limits ---
    run_timeout_seconds : int = 300
    max_tokens_per_run : int = 60000
    results_per_query : int = 5
    max_sources_to_read : int = 8
    
    #--- App ---
    database_url : str = "sqlite:///./data/runs.db"
    cors_origins : Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    auth_enabled : bool = False
    
    @field_validator("search_providers" , "cors_origins",mode="before")
    @classmethod
    def _split_csv(cls,v:object)->object:
        if isinstance(v,str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v
    
@lru_cache
def get_settings()->Settings:
    return Settings()
    
    
    
    
    
