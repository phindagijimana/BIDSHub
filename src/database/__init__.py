"""
Database operations for BIDSHub.

Provides a clean interface for all database operations including
subjects, scans, download queue, and QC management.

The implementation is split across focused mixins (one concern per module);
``Database`` simply composes them on top of the connection-owning
:class:`~src.database.base.DatabaseBase`. The public surface is unchanged —
import it exactly as before::

    from src.database import Database

**SQL and parameters:** every mixin uses the standard ``sqlite3`` API with
placeholders, e.g. ``cursor.execute(query, (value,))`` where ``query`` is a
string containing ``?`` tokens—**never** building SQL with string concatenation
of untrusted input.
"""

from .base import DatabaseBase
from .datasets import DatasetMixin
from .subjects import SubjectMixin
from .scans import ScanMixin
from .queue import DownloadQueueMixin
from .sessions import SessionMixin
from .misc import MiscMixin
from .maintenance import MaintenanceMixin


class Database(
    DatasetMixin,
    SubjectMixin,
    ScanMixin,
    DownloadQueueMixin,
    SessionMixin,
    MiscMixin,
    MaintenanceMixin,
    DatabaseBase,
):
    """Database manager for BIDSHub."""


__all__ = ["Database"]
