"""Streaming detectors D1, D2, D4 (plan.md §7.10, P6.2). Plain code, no AI (I2)."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from mastrace.core.schemas import Alert, EventKind, EventRecord
from mastrace.provenance.payload_store import PayloadStore
from mastrace.settings import REPO_ROOT

DETECTORS_CONFIG = REPO_ROOT / "configs" / "detectors.yaml"
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}


@dataclass(frozen=True)
class DetectorConfig:
    """Compiled `configs/detectors.yaml`."""

    canary: re.Pattern[str]
    injection: tuple[re.Pattern[str], ...]

    @classmethod
    def load(cls, path: Path = DETECTORS_CONFIG) -> DetectorConfig:
        """Read and compile the config."""
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(
            canary=re.compile(raw["canary_pattern"]),
            injection=tuple(re.compile(p, re.I) for p in raw["injection_patterns"]),
        )


class Detectors:
    """Runs D1, D2 and D4 over newly committed events."""

    def __init__(
        self,
        allowed_recipients: Sequence[str],
        payloads: PayloadStore,
        config: DetectorConfig | None = None,
    ) -> None:
        self.allowed = {a.lower() for a in allowed_recipients}
        self.payloads = payloads
        self.cfg = config or DetectorConfig.load()

    def injection_match(self, text: str) -> list[str]:
        """D4 features of a text: matched patterns and non-allowlisted addresses."""
        hits = [p.pattern for p in self.cfg.injection if p.search(text)]
        hits += sorted({e for e in EMAIL.findall(text) if e.lower() not in self.allowed})
        return hits

    def scan(self, events: Iterable[EventRecord]) -> list[Alert]:
        """Alerts for a batch of events, in event order."""
        alerts: list[Alert] = []
        for e in events:
            if e.kind == EventKind.TOOL_CALL and e.meta.get("source") == "action":
                alerts.extend(self._action(e))
            elif e.kind == EventKind.EXTERNAL_READ and e.output_ref:
                hits = self.injection_match(self.payloads.get(e.output_ref))
                if hits:
                    alerts.append(
                        Alert(
                            detector="injection_pattern",
                            severity="low",
                            event_id=e.event_id,
                            details={"matches": hits},
                        )
                    )
        return alerts

    def _action(self, e: EventRecord) -> list[Alert]:
        args = e.meta.get("args", {})
        if e.meta.get("tool") != "send_email":
            return []
        to = str(args.get("to", ""))
        if to.lower() in self.allowed:
            return []
        out = [
            Alert(
                detector="forbidden_recipient",
                severity="medium",
                event_id=e.event_id,
                details={"to": to, "status": e.meta.get("status")},
            )
        ]
        blob = " ".join(str(v) for v in args.values())
        if e.meta.get("status") == "ok" and self.cfg.canary.search(blob):
            out.insert(
                0,
                Alert(
                    detector="canary_leak", severity="high", event_id=e.event_id, details={"to": to}
                ),
            )
        return out


def top_alert(alerts: Sequence[Alert]) -> Alert | None:
    """The highest-severity alert (earliest first among equals)."""
    if not alerts:
        return None
    return max(enumerate(alerts), key=lambda ia: (SEVERITY_RANK[ia[1].severity], -ia[0]))[1]
