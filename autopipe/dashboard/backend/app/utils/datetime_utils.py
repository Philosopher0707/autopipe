"""Shared datetime utilities."""

from datetime import timezone


def safe_duration_seconds(start, end):
    """Compute duration in seconds handling aware/naive datetime mix.

    SQLite returns naive datetimes while datetime.now(timezone.utc)
    returns timezone-aware. This helper normalizes both sides before
    subtraction so the thread never crashes on TypeError.
    """
    if start is None or end is None:
        return None
    if start.tzinfo is None and end.tzinfo is not None:
        start = start.replace(tzinfo=timezone.utc)
    elif start.tzinfo is not None and end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return (end - start).total_seconds()
