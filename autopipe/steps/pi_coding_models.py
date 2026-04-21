"""Result models for PiCodingStep.

Structured output from the pi coding agent, typed and versioned
for programmatic consumption in pipeline steps.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Dict, List, Optional


@dataclasses.dataclass(frozen=True)
class PiToolCall:
    """A single tool invocation recorded by the pi agent."""

    tool_name: str
    call_number: int
    input: Dict[str, Any]
    output: str
    is_error: bool = False

    def __repr__(self) -> str:
        status = "ERR" if self.is_error else "OK"
        return f"PiToolCall({self.tool_name}#{self.call_number} [{status}])"


@dataclasses.dataclass(frozen=True)
class PiTurn:
    """One assistant turn: text response + tool calls."""

    turn_number: int
    text: str
    tool_calls: List[PiToolCall] = dataclasses.field(default_factory=list)
    thinking: str = ""

    @property
    def has_tools(self) -> bool:
        return len(self.tool_calls) > 0

    @property
    def tool_errors(self) -> List[PiToolCall]:
        return [tc for tc in self.tool_calls if tc.is_error]


@dataclasses.dataclass
class PiCodingResult:
    """Structured result from a pi coding session."""

    success: bool
    turns: List[PiTurn] = dataclasses.field(default_factory=list)
    raw_json: Dict[str, Any] = dataclasses.field(default_factory=dict)
    session_id: Optional[str] = None
    duration_ms: float = 0.0
    prompt: str = ""
    error: Optional[str] = None

    @property
    def final_text(self) -> str:
        """Return the final assistant text (last turn's text)."""
        if not self.turns:
            return ""
        return self.turns[-1].text

    @property
    def all_tool_calls(self) -> List[PiToolCall]:
        """Flatten all tool calls across turns."""
        return [tc for turn in self.turns for tc in turn.tool_calls]

    @property
    def generated_files(self) -> Dict[str, str]:
        """Heuristic: find files that were written by the agent.

        Returns a mapping of {filepath -> content} for files that
        appear to have been created with edit/write tool calls.
        """
        files: Dict[str, str] = {}
        for tc in self.all_tool_calls:
            if tc.tool_name in ("edit", "write"):
                path = tc.input.get("file_path", tc.input.get("path", ""))
                content = tc.output
                if path and path not in files:
                    # In edit mode, output contains the applied diff or status;
                    # the original tool input has the content.  JSON mode
                    # returns input in the tool_call record.
                    files[path] = content
        return files

    @property
    def total_tool_calls(self) -> int:
        return len(self.all_tool_calls)

    @property
    def total_tool_errors(self) -> int:
        return sum(1 for tc in self.all_tool_calls if tc.is_error)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict (useful for logging / JSON)."""
        return {
            "success": self.success,
            "session_id": self.session_id,
            "duration_ms": self.duration_ms,
            "prompt": self.prompt,
            "error": self.error,
            "final_text": self.final_text,
            "total_tool_calls": self.total_tool_calls,
            "total_tool_errors": self.total_tool_errors,
            "turns": [
                {
                    "turn_number": t.turn_number,
                    "text": t.text,
                    "thinking": t.thinking,
                    "tool_calls": [
                        {
                            "tool_name": tc.tool_name,
                            "call_number": tc.call_number,
                            "input": tc.input,
                            "output": tc.output,
                            "is_error": tc.is_error,
                        }
                        for tc in t.tool_calls
                    ],
                }
                for t in self.turns
            ],
        }
