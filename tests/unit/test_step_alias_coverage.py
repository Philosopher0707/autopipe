"""Structural coverage: every public Step class must be YAML-reachable.

The loader's BUILTIN_ALIASES map is the framework's primary interface.
Historically only 6 of ~33 step classes had aliases — the rest were
reachable only by dotted path. This module makes alias starvation
structurally impossible:

1. Every alias target resolves and is a Step subclass.
2. An AST scan of the shipped step packages finds every public Step
   subclass; each must appear as an alias target.

Known, documented exceptions are explicit at the bottom — adding a new
step class without an alias fails this test until it is either aliased
or listed with a reason.
"""

import ast
from pathlib import Path

import pytest

from autopipe.core.loader import BUILTIN_ALIASES, resolve_step_type
from autopipe.core.step import Step

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "autopipe"

# Packages scanned for public Step subclasses (dotted-prefix -> filesystem).
SCANNED_PACKAGES = {
    "autopipe.core.steps": PACKAGE_ROOT / "core" / "steps.py",
    "autopipe.steps": PACKAGE_ROOT / "steps",
    "autopipe.monitoring.drift_detection": (PACKAGE_ROOT / "monitoring" / "drift_detection.py"),
}

# Classes intentionally NOT addressable via aliases, with reasons.
ALIAS_EXEMPT = {
    # Quarantined non-core opt-in tool: explicit imports only (see 0.2.0).
    "autopipe.steps.pi_coding.PiCodingStep",
    # Toy sample-dataset loader kept for the REPL probe and its own tests;
    # the canonical `data_loader` alias points at steps.data.DataLoaderStep.
    "autopipe.core.steps.DataLoaderStep",
}


def _iter_step_files():
    for dotted, path in SCANNED_PACKAGES.items():
        if path.is_dir():
            # Each module file is its own dotted package: steps/data.py -> autopipe.steps.data
            yield from (
                (f"{dotted}.{p.stem}", p)
                for p in sorted(path.glob("*.py"))
                if p.name != "__init__.py"
            )
        else:
            yield (dotted, path)


def _public_step_classes(path: Path):
    """Yield (class_name, has_step_base) via AST — no heavy imports."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name.startswith("_"):
            continue
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(base.attr)
        yield node.name, ("Step" in bases)


def test_every_alias_resolves_to_a_step_subclass():
    assert len(BUILTIN_ALIASES) >= 30, "alias map unexpectedly shrank"
    for alias in BUILTIN_ALIASES:
        resolved = resolve_step_type(alias)
        module_name, _, class_name = resolved.rpartition(".")
        module = __import__(module_name, fromlist=[class_name])
        cls = getattr(module, class_name)
        assert issubclass(cls, Step), f"alias {alias!r} -> {resolved} is not a Step"


@pytest.mark.parametrize("package_dotted,file", sorted(_iter_step_files(), key=lambda x: x[0]))
def test_public_steps_in_file_are_aliased(package_dotted, file):
    unaliased = []
    for class_name, is_step in _public_step_classes(file):
        if not is_step:
            continue
        dotted = f"{package_dotted}.{class_name}"
        if dotted not in BUILTIN_ALIASES.values() and dotted not in ALIAS_EXEMPT:
            unaliased.append(dotted)
    assert not unaliased, (
        "Public Step classes missing from BUILTIN_ALIASES "
        f"(add an alias or a documented ALIAS_EXEMPT entry): {unaliased}"
    )


def test_alias_shortcuts_share_targets_consciously():
    """Short aliases (fe) may duplicate a canonical alias's target — but
    every shared target must be an intentional shortcut pair."""
    from collections import Counter

    targets = Counter(BUILTIN_ALIASES.values())
    for target, count in targets.items():
        if count > 1:
            aliases = sorted(a for a, v in BUILTIN_ALIASES.items() if v == target)
            # Every multi-alias target must include a documented shortcut.
            assert aliases[0] in SHORTCUT_ALIASES or any(a in SHORTCUT_ALIASES for a in aliases), (
                f"unintentional target sharing: {target} <- {aliases}"
            )


# Documented shortcuts: short forms of a canonical alias.
SHORTCUT_ALIASES = {"fe"}
