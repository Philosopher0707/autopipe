"""P2: registry hardening — atomic index, uuid ids, checksums, joblib, torch."""

from pathlib import Path

import numpy as np
import pytest

from autopipe.registry.model_registry import ModelRegistry

sklearn = pytest.importorskip("sklearn.linear_model")


@pytest.fixture
def fitted_model():
    X = np.random.default_rng(0).normal(size=(60, 3))
    y = (X[:, 0] > 0).astype(int)
    return sklearn.LogisticRegression().fit(X, y)


class TestAtomicIndexAndIdentity:
    def test_no_temp_file_left_behind(self, tmp_path, fitted_model):
        reg = ModelRegistry(registry_dir=str(tmp_path))
        reg.register(fitted_model, "atomic", metrics={"a": 1})
        assert not list(tmp_path.glob("*.tmp")), "temp index file leaked"

    def test_index_readable_by_fresh_instance(self, tmp_path, fitted_model):
        reg = ModelRegistry(registry_dir=str(tmp_path))
        v = reg.register(fitted_model, "reopen", metrics={"a": 1})
        reg2 = ModelRegistry(registry_dir=str(tmp_path))
        assert reg2.get_versions("reopen")[0].model_id == v.model_id

    def test_model_ids_are_unique_across_rapid_registers(self, tmp_path, fitted_model):
        """Timestamp-md5 ids collided within the same second; uuid4 must not."""
        reg = ModelRegistry(registry_dir=str(tmp_path))
        ids = {reg.register(fitted_model, f"m{i}", metrics={}).model_id for i in range(5)}
        assert len(ids) == 5


class TestIntegrityChecksum:
    def test_corrupted_artifact_rejected(self, tmp_path, fitted_model):
        reg = ModelRegistry(registry_dir=str(tmp_path))
        v = reg.register(fitted_model, "integrity", metrics={})

        artifact = Path(v.artifact_path).with_suffix(".pkl")
        artifact.write_bytes(artifact.read_bytes() + b"tampered")

        with pytest.raises(ValueError, match="integrity"):
            reg.load("integrity")

    def test_clean_roundtrip_loads(self, tmp_path, fitted_model):
        reg = ModelRegistry(registry_dir=str(tmp_path))
        v = reg.register(fitted_model, "roundtrip", metrics={})
        loaded = reg.load("roundtrip")
        sample = np.random.default_rng(1).normal(size=(5, 3))
        np.testing.assert_array_equal(loaded.predict(sample), fitted_model.predict(sample))
        assert v.artifact_sha256


class TestTorchWeightsOnly:
    def test_torch_load_uses_weights_only(self, tmp_path):
        """torch.load must be called with weights_only=True (RCE guard)."""
        torch = pytest.importorskip("torch")
        calls = {}

        import autopipe.registry.model_registry as mod

        real_load = torch.load

        def spy(*args, **kwargs):
            calls["weights_only"] = kwargs.get("weights_only")
            return real_load(*args, **kwargs)

        reg = ModelRegistry(registry_dir=str(tmp_path))

        class Tiny(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.lin = torch.nn.Linear(2, 1)

        net = Tiny()
        v = reg.register(net, "net", metrics={}, framework="pytorch")
        assert Path(v.artifact_path).with_suffix(".pt").exists()

        orig_mod_load = mod.torch.load if hasattr(mod, "torch") else None
        try:
            import torch as t2

            t2.load = spy
            reg.load("net")
        finally:
            if orig_mod_load is not None:
                mod.torch.load = orig_mod_load
        assert calls.get("weights_only") is True, "torch.load must pass weights_only=True"
