"""Requested + resolved model identity in Run.provenance.

Admission writes REQUESTED_ONLY entries from the config; the LLM clients
record the response's ``model`` field on the success path only; the runner
drains those entries at finalize and ``RunStateStore.record_model_identities``
merges them (RESOLVED / UNAVAILABLE). Credential safety: only provider name,
requested model and resolved model ever reach provenance.
"""

import sys
import types
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.core.provenance import build_provenance, models_from_config
from app.db.models import Base, Pipeline, Run, RunStatus
from app.executor.sink import RunStateStore
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from autopipe.core.artifacts import drain_model_identities, record_model_identity

SENTINEL = "sk-sentinel-model-id-A"
OFFLINE = "http://127.0.0.1:9/v1"


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _fake_post(payload):
    """Build a stand-in for ``requests.post`` returning a fixed JSON body."""

    def _post(*_args, **_kwargs):
        return _FakeResponse(payload)

    return _post


# --- unit: models_from_config --------------------------------------------


def test_models_from_config_extracts_llm_step():
    config = {
        "steps": [
            {"name": "ask", "type": "llm", "params": {"provider": "ollama", "model": "llama3.1"}},
        ]
    }
    assert models_from_config(config) == [
        {
            "provider": "ollama",
            "requested_model": "llama3.1",
            "resolution_status": "REQUESTED_ONLY",
        }
    ]


def test_models_from_config_ignores_model_evaluation():
    """A model_evaluation step's `model` names a sklearn class, not an LLM."""
    config = {
        "steps": [
            {
                "name": "eval",
                "type": "model_evaluation",
                "params": {"model": "RandomForestClassifier"},
            }
        ]
    }
    assert models_from_config(config) is None


def test_models_from_config_none_without_model_steps():
    assert models_from_config(None) is None
    assert models_from_config({}) is None
    assert models_from_config({"steps": [{"name": "p", "type": "print"}]}) is None


def test_models_from_config_dedupes_pairs_preserving_order():
    config = {
        "steps": [
            {"name": "a", "type": "llm", "params": {"provider": "ollama", "model": "m1"}},
            {"name": "b", "type": "llm", "params": {"provider": "ollama", "model": "m1"}},
            {"name": "c", "type": "llm", "params": {"provider": "ollama", "model": "m2"}},
        ]
    }
    entries = models_from_config(config)
    assert entries is not None
    assert [(e["provider"], e["requested_model"]) for e in entries] == [
        ("ollama", "m1"),
        ("ollama", "m2"),
    ]


def test_models_from_config_accepts_fq_llmstep_type():
    config = {"steps": [{"name": "x", "type": "autopipe.core.steps.LLMStep", "params": {}}]}
    assert models_from_config(config) == [
        {"provider": "openrouter", "requested_model": None, "resolution_status": "REQUESTED_ONLY"}
    ]


def test_models_from_config_defaults_provider_to_openrouter():
    """Omitted provider matches the LLMStep runtime default ("openrouter")."""
    config = {"steps": [{"name": "a", "type": "llm", "params": {"model": "m"}}]}
    assert models_from_config(config) == [
        {"provider": "openrouter", "requested_model": "m", "resolution_status": "REQUESTED_ONLY"}
    ]


def test_models_from_config_lowercases_provider():
    config = {
        "steps": [
            {"name": "a", "type": "llm", "params": {"provider": "Ollama", "model": "m"}},
            {"name": "b", "type": "llm", "params": {"provider": "ollama", "model": "m"}},
        ]
    }
    entries = models_from_config(config)
    assert entries is not None
    assert [e["provider"] for e in entries] == ["ollama"], "dedup after normalization"


def test_build_provenance_models_key_present_only_when_declared():
    prov = build_provenance(
        "test",
        {"steps": [{"name": "a", "type": "llm", "params": {"provider": "ollama", "model": "m"}}]},
    )
    assert prov["models"][0]["requested_model"] == "m"
    assert prov["models"][0]["resolution_status"] == "REQUESTED_ONLY"

    prov2 = build_provenance("test", {"steps": [{"name": "p", "type": "print"}]})
    assert "models" not in prov2


