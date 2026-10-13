"""Builds providers from settings. The one place that knows every vendor."""

from collections.abc import Callable
from dataclasses import dataclass

from app.ai.providers.base import AIProvider, ProviderError
from app.core.config import Settings

PROVIDER_NAMES = ("openai", "anthropic", "gemini")


@dataclass(frozen=True)
class ProviderStatus:
    name: str
    active: bool
    configured: bool
    model: str | None
    fast_model: str | None


def _key(settings: Settings, name: str) -> str | None:
    secret = {
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "gemini": settings.gemini_api_key,
    }.get(name)
    return secret.get_secret_value() if secret else None


def _build(settings: Settings, name: str) -> AIProvider:
    timeout = settings.ai_request_timeout_seconds
    if name == "fake":
        from app.ai.providers.fake import FakeProvider

        return FakeProvider(delay=0.02 if settings.is_dev else 0.0)

    key = _key(settings, name)
    if not key:
        raise ProviderError(f"{name.upper()}_API_KEY is not set", code="not_configured")
    # Imported lazily so a deployment only pays for the SDK it actually uses.
    if name == "openai":
        from app.ai.providers.openai import OpenAIProvider

        return OpenAIProvider(
            key, moderation_model=settings.openai_moderation_model, timeout=timeout
        )
    if name == "anthropic":
        from app.ai.providers.anthropic import AnthropicProvider

        return AnthropicProvider(key, fast_model=settings.ai_fast_model, timeout=timeout)
    if name == "gemini":
        from app.ai.providers.gemini import GeminiProvider

        return GeminiProvider(key, fast_model=settings.ai_fast_model, timeout=timeout)
    raise ProviderError(f"Unknown AI provider '{name}'", code="not_configured")


class ProviderRegistry:
    def __init__(
        self, settings: Settings, builder: Callable[[Settings, str], AIProvider] = _build
    ) -> None:
        self._settings = settings
        self._builder = builder
        self._cache: dict[str, AIProvider] = {}

    @property
    def active_name(self) -> str:
        return self._settings.ai_provider

    def get(self, name: str | None = None) -> AIProvider:
        name = name or self.active_name
        if name not in self._cache:
            self._cache[name] = self._builder(self._settings, name)
        return self._cache[name]

    def register(self, provider: AIProvider) -> None:
        """Installs a ready-made provider (tests use this to inject a fake)."""
        self._cache[provider.name] = provider

    def statuses(self) -> list[ProviderStatus]:
        settings = self._settings
        names = [*PROVIDER_NAMES, *(["fake"] if self.active_name == "fake" else [])]
        return [
            ProviderStatus(
                name=name,
                active=name == self.active_name,
                configured=name == "fake" or bool(_key(settings, name)),
                # Model ids are only known for the active provider: AI_MODEL
                # belongs to whichever vendor AI_PROVIDER names.
                model=(settings.ai_model or None) if name == self.active_name else None,
                fast_model=(settings.ai_fast_model or None) if name == self.active_name else None,
            )
            for name in names
        ]
