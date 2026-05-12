"""Provider registry and base protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai_usage.config import Credentials
    from ai_usage.http import HttpClient
    from ai_usage.models import ProviderData


class Provider(ABC):
    """Abstract base for a balance/usage provider."""

    # Set by subclasses
    name: str = ""
    display_name: str = ""
    has_tokens: bool = False  # LLM providers with token tracking
    is_subscription: bool = False  # Codex/Claude — detail section, not table row

    def __init__(self, credentials: Credentials, http: HttpClient) -> None:
        self.creds = credentials
        self.http = http

    @abstractmethod
    def fetch(self) -> ProviderData:
        """Fetch balance, spend, and token data from the provider's APIs."""
        ...


class ProviderRegistry:
    """Manages provider discovery and construction."""

    def __init__(self) -> None:
        self._classes: dict[str, type[Provider]] = OrderedDict()

    def register(self, cls: type[Provider]) -> type[Provider]:
        """Decorator to register a provider class."""
        self._classes[cls.name] = cls
        return cls

    def get(self, name: str, credentials: Credentials, http: HttpClient) -> Provider:
        """Construct a provider by name."""
        cls = self._classes.get(name)
        if cls is None:
            raise KeyError(f"Unknown provider: {name}. Choices: {list(self._classes)}")
        return cls(credentials, http)

    def all_names(self) -> list[str]:
        """Return all registered provider names."""
        return list(self._classes.keys())

    def build_all(self, credentials: Credentials, http: HttpClient) -> dict[str, Provider]:
        """Build all registered providers."""
        return {name: self.get(name, credentials, http) for name in self._classes}


# Singleton registry
registry = ProviderRegistry()