# --- unit: client resolved capture ---------------------------------------


def test_ollama_chat_records_resolved_model(monkeypatch):
    from autopipe.llm import client as llm_client

    drain_model_identities()
    monkeypatch.setenv("OLLAMA_BASE_URL", OFFLINE)
    payload = {"model": "llama3.1:revision-a", "choices": [{"message": {"content": "hi"}}]}
    monkeypatch.setattr(llm_client.requests, "post", _fake_post(payload))

    client = llm_client.OllamaClient(model="llama3.1")
    assert client.chat([{"role": "user", "content": "hi"}]) == "hi"
    assert drain_model_identities() == [
        {
            "provider": "ollama",
            "requested_model": "llama3.1",
            "resolved_model": "llama3.1:revision-a",
        }
    ]


def test_ollama_response_missing_model_records_none(monkeypatch):
    from autopipe.llm import client as llm_client

    drain_model_identities()
    monkeypatch.setenv("OLLAMA_BASE_URL", OFFLINE)
    payload = {"choices": [{"message": {"content": "hi"}}]}  # no "model" field
    monkeypatch.setattr(llm_client.requests, "post", _fake_post(payload))

    client = llm_client.OllamaClient(model="llama3.1")
    client.chat([{"role": "user", "content": "hi"}])
    entries = drain_model_identities()
    assert entries[0]["provider"] == "ollama"
    assert entries[0]["resolved_model"] is None  # merge will mark UNAVAILABLE


def test_openai_chat_records_resolved_model(monkeypatch):
    from autopipe.llm import client as llm_client

    drain_model_identities()
    fake_response = SimpleNamespace(
        model="gpt-4o-2024-08-06",
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
    )
    fake_module = types.ModuleType("openai")
    fake_module.OpenAI = lambda **_kw: SimpleNamespace(  # type: ignore[attr-defined]
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_k: fake_response))
    )
    monkeypatch.setitem(sys.modules, "openai", fake_module)

    client = llm_client.OpenAIClient(api_key="test-key", model="gpt-4o")
    assert client.chat([{"role": "user", "content": "x"}]) == "ok"
    assert drain_model_identities() == [
        {
            "provider": "openai",
            "requested_model": "gpt-4o",
            "resolved_model": "gpt-4o-2024-08-06",
        }
    ]


def test_failed_chat_records_nothing(monkeypatch):
    from autopipe.llm import client as llm_client

    drain_model_identities()
    monkeypatch.setenv("OLLAMA_BASE_URL", OFFLINE)

    def boom(*a, **k):
        raise llm_client.requests.exceptions.ConnectionError("offline")

    monkeypatch.setattr(llm_client.requests, "post", boom)
    client = llm_client.OllamaClient(model="llama3.1")
    try:
        client.chat([{"role": "user", "content": "hi"}])
    except ValueError:
        pass  # expected: Cannot connect to Ollama
    else:
        raise AssertionError("offline chat must fail")
    assert drain_model_identities() == [], "no response -> no recorded identity"


