"""Offline-testable policy boundary. No HTTP, model, database, or subprocess client.

Approvals and adapters are supplied by trusted application code after human
review, never deserialized from model requests or scraped documents. The empty
default registry approves nothing. Reviewed adapters must enforce transport
policy as well; arbitrary Python adapters are not security-sandboxed here.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import ipaddress
import re
import socket
import time
from types import MappingProxyType
from typing import Awaitable, Callable
from urllib.parse import parse_qsl, unquote, urlsplit


POLICY_VERSION = "public-sources/1"
_IDENTIFIER = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
_SECRET = re.compile(
    r"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}"
    r"|\bgh[pousr]_[A-Za-z0-9]{20,}|\bAKIA[0-9A-Z]{16}"
    r"|\b(?:password|passwd|api[_-]?key|access[_-]?token|secret)\s*[:=]\s*\S+"
    r"|\bBearer\s+\S+)", re.IGNORECASE,
)
_FORBIDDEN_KEYS = frozenset({
    "password", "passwd", "token", "access_token", "api_key", "apikey",
    "secret", "authorization", "cookie", "session", "credential",
})


class Violation(ValueError):
    """Safe policy code only; never includes raw input or exception messages."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class Access(str, Enum):
    PUBLIC = "PUBLIC"
    REQUIRES_LOGIN = "REQUIRES_LOGIN"
    RESTRICTED = "RESTRICTED"
    BREACH_OR_LEAK = "BREACH_OR_LEAK"


class Outcome(str, Enum):
    FOUND = "FOUND"
    NO_RESULTS = "NO_RESULTS"
    BLOCKED = "BLOCKED"
    RATE_LIMITED = "RATE_LIMITED"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"


def _text(value: str, *, required: bool = True, limit: int = 500) -> None:
    if not isinstance(value, str) or len(value) > limit:
        raise Violation("INVALID_TEXT")
    if required and not value.strip():
        raise Violation("MISSING_TEXT")
    if any(ord(c) < 32 or ord(c) == 127 for c in value) or _SECRET.search(value):
        raise Violation("UNSAFE_CONTENT")


def _aware(value: datetime) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _url(value: str):
    _text(value, limit=2048)
    # Reject parser ambiguity, encoded hostname/userinfo, whitespace, and
    # fragments. Query decoding is performed separately against an allowlist.
    if "\\" in value or any(c.isspace() for c in value):
        raise Violation("UNSAFE_URL")
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        raise Violation("UNSAFE_URL") from None
    host = parts.hostname or ""
    if (parts.scheme != "https" or parts.username is not None or parts.password is not None
            or port not in (None, 443) or parts.fragment or not host.isascii()
            or not re.fullmatch(r"[a-zA-Z0-9.-]+", host) or host.endswith(".")
            or "." not in host or any(not label for label in host.split("."))
            or host.lower().endswith((".local", ".internal", ".localhost"))):
        raise Violation("UNSAFE_URL")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise Violation("IP_LITERAL_FORBIDDEN")
    path = parts.path or "/"
    decoded = unquote(path)
    if (decoded != path or "//" in path or ";" in path
            or any(segment in (".", "..") for segment in path.split("/"))):
        raise Violation("AMBIGUOUS_PATH")
    return parts, "https://" + host.lower(), path


@dataclass(frozen=True)
class Scope:
    """Exact HTTPS origin and path subtree; no wildcard domains or paths."""

    origin: str
    path_prefix: str
    query_keys: frozenset[str] = frozenset()

    def __post_init__(self):
        parts, origin, _ = _url(self.origin)
        if self.origin != origin or parts.path or parts.query:
            raise Violation("INVALID_ORIGIN")
        if not isinstance(self.path_prefix, str) or not self.path_prefix.endswith("/"):
            raise Violation("INVALID_PATH_SCOPE")
        _, _, path = _url(origin + self.path_prefix)
        if path != self.path_prefix or not path.startswith("/"):
            raise Violation("INVALID_PATH_SCOPE")
        object.__setattr__(self, "query_keys", frozenset(self.query_keys))
        if any(not _IDENTIFIER.fullmatch(k) or k.lower() in _FORBIDDEN_KEYS
               for k in self.query_keys):
            raise Violation("UNSAFE_QUERY_SCOPE")


@dataclass(frozen=True)
class Approval:
    source_id: str
    scopes: tuple[Scope, ...]
    reviewed_by: str
    review_reference: str
    expires_at: datetime
    access_method: str = "OFFICIAL_API"

    def __post_init__(self):
        if not _IDENTIFIER.fullmatch(self.source_id):
            raise Violation("INVALID_SOURCE_ID")
        _text(self.reviewed_by)
        _text(self.review_reference)
        object.__setattr__(self, "scopes", tuple(self.scopes))
        if not self.scopes or any(not isinstance(s, Scope) for s in self.scopes):
            raise Violation("MISSING_SCOPE")
        if not _aware(self.expires_at):
            raise Violation("INVALID_APPROVAL_EXPIRY")
        if self.access_method not in {"OFFICIAL_API", "OFFICIAL_DOWNLOAD", "PUBLIC_PAGE"}:
            raise Violation("UNAPPROVED_ACCESS_METHOD")


