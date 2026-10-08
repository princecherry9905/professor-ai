"""Provider-neutral interface for AI models, plus the errors every provider raises.

The rest of the app only knows about these types, never about a vendor SDK.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional

Role = Literal["student", "professor"]


@dataclass
class Message:
    role: Role
    text: str


@dataclass
class GenerationConfig:
    temperature: float = 0.6
    max_output_tokens: int = 2048
    json_schema: Optional[Dict[str, Any]] = None  # set => ask the model for JSON output
    extra: dict[str, Any] = field(default_factory=dict)


# ---- Errors -----------------------------------------------------------------

class ProviderError(Exception):
    """Base class for all AI provider failures."""


class ApiKeyMissingError(ProviderError):
    pass


class AuthError(ProviderError):
    pass


class RateLimitError(ProviderError):
    pass


class ProviderTimeout(ProviderError):
    pass


class ProviderUnavailable(ProviderError):
    pass


# ---- Interface --------------------------------------------------------------

class LLMProvider(ABC):
    name: str = "base"
    # Set to True after the provider rejects our credentials; shown on /api/health.
    auth_failed: bool = False

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """True if the provider has what it needs (e.g. an API key)."""

    @abstractmethod
    async def generate(self, system: str, messages: list[Message], config: GenerationConfig) -> str:
        """Return the model's text reply. Raise a ProviderError subclass on failure."""
