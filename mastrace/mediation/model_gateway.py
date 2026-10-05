"""Model gateway: the only path from an agent to a model (plan.md §7.7, P2.2)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from mastrace.core.canonical import canonical_json, request_hash_model, sha256_hex
from mastrace.core.errors import CacheMiss
from mastrace.core.ids import parse_turn_id
from mastrace.core.schemas import (
    ChatMessage,
    EventKind,
    ModelOutputOverride,
    ModelRequest,
    ModelResponse,
    Override,
)
from mastrace.mediation.budget import TokenBudget
from mastrace.mediation.cache import ResponseCache
from mastrace.mediation.providers.base import ModelProvider, estimate_tokens
from mastrace.provenance.recorder import EventBuffer

Mode = Literal["record", "replay", "strict_replay"]


@dataclass(frozen=True)
class ModelCallResult:
    """What an agent gets back: the response plus the local ref of its `model_call` event."""

    response: ModelResponse
    event_ref: str

    @property
    def text(self) -> str:
        """The model's text."""
        return self.response.text


class ModelGateway:
    """Caches, overrides, budgets and records every model call."""

    def __init__(
        self,
        provider: ModelProvider,
        cache: ResponseCache,
        budget: TokenBudget,
        mode: Mode = "record",
        overrides: Sequence[Override] = (),
        temperature: float = 0.0,
        max_tokens: int = 1024,
        seed: int | None = None,
        replay_salt: str | None = None,
    ) -> None:
        """`replay_salt` (replay mode, ISSUE-008) keeps independent replays independent:
        reads hit the salted entry or an entry written by a `record` run, and live answers
        are stored under the salted key, so replay k never reuses replay j's live calls."""
        self.replay_salt = replay_salt
        self.provider = provider
        self.cache = cache
        self.budget = budget
        self.mode = mode
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.seed = seed
        self._overrides = {
            (o.agent, o.turn, o.call_index): o
            for o in overrides
            if isinstance(o, ModelOutputOverride)
        }
        self._calls = 0
        self._live_calls = 0

    def stats(self) -> dict[str, int]:
        """Counters for gate check G-C1 (`calls` == number of `model_call` events)."""
        return {"calls": self._calls, "live_calls": self._live_calls}

    def call(
        self,
        agent_id: str,
        turn_id: str,
        call_index: int,
        messages: Sequence[ChatMessage],
        built_from: Sequence[str],
        buffer: EventBuffer,
    ) -> ModelCallResult:
        """Answer one model call and buffer its `model_call` event.

        Raises `CacheMiss` (strict replay) before recording anything, and `BudgetExceeded`
        after the event is buffered, so the log stays complete.
        """
        request = ModelRequest(
            model=self.provider.identity,
            messages=list(messages),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            seed=self.seed,
        )
        msg_dicts = [m.model_dump() for m in request.messages]
        rhash = request_hash_model(
            request.model, msg_dicts, request.temperature, request.max_tokens, request.seed
        )
        meta: dict[str, object] = {
            "model": request.model,
            "params": {
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "seed": request.seed,
            },
            "cache_hit": False,
            "cache_miss": False,
        }
        _, turn_n = parse_turn_id(turn_id)
        override = self._overrides.get((agent_id, turn_n, call_index))
        if override is not None:
            response = ModelResponse(
                text=override.replacement,
                prompt_tokens=sum(estimate_tokens(m.content) for m in request.messages),
                completion_tokens=estimate_tokens(override.replacement),
            )
            meta["override"] = True
        else:
            if self.replay_salt is None:
                cached = self.cache.get_model(rhash)
                store_key, origin = rhash, ("replay" if self.mode != "record" else "record")
            else:
                store_key = sha256_hex(f"{rhash}|{self.replay_salt}")
                cached = self.cache.get_model(store_key) or self.cache.get_model(
                    rhash, origin="record"
                )
                origin = f"replay:{self.replay_salt}"
            if cached is not None:
                response = cached
                meta["cache_hit"] = True
            else:
                if self.mode == "strict_replay":
                    raise CacheMiss(f"no cached response for {agent_id} {turn_id}/{call_index}")
                response = self.provider.complete(request)
                self._live_calls += 1
                self.cache.put_model(
                    store_key, request.model, canonical_json(msg_dicts), response, origin
                )
                meta["cache_miss"] = self.mode == "replay"
        meta["tokens"] = {
            "prompt": response.prompt_tokens,
            "completion": response.completion_tokens,
        }
        ref = buffer.add(
            EventKind.MODEL_CALL,
            call_index=call_index,
            built_from=list(built_from),
            request_hash=rhash,
            input_text=canonical_json(msg_dicts),
            output_text=response.text,
            meta=meta,
        )
        self._calls += 1
        self.budget.charge(response.total_tokens)
        return ModelCallResult(response=response, event_ref=ref)
