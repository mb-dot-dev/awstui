"""Pure formatting helpers for presenting AWS data."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

_MINUTE = 60
_HOUR = 3600
_DAY = 86400
_KIB = 1024


def relative_age(moment: datetime, now: datetime) -> str:
    """Render how long ago ``moment`` was, e.g. "2h ago"."""
    seconds = int((now - moment).total_seconds())
    if seconds < _MINUTE:
        return "just now"
    if seconds < _HOUR:
        return f"{seconds // _MINUTE}m ago"
    if seconds < _DAY:
        return f"{seconds // _HOUR}h ago"
    return f"{seconds // _DAY}d ago"


def status_style(status: str) -> str:
    """Rich style for a CloudFormation stack status (rollbacks/failures win)."""
    if "ROLLBACK" in status or "FAILED" in status:
        return "red"
    if status.endswith("_IN_PROGRESS"):
        return "yellow"
    if status.endswith("_COMPLETE"):
        return "green"
    return ""


def human_size(size: int) -> str:
    """Render a byte count for humans, e.g. "1.5 KB"."""
    if size < _KIB:
        return f"{size} B"
    value = float(size)
    for unit in ("KB", "MB", "GB", "TB"):
        value /= _KIB
        if value < _KIB:
            return f"{value:.1f} {unit}"
    return f"{value / _KIB:.1f} PB"
