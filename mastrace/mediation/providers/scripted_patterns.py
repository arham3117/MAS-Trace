"""What the scripted provider treats as an instruction (plan.md §7.13).

A constant list on purpose: the scripted provider must not depend on
`configs/detectors.yaml` (Phase 6). Besides these regexes, any email address that is not an
allowed recipient also makes a paragraph an instruction.
"""

from __future__ import annotations

import re

SCRIPTED_INSTRUCTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore (all|previous) instructions", re.I),
    re.compile(r"note to the (operator|team member)", re.I),
    re.compile(r"send (a )?copy to", re.I),
    re.compile(r"MARKER:"),
)

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
CREDENTIALS_PATH_PATTERN = re.compile(r"[\w./-]*credentials\.txt")
