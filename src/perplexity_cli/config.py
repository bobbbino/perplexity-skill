"""Settings via pydantic-settings with env var + keyring fallback."""

from enum import Enum

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Provider(str, Enum):
    perplexity = "perplexity"
    openrouter = "openrouter"


# Model mapping per provider
MODELS = {
    Provider.perplexity: {
        "ask": "sonar-pro",
        "research": "sonar-deep-research",
        "reason": "sonar-reasoning-pro",
    },
    Provider.openrouter: {
        "ask": "perplexity/sonar-pro",
        "research": "perplexity/sonar-deep-research",
        "reason": "perplexity/sonar-reasoning",
    },
}

BASE_URLS = {
    Provider.perplexity: "https://api.perplexity.ai",
    Provider.openrouter: "https://openrouter.ai/api/v1",
}


class Settings(BaseSettings):
    perplexity_api_key: str = ""
    openrouter_api_key: str = ""
    perplexity_base_url: str = ""
    perplexity_timeout_ms: int = 300_000

    @model_validator(mode="after")
    def _keyring_fallback(self):
        """Fall back to OS keyring for any empty secret fields."""
        for field_name in ("perplexity_api_key", "openrouter_api_key"):
            if getattr(self, field_name):
                continue
            try:
                import keyring

                val = keyring.get_password("perplexity", field_name)
                if val:
                    object.__setattr__(self, field_name, val)
            except Exception:
                pass
        return self

    def api_key(self, provider: Provider) -> str:
        if provider == Provider.perplexity:
            return self.perplexity_api_key
        return self.openrouter_api_key

    def base_url(self, provider: Provider) -> str:
        if self.perplexity_base_url and provider == Provider.perplexity:
            return self.perplexity_base_url
        return BASE_URLS[provider]


settings = Settings()
