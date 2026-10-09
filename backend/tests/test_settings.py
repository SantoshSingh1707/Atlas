from app.config.settings import Settings, get_settings


def test_defaults():
    s = Settings()
    assert s.llm_provider=="local"
    assert s.search_providers ==["tavily" , "duckduckgo"]
    assert s.auth_enabled is False
    

def test_comma_env_parses_to_list(monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDERS","duckduckgo,tavily")
    monkeypatch.setenv("MAX_TOKENS_PER_RUN","1234")
    
    s = Settings()
    assert s.search_providers == ["duckduckgo" , "tavily"]
    assert s.max_tokens_per_run == 1234

def test_get_settings_cached():
    assert get_settings() is get_settings()