"""Run provenance snapshots (PROVENANCE_MODEL steps 2-3 + code revision).

Everything here is read from the live process or an explicit "unavailable"
marker — never a placeholder (I15). Historical rows keep provenance = NULL
("not recorded").
"""

import hashlib
import json
import platform
import re
import subprocess
from importlib.metadata import distributions
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from autopipe.core.execution import ENGINE_VERSION

# Backend dir — always inside the git work tree, regardless of process cwd.
_REPO_ANCHOR = Path(__file__).resolve().parents[2]


def _canonical_name(name: str) -> str:
    """PEP 503 canonical package name: lowercase, runs of ``-_.`` → ``-``."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _canonical_package_records(raw: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Normalize, dedupe, and stably order ``(name, version)`` pairs.

    Names are PEP 503-canonicalized; missing/blank values become the explicit
    ``"unavailable"`` marker (never a guessed version, never silently dropped).
    Pairs are sorted by ``(name, version)`` so the order is deterministic
    regardless of ``distributions()`` enumeration order. Exact duplicate
    ``(name, version)`` pairs collapse to one; the same name with two different
    versions keeps both pairs (the hash covers the full sorted list; the dict
    form built from this list later-wins, so the lexicographically greater
    version wins after the sort).
    """
    normalized = [
        (_canonical_name(str(name)) or "unavailable", str(version) or "unavailable")
        for name, version in raw
    ]
    return sorted(set(normalized))


def _environment_hash(packages: List[Tuple[str, str]], python_version: str) -> str:
    """sha256 hex of canonical JSON over python version + sorted package pairs.

    Deterministic: same inputs → same hash; a version bump or python change →
    different hash; input list ordering is irrelevant (canonicalization is
    applied inside). Platform is deliberately excluded — its string varies
    cosmetically while python+packages are the material execution identity.
    """
    ordered = sorted(set(packages))
    payload = {"python": python_version, "packages": [list(p) for p in ordered]}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _environment_fingerprint() -> Dict[str, Any]:
    """Full installed-distribution snapshot for a Run's provenance.

    Reads ``importlib.metadata.distributions()`` once — names + versions only
    (no env vars, no editable-install paths). Any failure falls back to an
    explicit ``"unavailable"`` hash rather than raising (I15).
    """
    python = platform.python_version()
    plat = platform.platform()
    try:
        raw: List[Tuple[str, str]] = []
        for dist in distributions():
            try:
                meta = dist.metadata
                name = str(meta["Name"] or "unavailable")
                version = str(meta["Version"] or "unavailable")
            except Exception:
                name, version = "unavailable", "unavailable"
            raw.append((name, version))
        records = _canonical_package_records(raw)
        return {
            "python": python,
            "platform": plat,
            "packages": dict(records),
            "environment_hash": _environment_hash(records, python),
        }
    except Exception:
        return {
            "python": python,
            "platform": plat,
            "packages": {},
            "environment_hash": "unavailable",
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