@pytest.mark.parametrize("provider", ["openai", "anthropic", "openrouter", "ollama"])
def test_clients_record_exact_provider_literal(provider, monkeypatch):
    """Each provider client records its exact hardcoded literal (typo guard)."""
    from autopipe.llm import client as llm_client

    drain_model_identities()
    payload = {"model": "m-resolved", "choices": [{"message": {"content": "hi"}}]}
    if provider == "ollama":
        monkeypatch.setenv("OLLAMA_BASE_URL", OFFLINE)
        monkeypatch.setattr(llm_client.requests, "post", _fake_post(payload))
        client = llm_client.OllamaClient(api_key="test-key", model="m")
    elif provider == "openrouter":
        monkeypatch.setattr(llm_client.requests, "post", _fake_post(payload))
        client = llm_client.OpenRouterClient(api_key="test-key", model="m")
    elif provider == "openai":
        fake_response = SimpleNamespace(
            model="m-resolved",
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
        )
        fake_module = types.ModuleType("openai")
        fake_module.OpenAI = lambda **_kw: SimpleNamespace(  # type: ignore[attr-defined]
            chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_k: fake_response))
        )
        monkeypatch.setitem(sys.modules, "openai", fake_module)
        client = llm_client.OpenAIClient(api_key="test-key", model="m")
    else:  # anthropic
        fake_response = SimpleNamespace(
            model="m-resolved",
            content=[SimpleNamespace(text="ok")],
        )
        fake_module = types.ModuleType("anthropic")
        fake_module.Anthropic = lambda **_kw: SimpleNamespace(  # type: ignore[attr-defined]
            messages=SimpleNamespace(create=lambda **_k: fake_response)
        )
        monkeypatch.setitem(sys.modules, "anthropic", fake_module)
        client = llm_client.AnthropicClient(api_key="test-key", model="m")

    assert client.chat([{"role": "user", "content": "hi"}]) in ("hi", "ok")
    entries = drain_model_identities()
    assert entries == [
        {
            "provider": provider,
            "requested_model": "m",
            "resolved_model": "m-resolved",
        }
    ]


def test_recorder_does_not_leak_between_hygiene_cycles():
    record_model_identity(
        {"provider": "ollama", "requested_model": None, "resolved_model": "stale"}
    )
    assert drain_model_identities() == [
        {"provider": "ollama", "requested_model": None, "resolved_model": "stale"}
    ]
    assert drain_model_identities() == [], "second drain sees nothing"


# --- unit: merge logic (RunStateStore) -----------------------------------


def _make_sync_session(db_path: Path) -> sessionmaker:
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def _seed_run(SessionLocal: sessionmaker, provenance: dict | None = None) -> str:
    with SessionLocal() as db:
        pipeline = Pipeline(id=str(uuid4()), name="p", config={"steps": []})
        db.add(pipeline)
        db.commit()
        run = Run(
            id=str(uuid4()),
            pipeline_id=pipeline.id,
            status=RunStatus.RUNNING,
            config={"steps": []},
            config_hash=None,
            run_number=1,
            provenance=provenance,
        )
        db.add(run)
        db.commit()
        return run.id


_REQUESTED = {
    "provider": "ollama",
    "requested_model": "llama3.1",
    "resolution_status": "REQUESTED_ONLY",
}


def test_merge_requested_only_plus_resolved_becomes_resolved(tmp_path: Path):
    SessionLocal = _make_sync_session(tmp_path / "m1.db")
    run_id = _seed_run(SessionLocal, {"seed_applied": 7, "models": [dict(_REQUESTED)]})
    store = RunStateStore(SessionLocal)

    store.record_model_identities(
        run_id,
        [
            {
                "provider": "ollama",
                "requested_model": "llama3.1",
                "resolved_model": "llama3.1:revision-a",
            }
        ],
    )

    with SessionLocal() as db:
        prov = db.get(Run, run_id).provenance
        assert prov["models"] == [
            {
                "provider": "ollama",
                "requested_model": "llama3.1",
                "resolved_model": "llama3.1:revision-a",
                "resolution_status": "RESOLVED",
            }
        ]
        assert prov["seed_applied"] == 7, "sibling provenance keys must survive"


def test_merge_requested_only_plus_no_id_becomes_unavailable(tmp_path: Path):
    SessionLocal = _make_sync_session(tmp_path / "m2.db")
    run_id = _seed_run(SessionLocal, {"models": [dict(_REQUESTED)]})
    store = RunStateStore(SessionLocal)

    store.record_model_identities(
        run_id,
        [{"provider": "ollama", "requested_model": "llama3.1", "resolved_model": None}],
    )

    with SessionLocal() as db:
        entry = db.get(Run, run_id).provenance["models"][0]
        assert entry["resolution_status"] == "UNAVAILABLE", "response arrived, no id"
        assert not entry.get("resolved_model"), "never fabricate an identifier"


