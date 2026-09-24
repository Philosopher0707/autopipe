"""Model Identity & Environment Exactness — adversarial probes.

Attacks the Task 1/2 claims where nominal tests don't reach:
1. Model alias attack (mission §13-14): same config/requested name/seed/
   dataset, two full HTTP admit→run→finalize flows whose responses report
   different ``model`` ids — config_hash must stay equal WHILE
   provenance.models distinguishes the runs (mirror of
   ``TestChangedCodeProvenance`` for the model dimension).
2. Response-arrived-but-no-id is an explicit ``UNAVAILABLE`` (the attempt is
   documented), not a silent REQUESTED_ONLY leftover (mission matrix row 3).
3. Config vs environment separation (§32 rows 7-8): a changed package
   environment changes ``environment_hash`` while the fixed config's
   ``hash_config`` is untouched (config does not absorb env).
4. Credential boundary across model+environment provenance (§30, §32 row 6):
   sentinel keys under model+env recording never reach the provenance JSON,
   the SQLite file bytes (incl. WAL), or any credential-shaped userinfo URL.

Environment determinism / version-change / order-independence rows (§21-22)
are already OBSERVED in ``test_environment_identity.py`` — not repeated here.
"""

import hashlib
import json
import re

from app.core.provenance import build_provenance
from app.db.models import Run, RunStatus, hash_config
from httpx import AsyncClient

SENTINEL = "sk-sentinel-env-only-I12"
OFFLINE = "http://127.0.0.1:9/v1"
USERINFO_URL = re.compile(r"\w+://[^/\s@]+@")


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _response(model_id: str | None) -> dict:
    payload = {"choices": [{"message": {"content": "hello"}}]}
    if model_id is not None:
        payload["model"] = model_id
    return payload


class TestModelAliasAttack:
    """MISSION §13-14 PRIMARY: alias in config, distinct resolution in reality.

    Seam patched: ``autopipe.llm.client.requests`` (the module's own reference)
    — the real admission → LLMStep → OllamaClient.chat → record_model_identity
    → runner drain → RunStateStore.record_model_identities path runs with two
    controlled response bodies. No network, no worktree mutation.
    """

    async def test_alias_resolution_distinguishes_runs_with_equal_config(
        self,
        auth_client: AsyncClient,
        seed_pipeline,
        db_session,
        wait_terminal,
        tmp_path,
        monkeypatch,
    ):
        import matplotlib

        from autopipe.llm import client as llm_client

        matplotlib.use("Agg")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("OLLAMA_BASE_URL", OFFLINE)
        csv_path = tmp_path / "input.csv"
        csv_path.write_bytes(b"feature,target\n1,0\n2,1\n3,0\n")
        pipeline_id = seed_pipeline.id

        payloads = [_response("revision-a")]

        def fake_post(*_args, **_kwargs):
            return _FakeResponse(payloads[0])

        monkeypatch.setattr(llm_client.requests, "post", fake_post)

        async def run_once():
            resp = await auth_client.post(
                f"/api/v1/pipelines/{pipeline_id}/runs",
                json={
                    "config_override": {
                        "name": "model-alias",
                        "seed": 42,
                        "steps": [
                            {
                                "name": "load",
                                "type": "data_loader",
                                "params": {"source": str(csv_path), "format": "csv"},
                            },
                            {
                                "name": "ask",
                                "type": "llm",
                                "params": {
                                    "provider": "ollama",
                                    "model": "model-alias",
                                    "prompt_template": "hi",
                                },
                            },
                        ],
                    }
                },
            )
            assert resp.status_code == 201, resp.text
            run_id = resp.json()["id"]
            assert await wait_terminal(run_id) is RunStatus.SUCCESS
            db_session.expire_all()
            run = await db_session.get(Run, run_id)
            assert run is not None
            return {"config_hash": run.config_hash, "provenance": dict(run.provenance or {})}

        run_a = await run_once()
        payloads[0] = _response("revision-b")  # same alias, different server identity
        run_b = await run_once()

        # 1. Configuration identity: equal and non-vacuous.
        assert run_a["config_hash"] is not None
        assert run_b["config_hash"] is not None
        assert run_a["config_hash"] == run_b["config_hash"]

        # 2-4. models recorded on both runs; requested side is the alias,
        # resolution is non-vacuous (RESOLVED, not REQUESTED_ONLY/UNAVAILABLE).
        models_a = run_a["provenance"].get("models")
        models_b = run_b["provenance"].get("models")
        assert models_a and models_b
        for models in (models_a, models_b):
            assert len(models) == 1
            assert models[0]["provider"] == "ollama"
            assert models[0]["requested_model"] == "model-alias"
            assert models[0]["resolution_status"] == "RESOLVED"

        # 5. PRIMARY: resolved identities differ — provenance sees through the alias.
        resolved_a = models_a[0]["resolved_model"]
        resolved_b = models_b[0]["resolved_model"]
        assert resolved_a == "revision-a"
        assert resolved_b == "revision-b"
        assert resolved_a != resolved_b

        # 6. Conjunctive: equal config_hash WHILE model identity differs.
        assert run_a["config_hash"] == run_b["config_hash"] and resolved_a != resolved_b

        # 7. Seeds declared and applied identically (parity with code test).
        for snap in (run_a, run_b):
            assert snap["provenance"].get("seeds") == {"seed": 42}
            assert snap["provenance"].get("seed_applied") == 42

        # F. Dataset identity equal across runs — only model resolution differs.
        ds_a, ds_b = run_a["provenance"].get("datasets"), run_b["provenance"].get("datasets")
        assert ds_a and ds_a == ds_b
        file_entries = [e for e in ds_a if e["kind"] == "file"]
        assert len(file_entries) == 1
        assert file_entries[0]["sha256"] == hashlib.sha256(csv_path.read_bytes()).hexdigest()


