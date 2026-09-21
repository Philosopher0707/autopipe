"""Pipeline execution engine — bridges dashboard runs to autopipe.core.Pipeline.

Package-level bootstrap: the dashboard backend's virtualenv does not install the
core library, so ``autopipe`` is made importable here, once, before any executor
submodule is imported. This is documented technical debt — the honest fix is
packaging the core library into the backend environment — and it lives in the
package ``__init__`` so the path is established before ``sink``/``runner`` import
anything from ``autopipe``.
"""

import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parents[5])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
