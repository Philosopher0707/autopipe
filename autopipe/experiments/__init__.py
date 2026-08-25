"""AutoPipe Experiments Module.

Currently provides comparison report generation over tracked runs.
Full experiment management (versioning, result analysis) is planned;
see ROADMAP.md.
"""

from .reporting import ReportGenerator

__all__ = [
    "ReportGenerator",
]