def test_merge_appends_when_no_admission_entry(tmp_path: Path):
    SessionLocal = _make_sync_session(tmp_path / "m3.db")
    run_id = _seed_run(SessionLocal, {"origin": "dashboard"})  # no models key
    store = RunStateStore(SessionLocal)

    store.record_model_identities(
        run_id,
        [{"provider": "ollama", "requested_model": None, "resolved_model": "x"}],
    )

    with SessionLocal() as db:
        prov = db.get(Run, run_id).provenance
        assert prov["models"] == [
            {
                "provider": "ollama",
                "requested_model": None,
                "resolved_model": "x",
                "resolution_status": "RESOLVED",
            }
        ]
        assert prov["origin"] == "dashboard"


def test_merge_skips_empty_and_unknown_run(tmp_path: Path):
    SessionLocal = _make_sync_session(tmp_path / "m4.db")
    run_id = _seed_run(SessionLocal, {"models": [dict(_REQUESTED)]})
    store = RunStateStore(SessionLocal)

    store.record_model_identities(run_id, [])  # no-op, no raise
    store.record_model_identities("missing-run", [{"provider": "ollama"}])  # log + return

    with SessionLocal() as db:
        entry = db.get(Run, run_id).provenance["models"][0]
        assert entry["resolution_status"] == "REQUESTED_ONLY", "untouched"


def test_merge_openrouter_default_from_config_resolves_same_entry(tmp_path: Path):
    """Config-omitted provider -> "openrouter" admission entry resolves in place."""
    SessionLocal = _make_sync_session(tmp_path / "m5.db")
    config = {"steps": [{"name": "a", "type": "llm", "params": {"model": "gpt-x"}}]}
    admission = models_from_config(config)
    assert admission is not None and admission[0]["provider"] == "openrouter"
    run_id = _seed_run(SessionLocal, {"models": [dict(e) for e in admission]})
    store = RunStateStore(SessionLocal)

    store.record_model_identities(
        run_id,
        [
            {
                "provider": "openrouter",
                "requested_model": "gpt-x",
                "resolved_model": "gpt-x-2024-08-06",
            }
        ],
    )

    with SessionLocal() as db:
        models = db.get(Run, run_id).provenance["models"]
        assert len(models) == 1, "no orphaned REQUESTED_ONLY duplicate"
        assert models[0] == {
            "provider": "openrouter",
            "requested_model": "gpt-x",
            "resolved_model": "gpt-x-2024-08-06",
            "resolution_status": "RESOLVED",
        }


def test_merge_provider_casing_from_legacy_admission_row(tmp_path: Path):
    """Pre-fix admission row "Ollama" merges with client entry "ollama"."""
    SessionLocal = _make_sync_session(tmp_path / "m6.db")
    run_id = _seed_run(
        SessionLocal,
        {
            "models": [
                {
                    "provider": "Ollama",
                    "requested_model": "llama3.1",
                    "resolution_status": "REQUESTED_ONLY",
                }
            ]
        },
    )
    store = RunStateStore(SessionLocal)

    store.record_model_identities(
        run_id,
        [{"provider": "ollama", "requested_model": "llama3.1", "resolved_model": "llama3.1:rev"}],
    )

    with SessionLocal() as db:
        models = db.get(Run, run_id).provenance["models"]
        assert len(models) == 1, "case-insensitive provider match, no duplicate"
        assert models[0]["resolution_status"] == "RESOLVED"
        assert models[0]["provider"] == "Ollama", "existing entry's provider untouched"


# --- integration (HTTP admit -> run -> finalize) -------------------------

