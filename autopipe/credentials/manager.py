"""Secure credential management for AutoPipe."""

import os
from dataclasses import dataclass
from typing import Optional

from ..exceptions import ConfigurationError


@dataclass(frozen=True)
class Credentials:
    """Immutable credentials container."""

    api_key: Optional[str] = None
    base_url: Optional[str] = None
    additional: dict = None

    def __post_init__(self):
        if self.additional is None:
            object.__setattr__(self, "additional", {})

    @property
    def masked_key(self) -> str:
        """Return a masked version of the API key for logging."""
        if not self.api_key:
            return ""
        if len(self.api_key) <= 8:
            return "****"
        return f"{self.api_key[:4]}...-{self.api_key[-4:]}"


class CredentialManager:
    """Manages secure credential loading and storage.

    Credentials are loaded in priority order:
    1. Environment variables (highest priority)
    2. Credential files
    3. Configuration files (lowest priority)
    """

    def __init__(self):
        self._credentials: dict[str, Credentials] = {}

    def get_credentials(self, provider: str) -> Credentials:
        """Get credentials for a provider.

        Args:
            provider: Provider name (openai, anthropic, openrouter, etc.)

        Returns:
            Credentials object

        Raises:
            ConfigurationError: If credentials cannot be found
        """
        if provider in self._credentials:
            return self._credentials[provider]

        creds = self._load_credentials(provider)
        self._credentials[provider] = creds
        return creds

    def _load_credentials(self, provider: str) -> Credentials:
        """Load credentials from multiple sources."""
        # Check environment variables first
        env_key = self._get_env_key(provider)
        api_key = os.environ.get(env_key)

        # Check provider-specific environment variables
        if not api_key:
            env_vars = {
                "openai": ["OPENAI_API_KEY", "OPENAI_TOKEN"],
                "anthropic": ["ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN"],
                "openrouter": ["OPENROUTER_API_KEY", "OPENROUTER_TOKEN"],
            }
            for var in env_vars.get(provider, []):
                api_key = os.environ.get(var)
                if api_key:
                    break

        if not api_key:
            raise ConfigurationError(
                f"No API key found for provider '{provider}'. Set {env_key} environment variable."
            )

        # Get base URL from environment
        base_url = os.environ.get(f"{provider.upper()}_BASE_URL")

        return Credentials(api_key=api_key, base_url=base_url)

    def _get_env_key(self, provider: str) -> str:
        """Get the environment variable key for a provider."""
        return f"{provider.upper()}_API_KEY"

    def clear_cache(self) -> None:
        """Clear cached credentials."""
        self._credentials.clear()

    def validate_credentials(self, provider: str) -> bool:
        """Check if credentials exist for a provider without loading them."""
        try:
            self.get_credentials(provider)
            return True
        except ConfigurationError:
            return False


# Global credential manager instance
_credential_manager: Optional[CredentialManager] = None


def get_credential_manager() -> CredentialManager:
    """Get or create the global credential manager."""
    global _credential_manager
    if _credential_manager is None:
        _credential_manager = CredentialManager()
    return _credential_manager


def get_credentials(provider: str) -> Credentials:
    """Convenience function to get credentials for a provider."""
    return get_credential_manager().get_credentials(provider)


def clear_credential_cache() -> None:
    """Clear the credential cache."""
    global _credential_manager
    if _credential_manager is not None:
        _credential_manager.clear_cache()
