"""Tests for credentials module."""

import os
from unittest.mock import patch

import pytest

from autopipe.credentials.manager import CredentialManager, Credentials
from autopipe.exceptions import ConfigurationError


class TestCredentialManager:
    """Tests for CredentialManager."""

    def test_get_credentials_from_env(self):
        """Test loading credentials from environment."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}):
            manager = CredentialManager()
            creds = manager.get_credentials("openai")
            assert creds.api_key == "sk-test123"

    def test_get_credentials_caching(self):
        """Test that credentials are cached."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}):
            manager = CredentialManager()
            creds1 = manager.get_credentials("openai")
            creds2 = manager.get_credentials("openai")
            assert creds1 is creds2

    def test_missing_credentials(self):
        """Test error when credentials are missing."""
        with patch.dict(os.environ, {}, clear=True):
            manager = CredentialManager()
            with pytest.raises(ConfigurationError) as exc_info:
                manager.get_credentials("openai")
            assert "OPENAI_API_KEY" in str(exc_info.value)

    def test_clear_cache(self):
        """Test clearing credential cache."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}):
            manager = CredentialManager()
            creds1 = manager.get_credentials("openai")
            manager.clear_cache()
            creds2 = manager.get_credentials("openai")
            assert creds1 is not creds2

    def test_validate_credentials(self):
        """Test credential validation."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}):
            manager = CredentialManager()
            assert manager.validate_credentials("openai") is True

        with patch.dict(os.environ, {}, clear=True):
            manager = CredentialManager()
            assert manager.validate_credentials("nonexistent") is False


class TestCredentials:
    """Tests for Credentials dataclass."""

    def test_masked_key_full(self):
        """Test masking a full API key."""
        creds = Credentials(api_key="sk-abcdefghijklmnop-wxyz")
        assert creds.masked_key == "sk-a...-wxyz"

    def test_masked_key_short(self):
        """Test masking a short API key."""
        creds = Credentials(api_key="abc123")
        assert creds.masked_key == "****"

    def test_masked_key_empty(self):
        """Test masking an empty API key."""
        creds = Credentials(api_key=None)
        assert creds.masked_key == ""

    def test_base_url(self):
        """Test credentials with base URL."""
        creds = Credentials(api_key="sk-test123", base_url="https://custom.api.com")
        assert creds.base_url == "https://custom.api.com"