_LLM_CONFIG = {
    "name": "llm-identity",
    "steps": [
        {
            "name": "ask",
            "type": "llm",
            "params": {
                "provider": "ollama",
                "model": "llama3.1",
                "prompt_template": "hi",
            },
        }
    ],
}


async def test_e2e_mocked_ollama_success_records_resolved_model(
    auth_client: AsyncClient, seed_pipeline, db_session, wait_terminal, monkeypatch
):
    from autopipe.llm import client as llm_client

    monkeypatch.setenv("OLLAMA_BASE_URL", OFFLINE)
    payload = {"model": "llama3.1:revision-a", "choices": [{"message": {"content": "hello"}}]}
    monkeypatch.setattr(llm_client.requests, "post", _fake_post(payload))

    resp = await auth_client.post(
        f"/api/v1/pipelines/{seed_pipeline.id}/runs",
        json={"config_override": _LLM_CONFIG},
    )
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["id"]
    assert await wait_terminal(run_id) is RunStatus.SUCCESS

    db_session.expire_all()
    run = await db_session.get(Run, run_id)
    assert run is not None
    prov = run.provenance or {}
    assert prov["models"] == [
        {
            "provider": "ollama",
            "requested_model": "llama3.1",
            "resolved_model": "llama3.1:revision-a",
            "resolution_status": "RESOLVED",
        }
    ]
    assert run.config_hash is not None and len(run.config_hash) == 64


async def test_e2e_offline_llm_stays_requested_only(
    auth_client: AsyncClient, seed_pipeline, db_session, wait_terminal, monkeypatch
):
    monkeypatch.setenv("OLLAMA_BASE_URL", OFFLINE)

    resp = await auth_client.post(
        f"/api/v1/pipelines/{seed_pipeline.id}/runs",
        json={"config_override": _LLM_CONFIG},
    )
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["id"]
    assert await wait_terminal(run_id) is RunStatus.FAILED, "offline LLM must fail the run"

    db_session.expire_all()
    run = await db_session.get(Run, run_id)
    assert run is not None
    models = (run.provenance or {}).get("models")
    assert models == [dict(_REQUESTED)], "no response -> admission entry untouched"


async def test_e2e_sentinel_key_never_reaches_provenance(
    auth_client: AsyncClient, seed_pipeline, db_session, wait_terminal, monkeypatch
):
    from autopipe.credentials import clear_credential_cache
    from autopipe.llm import client as llm_client

    clear_credential_cache()
    monkeypatch.setenv("OLLAMA_API_KEY", SENTINEL)
    monkeypatch.setenv("OPENROUTER_API_KEY", SENTINEL)
    monkeypatch.setenv("OLLAMA_BASE_URL", OFFLINE)
    payload = {"model": "llama3.1:revision-a", "choices": [{"message": {"content": "hello"}}]}
    monkeypatch.setattr(llm_client.requests, "post", _fake_post(payload))
    try:
        resp = await auth_client.post(
            f"/api/v1/pipelines/{seed_pipeline.id}/runs",
            json={"config_override": _LLM_CONFIG},
        )
        assert resp.status_code == 201, resp.text
        run_id = resp.json()["id"]
        assert await wait_terminal(run_id) is RunStatus.SUCCESS

        db_session.expire_all()
        run = await db_session.get(Run, run_id)
        assert run is not None
        assert SENTINEL not in __import__("json").dumps(run.provenance or {})
        assert run.provenance["models"][0]["resolution_status"] == "RESOLVED"
    finally:
        clear_credential_cache()


async def test_e2e_non_model_pipeline_has_no_models_key(
    auth_client: AsyncClient, seed_pipeline, db_session, wait_terminal
):
    resp = await auth_client.post(f"/api/v1/pipelines/{seed_pipeline.id}/runs")
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["id"]
    assert await wait_terminal(run_id) is RunStatus.SUCCESS

    db_session.expire_all()
    run = await db_session.get(Run, run_id)
    assert run is not None
    assert (run.provenance or {}).get("models") is None, "absent/null, never a spurious list"
