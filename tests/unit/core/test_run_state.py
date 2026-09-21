"""Contract tests for the canonical run/step lifecycle state machine.

Enforcement mechanism for invariants I5 (one mutation path), I6 (terminal states
cannot silently regress) and I12 (every run reaches a terminal state).
"""

import pytest

from autopipe.core.run_state import (
    RUN_TRANSITIONS,
    STEP_TRANSITIONS,
    TERMINAL_RUN_STATES,
    TERMINAL_STEP_STATES,
    RunState,
    StepState,
    ensure_transition,
)
from autopipe.exceptions import StateTransitionError


class TestStateValues:
    """The wire values are a compatibility contract with the database."""

    def test_run_state_values_match_persisted_wire_format(self):
        # app.db.models.RunStatus stores these exact strings; adopting RunState
        # must not require a data migration.
        assert RunState.values() == {"pending", "running", "success", "failed", "cancelled"}

    def test_step_state_values_match_persisted_wire_format(self):
        assert StepState.values() == {"pending", "running", "success", "failed", "skipped"}

    def test_step_states_have_no_cancelled_member(self):
        # Cancellation is a *run* concept; steps become SKIPPED.
        assert not hasattr(StepState, "CANCELLED")

    def test_terminal_sets_are_consistent_with_transition_tables(self):
        for state, allowed in RUN_TRANSITIONS.items():
            assert (state in TERMINAL_RUN_STATES) == (allowed == frozenset())
        for state, allowed in STEP_TRANSITIONS.items():
            assert (state in TERMINAL_STEP_STATES) == (allowed == frozenset())

    def test_every_state_is_covered_by_a_transition_entry(self):
        assert set(RUN_TRANSITIONS) == set(RunState)
        assert set(STEP_TRANSITIONS) == set(StepState)


class TestLegalTransitions:
    @pytest.mark.parametrize(
        ("current", "new"),
        [
            (RunState.PENDING, RunState.RUNNING),
            (RunState.PENDING, RunState.FAILED),
            (RunState.PENDING, RunState.CANCELLED),
            (RunState.RUNNING, RunState.SUCCESS),
            (RunState.RUNNING, RunState.FAILED),
            (RunState.RUNNING, RunState.CANCELLED),
        ],
    )
    def test_run_transitions_allowed(self, current, new):
        assert ensure_transition(current, new, subject="run") is new

    @pytest.mark.parametrize(
        ("current", "new"),
        [
            (StepState.PENDING, StepState.RUNNING),
            (StepState.PENDING, StepState.SKIPPED),
            (StepState.PENDING, StepState.FAILED),
            (StepState.RUNNING, StepState.SUCCESS),
            (StepState.RUNNING, StepState.FAILED),
            (StepState.RUNNING, StepState.SKIPPED),
        ],
    )
    def test_step_transitions_allowed(self, current, new):
        assert ensure_transition(current, new, subject="step") is new


class TestCoercion:
    def test_accepts_wire_value_and_member_name(self):
        assert ensure_transition("pending", "running") is RunState.RUNNING
        assert ensure_transition("PENDING", "RUNNING") is RunState.RUNNING
        assert ensure_transition(RunState.PENDING, RunState.RUNNING) is RunState.RUNNING

    def test_no_prior_state_is_always_accepted(self):
        # First write of a brand-new record.
        assert ensure_transition(None, RunState.RUNNING) is RunState.RUNNING
        assert ensure_transition(None, StepState.RUNNING, subject="step") is StepState.RUNNING

    def test_unknown_state_is_rejected(self):
        with pytest.raises(StateTransitionError, match="Unknown run state"):
            ensure_transition(RunState.PENDING, "exploded")

    def test_unknown_current_state_is_rejected(self):
        # A recorded-but-uninterpretable value is corruption, and must not be
        # mistaken for "no prior state".
        with pytest.raises(StateTransitionError, match="Unknown current run state"):
            ensure_transition("exploded", RunState.RUNNING)


class TestIdempotence:
    def test_reasserting_same_state_is_allowed(self):
        # The dashboard re-broadcasts RUNNING while writers race; that must not
        # be an error.
        assert ensure_transition(RunState.RUNNING, RunState.RUNNING) is RunState.RUNNING
        assert ensure_transition(RunState.SUCCESS, RunState.SUCCESS) is RunState.SUCCESS

    def test_reasserting_terminal_state_does_not_require_recovery(self):
        assert ensure_transition("failed", "failed", allow_recovery=False) is RunState.FAILED


class TestTerminalImmutability:
    @pytest.mark.parametrize("terminal", sorted(TERMINAL_RUN_STATES, key=lambda s: s.value))
    @pytest.mark.parametrize("target", list(RunState))
    def test_no_legal_transition_leaves_a_terminal_state(self, terminal, target):
        if target is terminal:
            assert ensure_transition(terminal, target) is terminal
            return
        with pytest.raises(StateTransitionError):
            ensure_transition(terminal, target)

    def test_terminal_error_explains_itself(self):
        with pytest.raises(StateTransitionError) as excinfo:
            ensure_transition(RunState.SUCCESS, RunState.RUNNING, context="run-123")
        message = str(excinfo.value)
        assert "success -> running" in message
        assert "terminal" in message
        assert "run-123" in message

    def test_recovery_override_is_explicit_and_permitted(self):
        # The only sanctioned way out of a terminal state (startup orphan sweep).
        assert (
            ensure_transition(RunState.FAILED, RunState.RUNNING, allow_recovery=True)
            is RunState.RUNNING
        )

    def test_non_terminal_illegal_transition_lists_what_is_allowed(self):
        with pytest.raises(StateTransitionError) as excinfo:
            ensure_transition(RunState.PENDING, RunState.SUCCESS)
        assert excinfo.value.details["allowed"] == ["cancelled", "failed", "running"]

    @pytest.mark.parametrize("terminal", sorted(TERMINAL_STEP_STATES, key=lambda s: s.value))
    def test_step_terminal_states_are_immutable(self, terminal):
        with pytest.raises(StateTransitionError):
            ensure_transition(terminal, StepState.RUNNING, subject="step")

    def test_run_only_states_are_not_valid_step_states(self):
        # RunState.CANCELLED must not be accepted as a step target: the tables
        # share "failed"/"success" but the vocabularies are not interchangeable.
        with pytest.raises(StateTransitionError, match="Unknown step state"):
            ensure_transition(StepState.PENDING, "cancelled", subject="step")
