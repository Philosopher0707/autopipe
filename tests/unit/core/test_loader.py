"""Tests for autopipe.core.loader module."""

import pytest

from autopipe.core.loader import import_class, load_pipeline_from_config, load_step_from_config
from autopipe.core.pipeline import Pipeline
from autopipe.core.steps import PrintStep
from autopipe.schemas.models import PipelineConfig, SecretMaterialError


class TestImportClass:
    def test_import_valid_class(self):
        cls = import_class("autopipe.core.steps.PrintStep")
        assert cls is PrintStep

    def test_import_invalid_module(self):
        # Untrusted roots are rejected by the allowlist before any import.
        with pytest.raises(ValueError, match="not allowed"):
            import_class("nonexistent_module.SomeClass")

    def test_import_invalid_attribute(self):
        with pytest.raises(ValueError, match="not found in module"):
            import_class("autopipe.core.steps.NonexistentStep")


class TestLoadStepFromConfig:
    def test_load_print_step_by_alias(self):
        step = load_step_from_config(
            {"name": "hello", "type": "print", "params": {"message": "hi"}}
        )
        assert isinstance(step, PrintStep)
        assert step.name == "hello"

    def test_load_print_step_by_full_path(self):
        step = load_step_from_config(
            {
                "name": "hello",
                "type": "autopipe.core.steps.PrintStep",
                "params": {"message": "hi"},
            }
        )
        assert isinstance(step, PrintStep)

    def test_load_step_with_depends_on(self):
        step = load_step_from_config(
            {
                "name": "step_b",
                "type": "print",
                "params": {"message": "b"},
                "depends_on": ["step_a"],
            }
        )
        assert step.depends_on == ["step_a"]

    def test_load_step_missing_name_raises(self):
        with pytest.raises(KeyError):
            load_step_from_config({"type": "print"})

    def test_load_step_unknown_type_raises(self):
        with pytest.raises(ValueError):
            load_step_from_config({"name": "bad", "type": "nonexistent_step_type"})


class TestQuarantinedStepBoundary:
    """I16 hardening: untrusted config must not reach host-capability steps.

    PiCodingStep spawns a subprocess with a bash tool and is documented as
    quarantined (explicit Python import only — CHANGELOG 0.2.0, NORTH_STAR).
    The trusted-root allowlist alone does not enforce that, because
    ``autopipe.steps.`` covers the pi_coding module. These tests pin the
    boundary: every config-driven path is blocked; direct Python import
    remains available for human operators.
    """

    PI_FQ = "autopipe.steps.pi_coding.PiCodingStep"

    def test_import_class_rejects_fully_qualified_pi_step(self):
        with pytest.raises(ValueError, match="quarantine"):
            import_class(self.PI_FQ)

    def test_load_step_from_config_rejects_pi_step(self):
        with pytest.raises(ValueError, match="quarantine"):
            load_step_from_config({"name": "agent", "type": self.PI_FQ, "params": {"prompt": "x"}})

    def test_load_pipeline_from_config_rejects_nested_pi_step(self):
        config = {
            "name": "sneaky",
            "steps": [
                {"name": "ok", "type": "print", "params": {"message": "hi"}},
                {"name": "agent", "type": self.PI_FQ, "params": {"prompt": "run bash"}},
            ],
        }
        with pytest.raises(ValueError, match="quarantine"):
            load_pipeline_from_config(config)

    def test_no_alias_resolves_into_pi_coding(self):
        from autopipe.core.loader import BUILTIN_ALIASES

        offenders = [
            alias
            for alias, target in BUILTIN_ALIASES.items()
            if "pi_coding" in target or alias in {"pi", "pi_coding", "coding_agent"}
        ]
        assert offenders == []

    def test_direct_python_import_still_allowed(self):
        """Quarantine means config-forbidden, not import-forbidden."""
        from autopipe.steps.pi_coding import PiCodingStep

        assert PiCodingStep.__name__ == "PiCodingStep"

    def test_general_allowlist_still_enforced(self):
        with pytest.raises(ValueError, match="not allowed"):
            import_class("os.system")
        assert import_class("autopipe.steps.data.DataLoaderStep") is not None


class TestSecretParamBoundary:
    """I12-A: durable configs carry references, never key material.

    Every config path (CLI, YAML, library, dashboard admission) validates
    through PipelineConfig, so the model-level reject is the single gate.
    See docs/architecture/CREDENTIAL_REFERENCE_MODEL.md.
    """

    VALUE = "sk-must-never-appear-in-any-error"

    @staticmethod
    def _config(params):
        return {"name": "p", "steps": [{"name": "s", "type": "print", "params": params}]}

    def test_flat_api_key_rejected_on_load(self):
        with pytest.raises(SecretMaterialError, match="api_key"):
            load_pipeline_from_config(self._config({"message": "hi", "api_key": self.VALUE}))

    def test_error_names_key_but_never_value(self):
        with pytest.raises(SecretMaterialError) as ei:
            load_pipeline_from_config(self._config({"message": "hi", "api_key": self.VALUE}))
        message = str(ei.value)
        assert "api_key" in message
        assert self.VALUE not in message

    def test_nested_secret_rejected(self):
        with pytest.raises(SecretMaterialError, match=r"client\.auth_token"):
            PipelineConfig.model_validate(self._config({"client": {"auth_token": "x"}}))

    def test_key_normalization_covers_case_and_separators(self):
        for key in ("API-Key", "Auth_Token", "SECRET", "access-token"):
            with pytest.raises(SecretMaterialError, match=key):
                PipelineConfig.model_validate(self._config({key: "v"}))

    def test_benign_lookalikes_allowed(self):
        # max_tokens/tokenizer/monkey are not secret names — substring
        # matching would false-positive here, so matching is exact+suffix.
        PipelineConfig.model_validate(
            self._config({"message": "hi", "max_tokens": 100, "tokenizer": "gpt", "monkey": "x"})
        )

    def test_empty_and_none_values_allowed(self):
        # Explicitly clearing a key is not carrying material.
        PipelineConfig.model_validate(
            self._config({"message": "hi", "api_key": "", "secret": None})
        )

    def test_nesting_beyond_depth_limit_rejected(self):
        node = "leaf"
        for _ in range(12):
            node = {"w": node}
        with pytest.raises(SecretMaterialError, match="deeper than"):
            PipelineConfig.model_validate(self._config({"message": "hi", "deep": node}))


class TestLoadPipelineFromConfig:
    def test_load_simple_pipeline(self):
        config = {
            "name": "test_pipe",
            "steps": [
                {
                    "name": "load",
                    "type": "data_loader",
                    "params": {"source": "iris.csv", "format": "csv"},
                },
                {
                    "name": "print",
                    "type": "print",
                    "params": {"message": "done"},
                    "depends_on": ["load"],
                },
            ],
        }
        pipeline = load_pipeline_from_config(config)
        assert isinstance(pipeline, Pipeline)
        assert pipeline.name == "test_pipe"
        assert len(pipeline.steps) == 2

    def test_load_empty_pipeline(self):
        config = {"name": "empty", "steps": []}
        pipeline = load_pipeline_from_config(config)
        assert pipeline.name == "empty"
        assert len(pipeline.steps) == 0

    def test_load_pipeline_default_name(self):
        config = {"steps": [{"name": "s1", "type": "print"}]}
        pipeline = load_pipeline_from_config(config)
        assert pipeline.name == "default_pipeline"
