"""Dashboard widgets — ASCII sparklines, mini charts, and KV rows."""
from __future__ import annotations

BRAILLE_EMPTY = " "
BLOCK_CHARS = "▁▂▃▄▅▆▇█"


def sparkline(data: list[float], width: int = 20) -> str:
    """Render a Unicode block sparkline from a list of floats."""
    if not data:
        return BRAILLE_EMPTY * width
    chunk = max(1, len(data) // width)
    sampled = [sum(data[i : i + chunk]) / chunk for i in range(0, len(data), chunk)][-width:]
    mn, mx = min(sampled), max(sampled)
    rng = mx - mn or 1
    bars = ""
    for v in sampled:
        idx = int((v - mn) / rng * 7)
        bars += BLOCK_CHARS[idx]
    return bars.ljust(width)


def mini_chart_text(
    data: list[float], width: int = 28, height: int = 5, label: str = "", color: str = "magenta"
) -> str:
    """Render a tiny ASCII line chart as Rich markup text."""
    if len(data) < 2:
        return "\n" * height

    mn, mx = min(data), max(data)
    rng = mx - mn or 1
    step = max(1, len(data) / width)
    sampled = []
    i = 0.0
    while len(sampled) < width and int(i) < len(data):
        sampled.append(data[int(i)])
        i += step

    rows = []
    for row in range(height - 1, -1, -1):
        line = ""
        threshold = mn + rng * row / (height - 1)
        next_threshold = mn + rng * (row + 1) / (height - 1)
        for val in sampled:
            if threshold <= val < next_threshold or val >= next_threshold and row == height - 1:
                line += "·"
            else:
                line += " "
        rows.append(line)

    chart = "\n".join(f"[{color}]{r}[/{color}]" for r in rows)
    last_val = data[-1]
    first_val = data[0]
    footer = f"[dim]{first_val:.4g}[/dim][dim] → [/dim][bold {color}]{last_val:.4g}[/bold {color}]"
    return chart + "\n" + footer


# Textual widgets below — imported only when textual is available
try:
    from textual.widgets import Static as _Static
except ImportError:
    _Static = None  # type: ignore


class KVRow:
    """A single key-value row for the info panel (works with or without textual)."""

    def __init__(self, key: str, value: str, highlight: bool = False):
        self._key = key
        self._value = value
        self._highlight = highlight

    def render(self) -> str:
        style = "bold yellow" if self._highlight else "white"
        return f"[dim]{self._key:<24}[/dim][{style}]{self._value}[/{style}]"


if _Static is not None:

    class TUIKVRow(_Static):
        """Textual Static-backed KVRow — only available when textual is installed."""

        def __init__(self, key: str, value: str, highlight: bool = False, **kwargs):
            markup = (
                f"[dim]{key:<24}[/dim]"
                f"[{'bold yellow' if highlight else 'white'}]{value}[/{'bold yellow' if highlight else 'white'}]"
            )
            super().__init__(markup, **kwargs)
