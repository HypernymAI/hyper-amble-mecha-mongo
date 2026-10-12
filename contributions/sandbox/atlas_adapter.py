"""Resident-scoped reuse of the Presents Atlas mind, in a swarm process only.

The original module is loaded unchanged into private module state. Its database
access uses the swarm's bounded, auth-aware connection; no owner or visitor
scope, environment variables, or process-wide core module state is modified.
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
from pathlib import Path
import threading
from types import SimpleNamespace
from urllib.parse import quote


class _QuietErrors:
    def write(self, value):
        return len(value)

    def flush(self):
        pass


class AtlasAdapter:
    def __init__(self, config=None, *, database_getter):
        self._get_database = database_getter
        self._lock = threading.RLock()
        self._native = None
        self._busy = 0
        self._error = None
        self.configure(config or {})

    def configure(self, config):
        with self._lock:
            if self._busy:
                raise ValueError("A resident memory operation is running; retry Setup when it finishes")
            self._world_id = str(config.get("world_id") or "sandbox")
            self._database_name = str(config.get("mongodb_database") or config.get("database")
                                      or os.getenv("SANDBOX_MONGODB_DATABASE") or "amble_sandbox")
            self._key = str(config.get("voyage_api_key") or config.get("embedding_api_key")
                            or os.getenv("VOYAGE_API_KEY") or "")
            self._native_environment = dict(os.environ)
            native_model = config.get("voyage_model") or (
                config.get("embedding_model") if config.get("embedding_provider") == "voyage" else None)
            if native_model:
                self._native_environment["VOYAGE_MODEL"] = str(native_model)
            if config.get("voyage_base_url"):
                self._native_environment["VOYAGE_BASE_URL"] = str(config["voyage_base_url"])
            self._native = None
            self._indexes_ready = False
            self._error = None

    def scope(self, resident_id):
        if not isinstance(resident_id, str) or not resident_id.strip():
            raise ValueError("A nonempty resident_id is required")
        # Escape separators so distinct world/resident pairs cannot alias.
        return "sandbox:" + quote(self._world_id, safe="") + ":resident:" + quote(resident_id.strip(), safe="")

    def _module(self):
        if self._native is None:
            source = Path(__file__).resolve().parents[1] / "core" / "atlas_memory.py"
            spec = importlib.util.spec_from_file_location("sandbox._resident_atlas_native", source)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.DB_NAME = self._database_name
            module.db = self._database
            module._voyage_key = lambda: self._key
            # Chris's module otherwise reads provider configuration globally.
            module.os = SimpleNamespace(environ=self._native_environment)
            module.sys = SimpleNamespace(stderr=_QuietErrors())
            # Its original automatic backfill scans every scope. Derived memories
            # created by an explicit resident dream are already embedded in place.
            module._backfill_once = lambda _database: None
            original_parse = module._parse

            def checked_parse(text):
                parsed = original_parse(text)
                if not all(isinstance(parsed.get(key), list) for key in ("memories", "lessons", "retire")):
                    raise ValueError("Resident dream returned an invalid result; saved turns remain pending")
                return parsed

            module._parse = checked_parse
            self._native = module
        return self._native

    def _database(self):
        try:
            database = self._get_database()
            if database is not None and not self._indexes_ready:
                self._native._ensure_indexes(database)
                self._indexes_ready = True
            if database is None:
                self._error = "Resident Atlas memory is unavailable; local memory remains available"
            else:
                self._error = None
            return database
        except Exception:
            self._error = "Resident Atlas memory is unavailable; local memory remains available"
            return None

    def _start(self):
        with self._lock:
            module = self._module()
            self._busy += 1
            return module

    def _finish(self):
        with self._lock:
            self._busy -= 1

    def recall(self, resident_id, query):
        scope = self.scope(resident_id)
        module = self._start()
        try:
            return module.recall(scope, str(query))
        except Exception:
            self._error = "Resident recall is unavailable; local memory remains available"
            return {"memories": [], "lessons": [], "mode": "text"}
        finally:
            self._finish()

    def prompt_block(self, recalled):
        with self._lock:
            return self._module().prompt_block(recalled)

    def mind(self, resident_id):
        scope = self.scope(resident_id)
        module = self._start()
        try:
            return module.mind(scope)
        except Exception:
            self._error = "Resident mind is unavailable; local memory remains available"
            return {"enabled": False, "dreaming": False, "memories": [], "lessons": [],
                    "scores": [], "dreams": [], "stats": {}}
        finally:
            self._finish()

    async def dream(self, resident_id, *, backend, model):
        scope = self.scope(resident_id)
        module = self._start()
        try:
            with self._lock:
                if scope in module._dreaming:
                    return {"skipped": "resident is already dreaming"}
                module._dreaming.add(scope)
            try:
                if await asyncio.to_thread(self._database) is None:
                    return {"skipped": "resident memory is unavailable"}
                # Await the work: callers may own a short-lived asyncio.run loop.
                return await asyncio.wait_for(module.dream(scope, backend=backend, model=model), timeout=100.0)
            finally:
                module._dreaming.discard(scope)
        except Exception:
            self._error = "Resident dream failed; saved conversations are preserved"
            return {"error": self._error}
        finally:
            self._finish()

    def status(self):
        return {"ready": self._indexes_ready, "busy": self._busy > 0, "error": self._error}
