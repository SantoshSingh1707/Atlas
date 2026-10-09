import pytest

from app.config.settings import Settings
from app.providers.llm import ConfigError, get_llm


def test_local_points_at_base_url():
    llm = get_llm(Settings(llm_provider="local",local_llm_base_url="http://localhost:1234/v1",local_llm_model="m1"))
    assert str(llm.openai_api_base) == "http://localhost:1234/v1"
    assert llm.model_name == "m1"

def test_openai_requires_key():
    with pytest.raises(ConfigError):
        get_llm(Settings(llm_provider="openai", openai_api_key=None))


def test_openai_ok():
    llm = get_llm(Settings(llm_provider="openai", openai_api_key="sk-x", openai_model="gpt-4o-mini"))
    assert llm.model_name == "gpt-4o-mini"


def test_unknown_provider():
    with pytest.raises(ConfigError):
        get_llm(Settings(llm_provider="wat"))