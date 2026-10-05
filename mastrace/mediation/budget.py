"""Run-wide token budget shared by the model gateway and the router."""

from __future__ import annotations

from dataclasses import dataclass

from mastrace.core.errors import BudgetExceeded


@dataclass
class TokenBudget:
    """Counts tokens used by the run against `max_tokens_run`."""

    limit: int
    used: int = 0

    @property
    def exceeded(self) -> bool:
        """True once more than `limit` tokens have been used."""
        return self.used > self.limit

    def charge(self, tokens: int) -> None:
        """Add `tokens`; raise `BudgetExceeded` if the run is now over budget."""
        self.used += tokens
        if self.exceeded:
            raise BudgetExceeded(f"token budget exceeded: {self.used} > {self.limit}")
