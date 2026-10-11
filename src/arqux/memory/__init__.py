"""BLP-002 / BLP-003: ArqUX Memory Core.

BLP-002 — a local, rebuildable projection of CORTEX that is never the source
of truth. BLP-003 — deterministic recall plus governed outcomes and feedback,
with a hard boundary between recalled context and authorization.

Standard library only.
"""

from .authority import AuthorityBoundary, AuthorityViolation
from .events import TRUST_DATA, Feedback, FeedbackEvent, OutcomeEvent, RecallResult
from .feedback import FeedbackPolicy, OutcomeRecorder, utc_now
from .models import (
    SIGIL_KINDS,
    VALID_KINDS,
    VALID_SCOPES,
    VALID_STATUSES,
    MemoryRecord,
    Origin,
    Provenance,
    record_from_entry,
    sanitize_payload,
)
from .rebuild import MemoryIndex, build_index, content_hash
from .recall import RecallService, looks_like_instruction
from .store import LoadResult, LocalStore, MemoryStore

__all__ = [
    # models
    "MemoryRecord",
    "Origin",
    "Provenance",
    "SIGIL_KINDS",
    "VALID_KINDS",
    "VALID_SCOPES",
    "VALID_STATUSES",
    "record_from_entry",
    "sanitize_payload",
    # rebuild / store
    "MemoryIndex",
    "build_index",
    "content_hash",
    "LocalStore",
    "MemoryStore",
    "LoadResult",
    # recall / events
    "RecallService",
    "RecallResult",
    "Feedback",
    "FeedbackEvent",
    "OutcomeEvent",
    "TRUST_DATA",
    "looks_like_instruction",
    # feedback / authority
    "FeedbackPolicy",
    "OutcomeRecorder",
    "utc_now",
    "AuthorityBoundary",
    "AuthorityViolation",
]
