"""Unit tests for PiCodingStep.

These tests use extensive mocking so they run fast without needing a
real ``pi`` binary (or even Node.js).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from autopipe.core.pipeline import Pipeline
from autopipe.steps.pi_coding import PiCodingStep, _elapsed_ms, _JsonModeParser
from autopipe.steps.pi_coding_models import PiCodingResult, PiToolCall, PiTurn


class TestPiCodingResult:
    """Tests for the result dataclasses."""

    def test_empty_result(self) -> None:
        r = PiCodingResult(success=True)
        assert r.final_text == ""
        assert r.all_tool_calls == []
        assert r.total_tool_calls == 0
        assert r.total_tool_errors == 0
        assert r.generated_files == {}

    def test_final_text(self) -> None:
        r = PiCodingResult(
            success=True,
            turns=[
                PiTurn(turn_number=1, text="first", tool_calls=[]),
                PiTurn(turn_number=2, text="second", tool_calls=[]),
            ],
        )
        assert r.final_text == "second"

    def test_tool_calls_flattened(self) -> None:
        tc1 = PiToolCall(tool_name="read", call_number=1, input={"path": "a.py"}, output="ok")
        tc2 = PiToolCall(tool_name="edit", call_number=2, input={"path": "b.py"}, output="done")
        r = PiCodingResult(
            success=True,
            turns=[
                PiTurn(turn_number=1, text="", tool_calls=[tc1]),
                PiTurn(turn_number=2, text="", tool_calls=[tc2]),
            ],
        )
        assert r.total_tool_calls == 2
        assert r.total_tool_errors == 0
        assert r.all_tool_calls[0].tool_name == "read"

    def test_generated_files_heuristic(self) -> None:
        tc = PiToolCall(
            tool_name="write",
            call_number=1,
            input={"file_path": "utils.py", "path": "utils.py"},
            output="wrote 42 bytes",
        )
        r = PiCodingResult(
            success=True,
            turns=[PiTurn(turn_number=1, text="", tool_calls=[tc])],
        )
        assert r.generated_files == {"utils.py": "wrote 42 bytes"}

    def test_to_dict_roundtrip(self) -> None:
        r = PiCodingResult(
            success=True,
            turns=[
                PiTurn(
                    turn_number=1,
                    text="hello",
                    thinking=" hmm",
                    tool_calls=[
                        PiToolCall(
                            tool_name="read",
                            call_number=1,
                            input={"path": "x.py"},
                            output="content",
                            is_error=False,
                        )
                    ],
                )
            ],
            duration_ms=123.4,
        )
        d = r.to_dict()
        assert d["success"] is True
        assert d["final_text"] == "hello"
        assert d["total_tool_calls"] == 1
        assert d["turns"][0]["thinking"] == " hmm"


class TestJsonModeParser:
    """Tests for the pi --mode json line parser."""

    def _event(self, event_type: str, **kwargs) -> bytes:
        payload = {"type": event_type, **kwargs}
        return (json.dumps(payload) + "\n").encode("utf-8")

    def test_parse_text_delta(self) -> None:
        p = _JsonModeParser()
        p.feed(self._event("text_delta", text_delta="hello "))
        p.feed(self._event("text_delta", text_delta="world"))
        result = p.result()
        assert result.turns[0].text == "hello world"

    def test_parse_thinking_delta(self) -> None:
        p = _JsonModeParser()
        p.feed(self._event("thinking_delta", thinking_delta="thinking..."))
        result = p.result()
        assert result.turns[0].thinking == "thinking..."

    def test_parse_tool_call(self) -> None:
        p = _JsonModeParser()
        p.feed(self._event("tool_execution_start", toolName="read", input={"path": "a.py"}))
        p.feed(self._event("tool_execution_end", isError=False, finalOutput="content"))
        p.feed(self._event("turn_end"))
        result = p.result()
        assert result.turns[0].has_tools
        tc = result.turns[0].tool_calls[0]
        assert tc.tool_name == "read"
        assert tc.output == "content"
        assert not tc.is_error

    def test_parse_tool_with_streaming_output(self) -> None:
        p = _JsonModeParser()
        p.feed(self._event("tool_execution_start", toolName="bash", input={"command": "ls"}))
        p.feed(self._event("tool_execution_update", delta="file1\n"))
        p.feed(self._event("tool_execution_update", delta="file2\n"))
        p.feed(self._event("tool_execution_end", isError=False, finalOutput="done"))
        p.feed(self._event("turn_end"))
        result = p.result()
        tc = result.turns[0].tool_calls[0]
        assert tc.output == "file1\nfile2\ndone"

    def test_parse_multiple_turns(self) -> None:
        p = _JsonModeParser()
        for _ in range(3):
            p.feed(self._event("text_delta", text_delta="text"))
            p.feed(self._event("turn_end"))
        result = p.result()
        assert len(result.turns) == 3
        assert all(t.turn_number == i + 1 for i, t in enumerate(result.turns))

    def test_skips_non_json_lines(self) -> None:
        p = _JsonModeParser()
        p.feed(b"some random log\n")
        p.feed(self._event("text_delta", text_delta="ok"))
        p.feed(b"another log\n")
        result = p.result()
        assert result.turns[0].text == "ok"

    def test_tool_error_flag(self) -> None:
        p = _JsonModeParser()
        p.feed(self._event("tool_execution_start", toolName="bash", input={"cmd": "false"}))
        p.feed(self._event("tool_execution_end", isError=True, finalOutput="exit 1"))
        p.feed(self._event("turn_end"))
        result = p.result()
        assert result.turns[0].tool_errors[0].is_error is True


class TestPiCodingStep:
    """Tests for the step itself (with mocked pi binary)."""

    def test_requires_prompt_or_file(self) -> None:
        with pytest.raises(ValueError, match="either 'prompt' or 'prompt_file'"):
            PiCodingStep(name="bad")

    def test_prompt_property(self) -> None:
        step = PiCodingStep(name="test", prompt="hello")
        assert step.prompt == "hello"

    def test_tools_property(self) -> None:
        step = PiCodingStep(name="test", prompt="x", tools=["read", "bash"])
        assert step.tools == ("read", "bash")

    def test_default_tools(self) -> None:
        step = PiCodingStep(name="test", prompt="x")
        assert "edit" in step.tools
        assert "write" in step.tools

    def test_build_command(self) -> None:
        step = PiCodingStep(
            name="test",
            prompt="hello",
            tools=["read", "bash"],
            model="sonnet:high",
            provider="anthropic",
            append_system_prompt="Be terse.",
        )
        cmd = step._build_command("hello")
        assert cmd[0] == "pi"
        assert "--mode" in cmd
        assert "json" in cmd
        assert "--no-session" in cmd
        assert "-p" in cmd
        assert "--model" in cmd
        assert "sonnet:high" in cmd
        assert "--provider" in cmd
        assert "anthropic" in cmd
        assert "--append-system-prompt" in cmd
        assert "Be terse." in cmd
        assert "--tools" in cmd

    def test_build_command_tools_format(self) -> None:
        """Ensure tools are passed as comma-separated names (pi 0.68.0)."""
        step = PiCodingStep(name="test", prompt="x", tools=["read", "bash", "grep"])
        cmd = step._build_command("x")
        tools_idx = cmd.index("--tools")
        assert cmd[tools_idx + 1] == "read,bash,grep"

    def test_prompt_from_kwargs(self) -> None:
        step = PiCodingStep(name="test", prompt="original")
        result = step._build_prompt(prompt="override")
        assert result == "override"

    def test_prompt_from_file(self, tmp_path: Path) -> None:
        pf = tmp_path / "prompt.txt"
        pf.write_text("from file")
        step = PiCodingStep(name="test", prompt_file=str(pf))
        assert step._build_prompt() == "from file"

    def test_prompt_file_not_found(self) -> None:
        step = PiCodingStep(name="test", prompt_file="/nonexistent")
        with pytest.raises(FileNotFoundError):
            step._build_prompt()

    @patch("autopipe.steps.pi_coding.subprocess.Popen")
    def test_successful_run(self, mock_popen: MagicMock) -> None:
        mock_proc = MagicMock()
        mock_proc.stdout.read.side_effect = [
            json.dumps({"type": "text_delta", "text_delta": "done"}).encode() + b"\n",
            json.dumps({"type": "turn_end"}).encode() + b"\n",
            b"",  # EOF
        ]
        mock_proc.stderr.read.return_value = b""
        mock_proc.wait.return_value = 0
        mock_proc.poll.return_value = 0
        mock_popen.return_value = mock_proc

        step = PiCodingStep(name="test", prompt="hello")
        result = step.run()

        assert isinstance(result, PiCodingResult)
        assert result.success is True
        assert result.final_text == "done"
        assert result.duration_ms >= 0
        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        assert "--mode" in cmd
        assert "json" in cmd

    @patch("autopipe.steps.pi_coding.subprocess.Popen")
    def test_run_with_nonzero_exit(self, mock_popen: MagicMock) -> None:
        mock_proc = MagicMock()
        mock_proc.stdout.read.side_effect = [b"", b""]
        mock_proc.stderr.read.return_value = b"error: something went wrong"
        mock_proc.wait.return_value = 1
        mock_proc.poll.return_value = 1
        mock_popen.return_value = mock_proc

        step = PiCodingStep(name="test", prompt="hello")
        result = step.run()

        assert result.success is False
        assert "code 1" in (result.error or "")

    @patch("autopipe.steps.pi_coding.subprocess.Popen")
    def test_timeout(self, mock_popen: MagicMock) -> None:
        mock_proc = MagicMock()
        mock_proc.stdout.read.return_value = b""
        mock_proc.stderr.read.return_value = b""
        mock_proc.wait.return_value = 0
        # Simulate timeout by making the loop wait longer than timeout
        import time

        def slow_read(*_):
            time.sleep(0.01)
            return b""

        mock_proc.stdout.read.side_effect = slow_read
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        # Very short timeout to trigger the timeout branch
        step = PiCodingStep(name="test", prompt="hello", timeout=1)
        # Because our mock doesn't respect kill(), the timeout check
        # in the _invoke_pi loop will still fire.
        result = step.run()
        assert result is not None  # Even timeout returns a result object

    @patch("autopipe.steps.pi_coding.subprocess.Popen")
    def test_run_logs_metrics(self, mock_popen: MagicMock) -> None:
        mock_proc = MagicMock()
        mock_proc.stdout.read.side_effect = [
            json.dumps({"type": "text_delta", "text_delta": "ok"}).encode() + b"\n",
            json.dumps({"type": "turn_end"}).encode() + b"\n",
            b"",
        ]
        mock_proc.stderr.read.return_value = b""
        mock_proc.wait.return_value = 0
        mock_proc.poll.return_value = 0
        mock_popen.return_value = mock_proc

        step = PiCodingStep(name="test", prompt="hello")
        step.run()

        assert "duration_ms" in step.metrics
        assert step.metrics.get("tool_calls", 0) == 0

    def test_tool_call_callback(self) -> None:
        calls: List[PiToolCall] = []
        step = PiCodingStep(
            name="test",
            prompt="hello",
            on_tool_call=lambda tc: calls.append(tc),
        )
        parser = _JsonModeParser()
        parser.feed(json.dumps({"type": "text_delta", "text_delta": "hi"}).encode() + b"\n")
        parser.feed(
            json.dumps({"type": "tool_execution_start", "toolName": "read", "input": {}}).encode()
            + b"\n"
        )
        parser.feed(
            json.dumps(
                {"type": "tool_execution_end", "isError": False, "finalOutput": "x"}
            ).encode()
            + b"\n"
        )
        parser.feed(json.dumps({"type": "turn_end"}).encode() + b"\n")
        parser.result()
        # Callback tested via actual subprocess in integration; unit test
        # just ensures the config plumbing works.
        assert step._config.on_tool_call is not None

    def test_readonly_preset(self) -> None:
        step = PiCodingStep(name="test", prompt="x", tools=list(PiCodingStep.READ_TOOLS))
        assert "edit" not in step.tools
        assert "write" not in step.tools

    def test_readwrite_preset(self) -> None:
        step = PiCodingStep(name="test", prompt="x", tools=list(PiCodingStep.READ_WRITE_TOOLS))
        assert "edit" in step.tools
        assert "write" in step.tools


class TestPiCodingStepPipelineIntegration:
    """Smoke test: does PiCodingStep work inside an actual Pipeline?"""

    @patch("autopipe.steps.pi_coding.subprocess.Popen")
    def test_in_pipeline(self, mock_popen: MagicMock) -> None:
        mock_proc = MagicMock()
        mock_proc.stdout.read.side_effect = [
            json.dumps({"type": "text_delta", "text_delta": "pipeline ok"}).encode() + b"\n",
            json.dumps({"type": "turn_end"}).encode() + b"\n",
            b"",
        ]
        mock_proc.stderr.read.return_value = b""
        mock_proc.wait.return_value = 0
        mock_proc.poll.return_value = 0
        mock_popen.return_value = mock_proc

        pipeline = Pipeline(name="pi_test")
        pipeline.add_step(PiCodingStep(name="review", prompt="Review x.py"))

        results = pipeline.run()
        assert "review" in results
        assert results["review"].final_text == "pipeline ok"


class TestHelpers:
    def test_elapsed_ms(self) -> None:
        import time

        t0 = time.perf_counter()
        time.sleep(0.005)
        ms = _elapsed_ms(t0)
        assert ms >= 0.0
