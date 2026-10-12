"""Atlas Agent Engine Memory — a second, managed memory beside our own.

When Agent Engine is configured, every turn Amble records in Atlas is also
recorded in Agent Engine Memory (short-term turns, consolidated by the service
into semantic and episodic memory), and its ``build_context`` result rides
along in the prompt next to our own recall.

Configured by the SDK's own variables: ``AGENTIC_MEMORY_BASE_URL`` (local
memory server, e.g. ``http://localhost:8080``) or
``AGENTIC_MEMORY_SERVICE_ACCOUNT_TOKEN`` (+ ``AGENTIC_MEMORY_PROJECT_ID``)
for the hosted service. Unset, or the SDK missing, every call is a no-op.

Identity: our scope is the Agent Engine ``user_id``; ``agent_id`` is "amble".
Fail-soft like the rest of memory: errors are logged, chat goes on, and after
``FAIL_LIMIT`` consecutive failures it switches off until restart.
"""
from __future__ import annotations

import os
import sys

AGENT_ID = "amble"
SESSION_ID = "presents"
FAIL_LIMIT = 3
CONTEXT_TOKENS = 1024

_memory = None
_off = False
_fails = 0


def _configured() -> bool:
    return any(os.environ.get(k, "").strip() for k in
               ("AGENTIC_MEMORY_BASE_URL", "AGENTIC_MEMORY_SERVICE_ACCOUNT_TOKEN"))


def _client():
    global _memory, _off
    if _off:
        return None
    if _memory is None:
        if not _configured():
            _off = True
            return None
        try:
            from agent_engine_sdk_memory import Memory
            _memory = Memory()  # reads AGENTIC_MEMORY_* from the environment
        except Exception as exc:  # noqa: BLE001
            print(f"[agent-engine] off: {type(exc).__name__}", file=sys.stderr)
            _off = True
            return None
    return _memory


def enabled() -> bool:
    return _client() is not None


def _session(scope: str):
    from agent_engine_sdk_memory import MemoryRequestContext
    return _client().bind(MemoryRequestContext(user_id=scope, agent_id=AGENT_ID, session_id=SESSION_ID))


def _failed(where: str, exc: Exception) -> None:
    global _fails, _off
    _fails += 1
    print(f"[agent-engine] {where} failed ({_fails}/{FAIL_LIMIT}): {type(exc).__name__}",
          file=sys.stderr)
    if _fails >= FAIL_LIMIT:
        _off = True


def record_turn(scope: str, role: str, text: str) -> None:
    global _fails
    if _client() is None or role not in {"user", "assistant"} or not text:
        return
    try:
        _session(scope).record_turn(role=role, content=text[:8000])
        _fails = 0
    except Exception as exc:  # noqa: BLE001
        _failed("record", exc)


def context(scope: str, query: str) -> str:
    """Agent Engine's formatted context for this person and message, or ''."""
    global _fails
    if _client() is None or not query:
        return ""
    try:
        result = _session(scope).build_context(query=query[:2000], max_tokens=CONTEXT_TOKENS)
        _fails = 0
        return (getattr(result, "formatted_context", "") or "").strip()[:6000]
    except Exception as exc:  # noqa: BLE001
        _failed("context", exc)
        return ""
