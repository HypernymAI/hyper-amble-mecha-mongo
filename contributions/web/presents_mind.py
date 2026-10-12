"""Presents mind — what Amble remembers about one link, read from Atlas.

Two more handlers in the unauthenticated ``presents_*`` family
(``web/api.py`` registers them in ``PRESENTS_VISITOR_HANDLERS``):
``presents_mind`` returns ``core.atlas_memory.mind(scope)`` and
``presents_dream`` asks for a dream now. The link token is the only
credential and the scope is always ``"visitor:" + link id``, so a visitor
only ever sees their own link's memories. Only a chat-enabled link may look.
Fail-soft: an Atlas problem reads as an empty, disabled mind, never a
traceback.
"""
from __future__ import annotations

import asyncio
import sys

from core import presents_links

_EMPTY = {"enabled": False, "dreaming": False, "stats": {"turns": 0, "memories": 0, "lessons": 0, "dreams": 0},
          "memories": [], "lessons": [], "dreams": [], "scores": [],
          "improvement": {"before_avg": None, "after_avg": None, "n_before": 0, "n_after": 0}}


def _reply(ok: bool, **fields) -> dict:
    return {"type": "presents_mind_reply", "ok": ok, **fields}


def _scope(msg: dict):
    """(scope, None) for a chat-enabled link, else (None, refusal)."""
    link = presents_links.resolve(msg.get("k"))
    if link is None or not link.get("chat"):
        return None, _reply(False, error="link", note="This link cannot chat.")
    return "visitor:" + str(link["id"]), None


async def handle_mind(msg: dict, visit: dict) -> dict:
    scope, refusal = _scope(msg)
    if refusal:
        return refusal
    from core import atlas_memory
    try:
        mind = await asyncio.to_thread(atlas_memory.mind, scope)
    except Exception as exc:  # noqa: BLE001 — memory never breaks the page
        print(f"[presents] mind unavailable: {type(exc).__name__}: {str(exc)[:200]}", file=sys.stderr)
        mind = dict(_EMPTY)
    return _reply(True, mind=mind if isinstance(mind, dict) else dict(_EMPTY))


async def handle_dream(msg: dict, visit: dict) -> dict:
    scope, refusal = _scope(msg)
    if refusal:
        return refusal
    from core import atlas_memory
    from core.engine import presents_backend, presents_model
    from bridges.model_bridge import get_default_model
    try:
        backend = presents_backend()
        model = presents_model() or get_default_model(backend)
        await asyncio.to_thread(atlas_memory.enabled)  # first db() connect blocks; do it off the loop
        started = bool(atlas_memory.request_dream(scope, backend=backend, model=model))
    except Exception as exc:  # noqa: BLE001
        print(f"[presents] dream unavailable: {type(exc).__name__}: {str(exc)[:200]}", file=sys.stderr)
        started = False
    return _reply(True, started=started)
