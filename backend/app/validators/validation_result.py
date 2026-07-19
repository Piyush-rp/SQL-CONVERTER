from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ValidationResult:
    is_valid: bool
    message: str
    sql: str
    warnings: List[str] = field(default_factory=list)
    error_code: Optional[str] = None

    # Deliberately no __bool__ override here: `if result:` would then mean
    # "is valid" while `result is not None` means "exists", and it is very
    # easy to mix the two up (an invalid-but-present ValidationResult must
    # stay truthy for identity checks). Always check `is not None` and
    # `.is_valid` explicitly instead.
