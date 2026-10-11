"""Text I/O must declare its encoding.

On Windows the default text encoding is cp1252, so writing a pipeline template
containing an em-dash produced a file that is not valid UTF-8; reading it back
raised ``UnicodeDecodeError``. That was the CI failure in
``test_shipped_examples_execute.py::test_create_template_output_is_execution_ready``,
failing on every Windows job since the initial release.

The tests force the locale to ``C`` with UTF-8 mode off, which makes Python's
default text encoding US-ASCII on any platform — a faithful stand-in for the
Windows case that behaves identically on Linux and macOS.
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]

ASCII_LOCALE = {"LC_ALL": "C", "LANG": "C", "PYTHONUTF8": "0"}

# Stdio is kept UTF-8 so rich's console can print; this does NOT affect the
# default encoding of open(), which is what the bug is about. On a real Windows
# box the console is cp1252 too and rich would crash before the file was even
# written — a second symptom of the same missing-encoding class.
_STDIO = {"PYTHONIOENCODING": "utf-8"}


def _env(**extra: str) -> dict:
    return {**os.environ, **ASCII_LOCALE, **_STDIO, "PYTHONPATH": str(REPO), **extra}


def test_forced_locale_really_is_ascii():
    """Guard the premise: these tests would not catch the regression otherwise."""
    out = subprocess.run(
        [sys.executable, "-c", "import locale; print(locale.getencoding())"],
        env=_env(),
        capture_output=True,
        text=True,
    )
    assert "ASCII" in out.stdout, (
        f"locale forcing did not take effect; got {out.stdout!r}. "
        "These tests would pass regardless of the bug."
    )


def test_create_emits_utf8_under_ascii_locale(tmp_path):
    """`autopipe create` must write UTF-8 whatever the platform locale is."""
    driver = (
        "import sys; sys.argv = ['autopipe', 'create', 'generated'];"
        "from autopipe.cli import main; main()"
    )
    result = subprocess.run(
        [sys.executable, "-c", driver],
        cwd=tmp_path,
        env=_env(),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"create failed:\n{result.stderr}"

    emitted = tmp_path / "generated.yaml"
    assert emitted.exists(), "create must write the pipeline file"

    text = emitted.read_bytes().decode("utf-8")  # must not raise
    assert "—" in text, "the template's em-dash must survive the write"
    assert yaml.safe_load(text)["steps"], "emitted config must have steps"


def _text_io_without_encoding() -> list:
    """Every text-mode open()/write_text() in the package that names no encoding."""
    offenders = []
    for path in sorted((REPO / "autopipe").rglob("*.py")):
        if ".venv" in path.parts or "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if name not in {"open", "write_text"}:
                continue
            if any(kw.arg == "encoding" for kw in node.keywords):
                continue

            if name == "write_text":
                offenders.append(f"{path.relative_to(REPO)}:{node.lineno} write_text()")
                continue

            # open(path, mode): mode is the 2nd positional arg.
            if len(node.args) < 2:
                offenders.append(f"{path.relative_to(REPO)}:{node.lineno} open() no mode")
                continue
            mode = node.args[1]
            if not isinstance(mode, ast.Constant):  # computed mode: cannot judge
                continue
            if "b" in str(mode.value):  # binary never takes an encoding
                continue
            offenders.append(f"{path.relative_to(REPO)}:{node.lineno} open({mode.value!r})")

    return offenders


def test_no_text_io_without_encoding():
    """A source-level guard, because the runtime symptom only shows on Windows."""
    offenders = _text_io_without_encoding()
    assert not offenders, "text I/O relying on the platform default encoding:\n  " + "\n  ".join(
        offenders
    )


def test_binary_io_is_left_alone():
    """The guard above must not demand an encoding where none is legal."""
    src = (REPO / "autopipe" / "core" / "artifacts.py").read_text(encoding="utf-8")
    assert 'open(path, "rb")' in src, "fixture changed; binary opens must stay bare"
