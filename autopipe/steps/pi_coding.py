"""PiCodingStep — call the pi coding agent as a pipeline step.

Runs ``pi --mode json`` as a subprocess so the pi agent can use its
built-in tools (read, bash, edit, write, grep, find, ls) to operate
on the source tree.  Output is parsed from JSON lines into a
structured :class:`PiCodingResult`.

Usage::

    from autopipe.steps.pi_coding import PiCodingStep
    from autopipe import Pipeline

    pipeline = Pipeline(name="review_and_fix")
    pipeline.add_step(PiCodingStep(
        name="review",
        prompt="Review models/latest.py for memory leaks.",
        tools=["read", "bash", "grep"],
        timeout=180,
    ))
    results = pipeline.run()
    print(results["review"].final_text)
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from autopipe.core.step import Step
from autopipe.steps.pi_coding_models import PiCodingResult, PiToolCall, PiTurn

logger = logging.getLogger(__name__)

# Tool sets for convenience
READ_TOOLS: Tuple[str, ...] = ("read", "grep", "find", "ls")
READ_WRITE_TOOLS: Tuple[str, ...] = ("read", "bash", "edit", "write", "grep", "find", "ls")
ALL_TOOLS: Tuple[str, ...] = ("read", "bash", "edit", "write", "grep", "find", "ls")


@dataclasses.dataclass
class PiStepConfig:
    """Typed configuration for PiCodingStep (internal helper)."""

    name: str
    prompt: str = ""
    prompt_file: Optional[str] = None
    tools: Tuple[str, ...] = ALL_TOOLS
    model: Optional[str] = None
    provider: Optional[str] = None
    cwd: str = "."
    timeout: int = 300
    pi_path: str = "pi"
    json_mode_depth: int = 1
    append_system_prompt: Optional[str] = None
    max_lines_per_turn: int = 2000
    on_tool_call: Optional[Callable[[PiToolCall], None]] = None


class _JsonModeParser:
    """Parse pi --mode json output (JSON Lines)."""

    # Expected event keys from pi --mode json
    TEXT_DELTA = "text_delta"
    THINKING_DELTA = "thinking_delta"
    TOOL_EXECUTION_START = "tool_execution_start"
    TOOL_EXECUTION_END = "tool_execution_end"
    TURN_END = "turn_end"

    def __init__(self):
        self.current_turn_number: int = 0
        self.current_text: str = ""
        self.current_thinking: str = ""
        self.current_tools: List[PiToolCall] = []
        self.turns: List[PiTurn] = []
        self.tool_call_counter: int = 0
        self._pending_tool: Optional[Dict[str, Any]] = None

    def feed(self, raw: bytes) -> None:
        """Feed raw stdout bytes from the pi process."""
        text = raw.decode("utf-8", errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                logger.debug("Skipping non-JSON line: %s", line[:200])
                continue
            self._handle_event(event)

    def _handle_event(self, event: Dict[str, Any]) -> None:
        event_type = event.get("type", "")

        if event_type == "text_delta" and self.TEXT_DELTA in event:
            self.current_text += event[self.TEXT_DELTA]

        elif event_type == "thinking_delta" and self.THINKING_DELTA in event:
            self.current_thinking += event[self.THINKING_DELTA]

        elif event_type == "tool_execution_start":
            self.tool_call_counter += 1
            self._pending_tool = {
                "tool_name": event.get("toolName", "unknown"),
                "call_number": self.tool_call_counter,
                "input": event.get("input", {}),
                "output": "",
                "is_error": False,
            }

        elif event_type == "tool_execution_update":
            # Streaming tool output — accumulate
            if self._pending_tool is not None:
                delta = event.get("delta", "")
                self._pending_tool["output"] += delta

        elif event_type == "tool_execution_end":
            if self._pending_tool is not None:
                self._pending_tool["is_error"] = event.get("isError", False)
                self._pending_tool["output"] += event.get("finalOutput", "")
                tc = PiToolCall(
                    tool_name=self._pending_tool["tool_name"],
                    call_number=self._pending_tool["call_number"],
                    input=self._pending_tool["input"],
                    output=self._pending_tool["output"],
                    is_error=self._pending_tool["is_error"],
                )
                self.current_tools.append(tc)
                self._pending_tool = None

        elif event_type == "turn_end":
            self.current_turn_number += 1
            self.turns.append(
                PiTurn(
                    turn_number=self.current_turn_number,
                    text=self.current_text,
                    thinking=self.current_thinking,
                    tool_calls=list(self.current_tools),
                )
            )
            self.current_text = ""
            self.current_thinking = ""
            self.current_tools = []

    def result(self) -> PiCodingResult:
        """Build PiCodingResult from accumulated state."""
        # If there's a partially-built turn not yet closed, flush it
        if self.current_text or self.current_tools or self.current_thinking:
            self.current_turn_number += 1
            self.turns.append(
                PiTurn(
                    turn_number=self.current_turn_number,
                    text=self.current_text,
                    thinking=self.current_thinking,
                    tool_calls=list(self.current_tools),
                )
            )
        return PiCodingResult(
            success=True,
            turns=self.turns,
            raw_json={},
            session_id=None,
            duration_ms=0.0,
        )


class PiCodingStep(Step):
    """Pipeline step that runs the ``pi`` coding agent as a subprocess.

    The agent operates in ``--mode json --no-session`` so output can be
    parsed programmatically while being completely ephemeral.

    Parameters
    ----------
    name: str
        Step name (required).
    prompt: str
        The user prompt to send to the agent.
    prompt_file: str, optional
        Path to a prompt file (alternative to *prompt*).  If given,
        the file is passed with ``@path`` to the agent rather than
        being placed on the command line.
    tools: list[str], optional
        Allowlist of tool names.  Defaults to *ALL_TOOLS*.
        Common presets: ``READ_TOOLS``, ``READ_WRITE_TOOLS``.
    model: str, optional
        Model pattern passed to ``--model``.
    provider: str, optional
        Provider name passed to ``--provider``.
    cwd: str, optional
        Working directory for the pi subprocess.  Defaults to
        the directory resolved at runtime (or ``.``).
    timeout: int, optional
        Subprocess timeout in seconds (default 300).
    pi_path: str, optional
        Path to the ``pi`` binary (default ``"pi"``, resolved via
        :envvar:`PATH`).
    append_system_prompt: str, optional
        Extra text appended to the system prompt via
        ``--append-system-prompt``.
    on_tool_call: callable, optional
        Hook invoked synchronously every time a tool call is parsed.
        Receives a :class:`PiToolCall` dataclass.
    depends_on: list[str], optional
        Pipeline dependency names.

    Examples
    --------
    Simple code review::

        PiCodingStep(
            name="review_model",
            prompt="Review models/train.py for anti-patterns.",
            tools=["read", "bash", "grep"],
        )

    Code generation with edit capability::

        PiCodingStep(
            name="generate_utils",
            prompt="Create a utility module for data augmentation.",
            tools=["read", "bash", "edit", "write"],
            model="sonnet:high",
        )

    Read-only mode (no edits)::

        PiCodingStep(
            name="audit",
            prompt="List all files that import pandas.",
            tools=PiCodingStep.READ_TOOLS,
        )
    """

    # Convenience constants exposed on class for users
    ALL_TOOLS = ALL_TOOLS
    READ_TOOLS = READ_TOOLS
    READ_WRITE_TOOLS = READ_WRITE_TOOLS

    def __init__(
        self,
        name: str,
        prompt: str = "",
        prompt_file: Optional[str] = None,
        tools: Optional[List[str]] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        cwd: Optional[str] = None,
        timeout: int = 300,
        pi_path: str = "pi",
        append_system_prompt: Optional[str] = None,
        on_tool_call: Optional[Callable[[PiToolCall], None]] = None,
        depends_on: Optional[List[str]] = None,
    ):
        super().__init__(name, depends_on=depends_on)

        if not prompt and not prompt_file:
            raise ValueError("PiCodingStep requires either 'prompt' or 'prompt_file'")

        # Resolve cwd at init time if provided; otherwise defer to run time
        resolved_cwd = os.path.abspath(cwd) if cwd else os.getcwd()

        self._config = PiStepConfig(
            name=name,
            prompt=prompt,
            prompt_file=prompt_file,
            tools=tuple(tools) if tools else ALL_TOOLS,
            model=model,
            provider=provider,
            cwd=resolved_cwd,
            timeout=timeout,
            pi_path=pi_path,
            append_system_prompt=append_system_prompt,
            on_tool_call=on_tool_call,
        )

        logger.info(
            "PiCodingStep '%s' configured: tools=%s model=%s timeout=%ds",
            name,
            self._config.tools,
            self._config.model or "default",
            self._config.timeout,
        )

    @property
    def prompt(self) -> str:
        """Return the configured prompt (or empty string if prompt_file is used)."""
        return self._config.prompt

    @property
    def tools(self) -> Tuple[str, ...]:
        return self._config.tools

    # ------------------------------------------------------------------
    # Step protocol
    # ------------------------------------------------------------------
    def run(self, **kwargs) -> PiCodingResult:
        """Execute the pi coding agent and return a structured result."""
        t0 = time.perf_counter()

        # Allow prompt override at runtime
        prompt_text = self._build_prompt(**kwargs)

        cmd_args = self._build_command(prompt_text)
        logger.debug("PiCodingStep '%s' invoking: %s", self._config.name, " ".join(cmd_args))

        # Resolve prompt — either inline or via temp file (always safer)
        with self._prompt_as_file(prompt_text) as prompt_path:
            result = self._invoke_pi([*cmd_args, f"@{prompt_path}"], t0)

        result.prompt = prompt_text
        self.log_metrics(
            duration_ms=result.duration_ms,
            tool_calls=result.total_tool_calls,
            tool_errors=result.total_tool_errors,
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_prompt(self, **kwargs) -> str:
        """Resolve the final prompt text.

        If the step was configured with *prompt_file*, its contents
        are used (overridden by any runtime ``prompt`` kwarg).
        """
        if kwargs.get("prompt"):
            return str(kwargs["prompt"])

        if self._config.prompt_file:
            path = Path(self._config.prompt_file)
            if not path.is_file():
                raise FileNotFoundError(f"Prompt file not found: {path}")
            return path.read_text(encoding="utf-8")

        return self._config.prompt

    def _build_command(self, _prompt_text: str) -> List[str]:
        """Build the pi CLI argument list (minus the prompt file)."""
        cfg = self._config
        args: List[str] = [cfg.pi_path, "--mode", "json", "--no-session", "-p"]

        if cfg.model:
            args += ["--model", cfg.model]
        if cfg.provider:
            args += ["--provider", cfg.provider]
        if cfg.append_system_prompt:
            args += ["--append-system-prompt", cfg.append_system_prompt]

        # 0.68.0 format: comma-separated tool names
        args += ["--tools", ",".join(cfg.tools)]

        return args

    def _invoke_pi(self, cmd_args: List[str], t0: float) -> PiCodingResult:
        """Run the subprocess, parse JSON output, handle errors."""
        cfg = self._config
        parser = _JsonModeParser()
        raw_stdout = b""
        raw_stderr = b""
        proc: Optional[subprocess.Popen] = None

        try:
            proc = subprocess.Popen(
                cmd_args,
                cwd=cfg.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,  # We decode ourselves for better control
            )

            # Stream stdout with timeout check
            chunk_timeout = cfg.timeout
            deadline = time.monotonic() + chunk_timeout

            while True:
                if time.monotonic() > deadline:
                    proc.kill()
                    raise subprocess.TimeoutExpired(cmd_args[0], cfg.timeout)

                chunk = proc.stdout.read(8192) if proc.stdout else b""
                if not chunk:
                    break
                raw_stdout += chunk
                parser.feed(chunk)

                # Invoke on-tool-call hook for every completed tool parsed so far
                if cfg.on_tool_call:
                    for turn in parser.turns:
                        for tc in turn.tool_calls:
                            cfg.on_tool_call(tc)

            # Collect stderr
            raw_stderr = proc.stderr.read() if proc.stderr else b""
            retcode = proc.wait()

            if retcode != 0:
                logger.error(
                    "Pi agent exited with code %d (stderr: %s)",
                    retcode,
                    raw_stderr.decode("utf-8", errors="replace")[:500],
                )
                return PiCodingResult(
                    success=False,
                    turns=parser.turns,
                    raw_json={},
                    session_id=None,
                    duration_ms=_elapsed_ms(t0),
                    error=f"pi exited with code {retcode}",
                )

            result = parser.result()
            result.duration_ms = _elapsed_ms(t0)
            result.success = True
            return result

        except subprocess.TimeoutExpired:
            logger.error("Pi agent timed out after %d seconds", cfg.timeout)
            if proc and proc.poll() is None:
                proc.kill()
            return PiCodingResult(
                success=False,
                turns=parser.turns,
                raw_json={},
                session_id=None,
                duration_ms=_elapsed_ms(t0),
                error=f"pi agent timed out after {cfg.timeout}s",
            )

        except FileNotFoundError:
            logger.error("'%s' not found in PATH. Is pi installed?", cfg.pi_path)
            return PiCodingResult(
                success=False,
                turns=parser.turns if "parser" in dir() else [],
                raw_json={},
                session_id=None,
                duration_ms=_elapsed_ms(t0),
                error=f"'{cfg.pi_path}' not found in PATH",
            )

        except Exception as exc:
            logger.exception("Unexpected error invoking pi agent")
            if proc and proc.poll() is None:
                proc.kill()
            return PiCodingResult(
                success=False,
                turns=parser.turns if "parser" in dir() else [],
                raw_json={},
                session_id=None,
                duration_ms=_elapsed_ms(t0),
                error=str(exc),
            )

    @contextlib.contextmanager
    def _prompt_as_file(self, prompt_text: str):
        """Context manager that yields a temp file containing *prompt_text*.

        Using ``@file`` syntax prevents shell-escaping bugs and
        allows arbitrarily long prompts.
        """
        fd, path = tempfile.mkstemp(prefix="autopipe_pi_", suffix=".txt")
        try:
            os.write(fd, prompt_text.encode("utf-8"))
            os.close(fd)
            logger.debug("Prompt written to temp file: %s", path)
            yield path
        finally:
            with contextlib.suppress(OSError):
                os.unlink(path)

    # ------------------------------------------------------------------
    # Visualise
    # ------------------------------------------------------------------
    def visualize(self, **kwargs) -> None:
        """Print a text summary of the pi session to the console."""
        if not self.metrics:
            return
        duration = self.metrics.get("duration_ms", 0)
        calls = self.metrics.get("tool_calls", 0)
        errors = self.metrics.get("tool_errors", 0)
        print(f"[{self.name}] Pi Session: {duration:.0f}ms | {calls} tools ({errors} errors)")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _elapsed_ms(t0: float) -> float:
    return (time.perf_counter() - t0) * 1000