@dataclass(frozen=True)
class Query:
    owner_name: str
    place: str = ""
    year: int | None = None

    def validate(self):
        _text(self.owner_name)
        _text(self.place, required=False)
        if self.year is not None and (type(self.year) is not int or not 1700 <= self.year <= 2200):
            raise Violation("INVALID_YEAR")


@dataclass(frozen=True)
class Observation:
    source_url: str
    source_record_id: str
    origin_record_id: str
    title: str
    excerpt: str
    retrieved_at: datetime
    access: Access = Access.PUBLIC
    # This records what the source said, not a confirmed owner identity.
    claim_kind: str = "SOURCE_OBSERVATION"


@dataclass(frozen=True)
class Result:
    outcome: Outcome
    observations: tuple[Observation, ...] = ()
    code: str | None = None


@dataclass(frozen=True)
class Budget:
    max_calls: int = 8
    timeout_seconds: float = 10.0
    run_seconds: float = 30.0
    max_observations: int = 40
    max_result_bytes: int = 64_000
    max_active_calls: int = 4
    max_depth: int = 2
    max_events: int = 64

    def __post_init__(self):
        for name in ("max_calls", "max_observations", "max_result_bytes", "max_active_calls", "max_depth", "max_events"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise Violation("INVALID_BUDGET")
        for value in (self.timeout_seconds, self.run_seconds):
            if type(value) not in (int, float) or not 0 < value <= 300:
                raise Violation("INVALID_BUDGET")


@dataclass(frozen=True)
class Adapter:
    approval: Approval
    collect: Callable[[Context, Query], Awaitable[Result]]


def _resolve(host: str) -> tuple[str, ...]:
    return tuple({row[4][0] for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})


@dataclass
class _Run:
    budget: Budget
    deadline: float
    calls: int = 0
    active: int = 0
    observations: int = 0
    result_bytes: int = 0
    dropped_events: int = 0
    events: list[dict[str, str]] = field(default_factory=list)


class Context:
    """One adapter call; nested dispatch shares the same run budget and policy."""

    def __init__(self, boundary: Boundary, run: _Run, approval: Approval, depth: int, deadline: float):
        self._boundary, self._run, self._approval, self._depth = boundary, run, approval, depth
        self._deadline = deadline

    async def dispatch(self, source_id: str, query: Query) -> Result:
        return await self._boundary._dispatch(source_id, query, self._run, self._depth + 1)

    async def authorize_destination(self, url: str) -> tuple[str, ...]:
        """Return reviewed public IPs, not permission to re-resolve/follow redirects.

        Future transports must pin these addresses and validate every redirect
        through this method, or use a comparably enforcing egress proxy.
        """
        if time.monotonic() >= self._deadline:
            raise Violation("RUN_BUDGET_EXCEEDED")
        if self._approval.expires_at <= datetime.now(timezone.utc):
            raise Violation("APPROVAL_EXPIRED")
        parts, origin, path = _url(url)
        scope = next((s for s in self._approval.scopes
                      if s.origin == origin and path.startswith(s.path_prefix)), None)
        if scope is None:
            raise Violation("DESTINATION_NOT_APPROVED")
        keys = set()
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            if key in keys or key not in scope.query_keys or key.lower() in _FORBIDDEN_KEYS:
                raise Violation("QUERY_NOT_APPROVED")
            keys.add(key)
            _text(value, required=False)
        try:
            addresses = tuple(await asyncio.wait_for(
                asyncio.to_thread(self._boundary._resolver, parts.hostname),
                min(self._run.budget.timeout_seconds, self._deadline - time.monotonic()),
            ))
            parsed_addresses = tuple(ipaddress.ip_address(ip) for ip in addresses)
            if not addresses or any(
                not ip.is_global or ip.is_multicast or ip.is_reserved
                or ip.is_unspecified or ip.is_loopback or ip.is_link_local
                for ip in parsed_addresses
            ):
                raise Violation("NON_PUBLIC_DESTINATION")
        except Violation:
            raise
        except asyncio.TimeoutError:
            raise Violation("DESTINATION_RESOLUTION_TIMEOUT") from None
        except Exception:
            raise Violation("DESTINATION_RESOLUTION_FAILED") from None
        return addresses


class Boundary:
    def __init__(self, adapters: tuple[Adapter, ...] = (), *, resolver=_resolve):
        registry = {}
        for adapter in adapters:
            if not isinstance(adapter, Adapter) or not callable(adapter.collect):
                raise Violation("INVALID_ADAPTER")
            source_id = adapter.approval.source_id
            if source_id in registry:
                raise Violation("DUPLICATE_SOURCE")
            registry[source_id] = adapter
        self._registry = MappingProxyType(registry)
        self._resolver = resolver

    @property
    def source_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._registry))

    def new_run(self, budget: Budget = Budget()) -> _Run:
        if not isinstance(budget, Budget):
            raise Violation("INVALID_BUDGET")
        return _Run(budget, time.monotonic() + budget.run_seconds)

    async def dispatch(self, source_id: str, query: Query, *, run: _Run | None = None) -> Result:
        return await self._dispatch(source_id, query, run if run is not None else self.new_run(), 0)

    async def _dispatch(self, source_id: str, query: Query, run: _Run, depth: int) -> Result:
        # Events intentionally contain no query, document, URL, reviewer, or
        # exception text. Persistence is the future repository's responsibility.
        def finish(outcome, code=None, observations=()):
            if len(run.events) < run.budget.max_events:
                run.events.append({"policy_version": POLICY_VERSION, "outcome": outcome.value,
                                   "code": code or "OK"})
            else:
                run.dropped_events += 1
            return Result(outcome, tuple(observations), code)

        try:
            if not isinstance(source_id, str) or source_id not in self._registry:
                raise Violation("SOURCE_NOT_APPROVED")
            if not isinstance(query, Query):
                raise Violation("INVALID_QUERY")
            query.validate()
            adapter = self._registry[source_id]
            if adapter.approval.expires_at <= datetime.now(timezone.utc):
                raise Violation("APPROVAL_EXPIRED")
            if (run.calls >= run.budget.max_calls or run.active >= run.budget.max_active_calls
                    or depth > run.budget.max_depth or time.monotonic() >= run.deadline):
                raise Violation("RUN_BUDGET_EXCEEDED")
        except Violation as exc:
            return finish(Outcome.BLOCKED, exc.code)

        # Reservation occurs before awaiting: concurrent/nested calls cannot
        # obtain separate budgets or exceed the shared active/call count.
        run.calls += 1
        run.active += 1
        call_deadline = min(run.deadline, time.monotonic() + run.budget.timeout_seconds)
        ctx = Context(self, run, adapter.approval, depth, call_deadline)
        try:
            remaining = min(run.budget.timeout_seconds, run.deadline - time.monotonic())
            result = await asyncio.wait_for(adapter.collect(ctx, query), remaining)
            if time.monotonic() >= call_deadline:
                raise asyncio.TimeoutError()
            if not isinstance(result, Result) or not isinstance(result.outcome, Outcome):
                raise Violation("INVALID_ADAPTER_RESULT")
            if result.outcome not in (Outcome.FOUND, Outcome.NO_RESULTS):
                # Never propagate adapter-controlled exception/error text.
                return finish(result.outcome, "ADAPTER_UNAVAILABLE")
            if not isinstance(result.observations, tuple):
                raise Violation("INVALID_OBSERVATIONS")
            if (result.outcome == Outcome.FOUND) != bool(result.observations):
                raise Violation("INCONSISTENT_RESULT")
            if len(result.observations) + run.observations > run.budget.max_observations:
                raise Violation("RESULT_BUDGET_EXCEEDED")
            size = 0
            for observation in result.observations:
                if not isinstance(observation, Observation):
                    raise Violation("INVALID_OBSERVATION")
                if observation.access is not Access.PUBLIC:
                    raise Violation("NON_PUBLIC_CONTENT")
                if observation.claim_kind != "SOURCE_OBSERVATION" or not _aware(observation.retrieved_at):
                    raise Violation("INVALID_PROVENANCE")
                for value in (observation.source_record_id, observation.origin_record_id,
                              observation.title, observation.excerpt):
                    _text(value, limit=run.budget.max_result_bytes)
                await ctx.authorize_destination(observation.source_url)
                size += sum(len(value.encode("utf-8")) for value in (
                    observation.source_url, observation.source_record_id, observation.origin_record_id,
                    observation.title, observation.excerpt,
                ))
                if size + run.result_bytes > run.budget.max_result_bytes:
                    raise Violation("RESULT_BUDGET_EXCEEDED")
            # Receipt validation awaits DNS. Re-check shared capacity after
            # those awaits, then commit counters without yielding to other calls.
            if (run.observations + len(result.observations) > run.budget.max_observations
                    or run.result_bytes + size > run.budget.max_result_bytes):
                raise Violation("RESULT_BUDGET_EXCEEDED")
            if time.monotonic() >= call_deadline:
                raise asyncio.TimeoutError()
            run.observations += len(result.observations)
            run.result_bytes += size
            return finish(result.outcome, observations=result.observations)
        except Violation as exc:
            return finish(Outcome.BLOCKED, exc.code)
        except asyncio.TimeoutError:
            return finish(Outcome.TIMEOUT, "ADAPTER_TIMEOUT")
        except asyncio.CancelledError:
            finish(Outcome.ERROR, "CANCELLED")
            raise
        except Exception:
            return finish(Outcome.ERROR, "ADAPTER_ERROR")
        finally:
            run.active -= 1