async def test_response_without_model_id_is_unavailable(
    auth_client: AsyncClient, seed_pipeline, db_session, wait_terminal, monkeypatch
):
    """Mission matrix row 3: response arrived, no id → explicit UNAVAILABLE.

    Not silent None-only and not a leftover REQUESTED_ONLY: the merge must
    document the attempt. (Offline/no-response failure stays REQUESTED_ONLY —
    covered in test_model_identity.py; here the response succeeds.)
    """
    from autopipe.llm import client as llm_client

    monkeypatch.setenv("OLLAMA_BASE_URL", OFFLINE)
    payload = _response(None)  # success body WITHOUT a "model" key

    def fake_post(*_args, **_kwargs):
        return _FakeResponse(payload)

    monkeypatch.setattr(llm_client.requests, "post", fake_post)

    resp = await auth_client.post(
        f"/api/v1/pipelines/{seed_pipeline.id}/runs",
        json={
            "config_override": {
                "name": "no-model-id",
                "steps": [
                    {
                        "name": "ask",
                        "type": "llm",
                        "params": {
                            "provider": "ollama",
                            "model": "model-alias",
                            "prompt_template": "hi",
                        },
                    }
                ],
            }
        },
    )
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["id"]
    assert await wait_terminal(run_id) is RunStatus.SUCCESS, "response was successful"

    db_session.expire_all()
    run = await db_session.get(Run, run_id)
    assert run is not None
    models = (run.provenance or {}).get("models")
    assert models and len(models) == 1
    entry = models[0]
    assert entry["requested_model"] == "model-alias"
    assert entry["resolution_status"] == "UNAVAILABLE", "attempt documented, not silent"
    assert not entry.get("resolved_model"), "never fabricate an identifier"


