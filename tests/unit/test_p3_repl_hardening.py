"""P3: REPL sandbox hardening — format-string escape, eval fallthrough, redaction."""

import pytest

from autopipe.repl import (
    SecurityError,
    _looks_secret,
    _redact,
    _redact_history_line,
    _validate_ast,
)


class TestFormatStringEscape:
    def test_dunder_escape_via_format_constant_blocked(self):
        """'{0.__class__.__mro__[1]}'.format(x) — dunders hidden in a constant
        string never produce AST Attribute nodes; the .format() call itself
        must be rejected."""
        with pytest.raises(SecurityError, match="format"):
            _validate_ast('"{0.__class__.__mro__[1].__subclasses__()}".format(int)')

    def test_benign_format_also_rejected_with_guidance(self):
        with pytest.raises(SecurityError, match="f-strings"):
            _validate_ast("'hello {}'.format(name)")

    def test_fstring_expressions_still_parsed(self):
        """f-strings keep their expressions visible to the AST checker."""
        _validate_ast("f'{x}'")
        with pytest.raises(SecurityError):
            _validate_ast("f'{x.__class__}'")


class TestRedaction:
    @pytest.mark.parametrize(
        "name", ["OPENAI_API_KEY", "auth_token", "SECRET_VALUE", "db_password"]
    )
    def test_secret_names_detected(self, name):
        assert _looks_secret(name)

    @pytest.mark.parametrize("name", ["OLLAMA_URL", "model_name", "count"])
    def test_non_secret_names_pass_through(self, name):
        assert not _looks_secret(name)

    def test_redaction_preserves_short_prefix_suffix(self):
        assert _redact("sk-live-abcdef123456") == "sk****56"
        assert _redact("abc") == "****"

    def test_history_line_masks_config_secrets(self):
        line = _redact_history_line("config OPENAI_API_KEY sk-live-abcdef123")
        assert "sk-live" not in line
        assert "OPENAI_API_KEY" in line  # name stays readable for usability
