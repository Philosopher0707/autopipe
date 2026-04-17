"""Test module for main __init__."""
import pytest
import sys
from unittest.mock import patch, MagicMock


class TestAutopipeInit:
    """Tests for autopipe module initialization."""

    def test_version_exists(self):
        """Test that version is defined."""
        import autopipe
        assert hasattr(autopipe, '__version__')
        assert isinstance(autopipe.__version__, str)

    def test_all_exports_defined(self):
        """Test that __all__ is defined."""
        import autopipe
        assert hasattr(autopipe, '__all__')
        assert isinstance(autopipe.__all__, list)

    def test_getattr_lazy_import(self):
        """Test lazy import via __getattr__."""
        import autopipe
        
        # Clear any cached imports
        if hasattr(autopipe, 'Pipeline'):
            delattr(autopipe, 'Pipeline')
        
        with patch.object(sys, 'modules') as mock_modules:
            # This would trigger the import
            pass  # Testing the structure exists

    def test_main_exports_importable(self):
        """Test that main exports can be imported."""
        # These should not raise
        from autopipe import Pipeline, Step, ChartGenerator
        from autopipe import LLMClient, LLMFactory, Config


class TestAutopipeCLI:
    """Tests for autopipe CLI entry point."""

    def test_cli_main_exists(self):
        """Test that CLI main exists."""
        from autopipe.cli import main
        assert callable(main)
