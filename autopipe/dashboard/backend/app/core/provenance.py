"""Run provenance snapshots (PROVENANCE_MODEL steps 2-3 + code revision).

Everything here is read from the live process or an explicit "unavailable"
marker — never a placeholder (I15). Historical rows keep provenance = NULL
("not recorded").
"""

import platform
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from autopipe.core.execution import ENGINE_VERSION

# Fixed list: the packages that determine run behaviour. Uninstalled entries
# record "unavailable", never a guessed version. scikit-learn is included
# because builtin sample-dataset content (iris/diabetes) is version-defined.
_PACKAGES = ("autopipe", "fastapi", "sqlalchemy", "pydantic", "scikit-learn")

# Backend dir — always inside the git work tree, regardless of process cwd.
_REPO_ANCHOR = Path(__file__).resolve().parents[2]


def _environment_fingerprint() -> Dict[str, Any]:
    from importlib.metadata import PackageNotFoundError, version

    packages: Dict[str, str] = {}
    for name in _PACKAGES:
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = "unavailable"
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": packages,
    }


def _code_revision() -> str:
    """Git HEAD at run creation, suffixed -dirty if the work tree is dirty."""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_REPO_ANCHOR,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=_REPO_ANCHOR,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
        return f"{head}-dirty" if dirty else head
    except Exception:
        return "unavailable"


def seeds_from_config(config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Top-level seed declarations, if the config genuinely carries any.

    Step-level seed cooperation (PROVENANCE_MODEL step 5) does not exist yet;
    this records only what the config itself states.
    """
    if not config:
        return None
    found = {k: config[k] for k in ("seed", "seeds") if k in config}
    return found or None


def build_provenance(origin: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Snapshot engine + environment + code identity for a Run about to be created."""
    return {
        "engine_version": ENGINE_VERSION,
        "origin": origin,
        "environment": _environment_fingerprint(),
        "code_revision": _code_revision(),
        "seeds": seeds_from_config(config),
    }