class TestConfigModelEnvironmentSeparation:
    """MISSION §32 rows 7-8: config / model / environment are separate axes.

    Model-vs-config separation is asserted end-to-end in
    ``TestModelAliasAttack``; environment-vs-config is exercised here by
    forcing two different package environments through the real
    ``build_provenance`` while the config dict stays fixed.
    """

    def test_environment_change_does_not_touch_config_hash(self, monkeypatch):
        from app.core import provenance as provenance_mod

        class _Dist:
            def __init__(self, name, version):
                self.metadata = {"Name": name, "Version": version}

        config = {
            "name": "sep",
            "seed": 1,
            "steps": [{"name": "a", "type": "llm", "params": {"provider": "ollama", "model": "m"}}],
        }
        cfg_hash = hash_config(config)
        assert cfg_hash is not None

        monkeypatch.setattr(provenance_mod, "distributions", lambda: [_Dist("pkg-a", "1.0.0")])
        prov_env_1 = build_provenance("test", config)

        monkeypatch.setattr(provenance_mod, "distributions", lambda: [_Dist("pkg-a", "2.0.0")])
        prov_env_2 = build_provenance("test", config)

        env_1 = prov_env_1["environment"]["environment_hash"]
        env_2 = prov_env_2["environment"]["environment_hash"]
        assert env_1 != env_2, "controlled package change must discriminate"
        assert hash_config(config) == cfg_hash, "config identity must not absorb environment"
        # models axis is config-derived and identical on both snapshots.
        assert prov_env_1["models"] == prov_env_2["models"]


class TestCredentialBoundary:
    """MISSION §30 / §32 row 6: sentinel keys under model+env provenance."""

    async def test_sentinels_stay_out_of_provenance_json_and_db(
        self,
        auth_client: AsyncClient,
        seed_pipeline,
        db_session,
        wait_terminal,
        tmp_path,
        monkeypatch,
    ):
        from autopipe.credentials import clear_credential_cache
        from autopipe.llm import client as llm_client

        clear_credential_cache()
        monkeypatch.setenv("OPENROUTER_API_KEY", SENTINEL)
        monkeypatch.setenv("OLLAMA_API_KEY", SENTINEL)
        monkeypatch.setenv("ANTHROPIC_API_KEY", SENTINEL)
        monkeypatch.setenv("OPENAI_API_KEY", SENTINEL)
        monkeypatch.setenv("DATABASE_URL", "postgresql://alice:s3cr3t-pw@db.internal:5432/fake")
        monkeypatch.setenv("OLLAMA_BASE_URL", OFFLINE)
        payload = _response("revision-a")

        def fake_post(*_args, **_kwargs):
            return _FakeResponse(payload)

        monkeypatch.setattr(llm_client.requests, "post", fake_post)
        try:
            resp = await auth_client.post(
                f"/api/v1/pipelines/{seed_pipeline.id}/runs",
                json={
                    "config_override": {
                        "name": "cred-boundary",
                        "steps": [
                            {
                                "name": "ask",
                                "type": "llm",
                                "params": {
                                    "provider": "ollama",
                                    "model": "model-alias",
                                    "prompt_template": "hi",
                                },
                            }
                        ],
                    }
                },
            )
            assert resp.status_code == 201, resp.text
            run_id = resp.json()["id"]
            assert await wait_terminal(run_id) is RunStatus.SUCCESS

            db_session.expire_all()
            run = await db_session.get(Run, run_id)
            assert run is not None
            prov = run.provenance or {}

            # Non-vacuous: both new dimensions actually recorded.
            assert prov["models"][0]["resolution_status"] == "RESOLVED"
            assert re.match(r"^[0-9a-f]{64}$", prov["environment"]["environment_hash"])

            # 1. No sentinel in the whole serialized provenance dict.
            serialized = json.dumps(prov)
            assert SENTINEL not in serialized

            # 2. No sentinel in the durable DB bytes (incl. WAL sidecars).
            blobs = b"".join(p.read_bytes() for p in sorted(tmp_path.glob("test.db*")))
            assert SENTINEL.encode() not in blobs, (
                "credential material must never reach the DB file"
            )

            # 3. No credential-shaped userinfo URL anywhere in provenance.
            assert not USERINFO_URL.search(serialized), "no user:pass@ URLs in provenance"
        finally:
            clear_credential_cache()
