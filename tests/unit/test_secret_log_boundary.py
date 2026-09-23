"""I12-H: a runtime secret must not become observable through logs or failure output.

Witnesses the log/failure boundary on the REAL execution path (OBSERVED):

env sentinel -> CredentialManager -> OllamaClient (holds the key) -> offline
failure -> engine failure serialization.

Channels covered (CREDENTIAL_REFERENCE_MODEL threat taxonomy):

* A — direct logging: every record captured by ``caplog`` (DEBUG, all loggers).
* B — exception interpolation: ``result.error`` and the preserved exception.
* D — traceback: ``ExecutionResult.traceback`` / ``StepOutcome.traceback``.
* E — event payload: every field of every ``ExecutionEvent`` via a recording sink.
* F — accidental serialization: ``repr()`` of the result, the client, the
  exception, plus stdout/stderr writes.

Threat C (structured config logging) is exercised by the same ``caplog``
capture: no structured logging exists in the repo, and any future record at
DEBUG would be captured here.
"""

import logging

import pytest

from autopipe.core.execution import (
    ExecutionContext,
    ExecutionEngine,
    RecordingEventSink,
)
from autopipe.core.pipeline import Pipeline
from autopipe.core.run_state import RunState
from autopipe.core.steps import LLMStep
from autopipe.credentials import clear_credential_cache

SENTINEL = "I12_LOG_SENTINEL_7f3a-do-not-emit"
#: Loopback discard port: connection refused is immediate (and even a firewall
#: timeout surfaces as requests.ConnectTimeout, a ConnectionError subclass, so
#: the OllamaClient warning path stays deterministic).
OFFLINE_BASE = "http://127.0.0.1:9/v1"


@pytest.fixture
def hostile_env(monkeypatch):
    """Put the sentinel on the real credential path; keep Ollama offline."""
    clear_credential_cache()
    monkeypatch.setenv("OLLAMA_API_KEY", SENTINEL)
    monkeypatch.setenv("OLLAMA_BASE_URL", OFFLINE_BASE)
    yield
    # monkeypatch reverts the env, but the module-global credential cache does
    # not — clear it so later tests never resolve the sentinel.
    clear_credential_cache()


def test_secret_not_observable_on_real_failure_path(hostile_env, caplog, capsys):
    pipeline = Pipeline("i12-h")
    step = LLMStep(
        name="ask",
        provider="ollama",
        model="llama3.1",
        prompt_template="hi",
    )
    pipeline.add_step(step)

    sink = RecordingEventSink()
    context = ExecutionContext(
        run_id="i12-h",
        pipeline_name=pipeline.name,
        sink=sink,
    )

    with caplog.at_level(logging.DEBUG):
        result = ExecutionEngine().execute(pipeline, context)
    captured = capsys.readouterr()

    # Non-vacuous guards: the secret really entered runtime state, and the
    # real failure path really ran — otherwise "not observed" is meaningless.
    assert step.client is not None, "client must have been constructed"
    assert step.client.api_key == SENTINEL, "sentinel must enter via the real credential path"
    assert result.state is RunState.FAILED
    assert result.failed_step is not None and result.failed_step.name == "ask"
    assert result.error, "failure path must serialize an error"
    # Proves logs were captured at all: the client logs the endpoint *reference*.
    assert OFFLINE_BASE in caplog.text, "expected the Ollama offline warning in captured logs"

    observables = [
        caplog.text,
        captured.out,
        captured.err,
        result.error or "",
        result.traceback or "",
        repr(result),
        repr(result.exception),
        repr(step.client),
    ]
    outcome = result.failed_step
    observables += [outcome.error or "", outcome.traceback or ""]
    observables += [repr(event) for event in sink.events]

    joined = "\n".join(observables)
    assert SENTINEL not in joined, "runtime secret leaked into an observable failure channel"
