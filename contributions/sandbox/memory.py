"""Private resident recall and durable Atlas replication for the sandbox.

This module is independent of Amble's personal memory. Writes commit to SQLite
before returning; ``flush`` belongs on the sandbox's background worker. It never
downloads embedding models. Cached MiniLM is optional; the always-available
fallback is explicitly lexical, not semantic. Atlas vector indexes must include
``resident_id`` and ``embedding_model`` filter fields alongside ``embedding``.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sandbox.atlas_adapter import AtlasAdapter


LEXICAL_MODEL = "lexical-hash-v1-256"
LOCAL_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
VOYAGE_MODEL = "voyage-3.5-lite"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _lexical(text):
    """Stable term hashes, never Python's process-randomized hash()."""
    vector = [0.0] * 256
    for term in re.findall(r"\w+", text.casefold()):
        digest = hashlib.blake2b(term.encode("utf-8"), digest_size=8).digest()
        vector[int.from_bytes(digest[:4], "big") % 256] += 1.0
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


def _cosine(left, right):
    if len(left) != len(right):
        return 0.0
    norm = math.sqrt(sum(x * x for x in left) * sum(x * x for x in right))
    return sum(a * b for a, b in zip(left, right)) / norm if norm else 0.0


def _resident(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A nonempty resident_id is required")
    return value.strip()


class Memory:
    """SQLite cache/outbox with optional MongoDB and semantic embeddings."""

    def __init__(self, path, config=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._remote_lock = threading.RLock()
        self._db = sqlite3.connect(str(self.path), check_same_thread=False, timeout=3)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY, resident_id TEXT NOT NULL,
                document TEXT NOT NULL, embedding_pending INTEGER NOT NULL DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS resident_memories_local ON memories(resident_id);
            CREATE TABLE IF NOT EXISTS outbox (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                collection TEXT NOT NULL, document_id TEXT NOT NULL,
                document TEXT NOT NULL, version TEXT NOT NULL,
                UNIQUE(collection, document_id)
            );
            CREATE TABLE IF NOT EXISTS snapshots (
                collection TEXT NOT NULL, document_id TEXT NOT NULL,
                document TEXT NOT NULL, PRIMARY KEY(collection, document_id)
            );
            CREATE TABLE IF NOT EXISTS native_mirrors (
                memory_id TEXT NOT NULL, scope TEXT NOT NULL, database_name TEXT NOT NULL,
                PRIMARY KEY(memory_id, scope, database_name)
            );
        """)
        self._client = None
        self._mongo = None
        self._model = None
        self._model_attempted = False
        self._connected = False
        self._mongo_error = None
        self._embedding_error = None
        self._embedding_provider = "lexical"
        self._embedding_model = LEXICAL_MODEL
        self._retrieval_path = "local_lexical"
        self._vector_status = "not_configured"
        self._last_sync = None
        self._config = {}
        self.atlas = AtlasAdapter(config or {}, database_getter=self._native_database)
        self.configure(config or {})

    def configure(self, config):
        """Accept private configuration; return only safe operational status."""
        with self._remote_lock:
            self.atlas.configure(config)
            previous = self._config
            self._config = dict(config)
            self._uri = str(config.get("mongodb_uri") or os.getenv("SANDBOX_MONGODB_URI")
                            or os.getenv("MONGODB_URI") or "").strip()
            self._database = str(config.get("mongodb_database") or config.get("database")
                                 or os.getenv("SANDBOX_MONGODB_DATABASE") or "amble_sandbox")
            self._voyage_key = str(config.get("voyage_api_key") or config.get("embedding_api_key")
                                   or os.getenv("VOYAGE_API_KEY") or "")
            self._provider = str(config.get("embedding_provider") or "auto").lower()
            self._voyage_model = str(config.get("embedding_model") or VOYAGE_MODEL)
            self._vector_index = str(config.get("mongodb_vector_index")
                                     or config.get("vector_index") or "")
            if self._client is not None:
                self._client.close()
            self._client = None
            self._mongo = None
            self._connected = False
            self._mongo_error = None
            self._auth_failed = False
            self._next_connect_at = 0.0
            self._vector_status = "pending" if self._vector_index else "not_configured"
            if previous != self._config:
                self._model = None
                self._model_attempted = False
                self._embedding_error = None
                self._embedding_provider, self._embedding_model = "lexical", LEXICAL_MODEL
                with self._lock, self._db:
                    self._db.execute("UPDATE memories SET embedding_pending=1")
            with self._lock, self._db:
                for row in self._db.execute("SELECT document FROM memories").fetchall():
                    self._mirror_native(json.loads(row[0]))
            return self.status()

    def _native_database(self):
        with self._remote_lock:
            return self._connect()

    def _mirror_native(self, document):
        if document.get("kind") not in {"chat", "job_prompt", "job_reply", "import"}:
            return
        scope = self.atlas.scope(document["resident_id"])
        cursor = self._db.execute(
            "INSERT OR IGNORE INTO native_mirrors(memory_id,scope,database_name) VALUES(?,?,?)",
            (document["_id"], scope, self._database),
        )
        if not cursor.rowcount:
            return
        turn_id = hashlib.sha256((scope + "\0" + document["_id"]).encode("utf-8")).hexdigest()
        self._enqueue("turns", {
            "_id": "swarm-turn:" + turn_id, "scope": scope,
            "role": document["role"], "text": document["text"],
            "ts": document["created_at"], "dreamed": False,
            "origin": "sandbox", "resident_id": document["resident_id"],
            "source_memory_id": document["_id"], "kind": document["kind"],
        })

    def _enqueue(self, collection, document):
        self._db.execute(
            "INSERT INTO outbox(collection,document_id,document,version) VALUES(?,?,?,?) "
            "ON CONFLICT(collection,document_id) DO UPDATE SET document=excluded.document,version=excluded.version",
            (collection, document["_id"], _json(document), uuid.uuid4().hex),
        )

    def record(self, resident_id, role, text, kind="chat", metadata=None):
        """Commit locally without making network calls or loading a model."""
        resident_id = _resident(resident_id)
        if not isinstance(text, str) or not isinstance(role, str):
            raise ValueError("role and text must be strings")
        document = {
            "_id": uuid.uuid4().hex, "resident_id": resident_id, "role": role,
            "text": text, "kind": str(kind), "metadata": dict(metadata or {}),
            "created_at": _now(), "embedding": _lexical(text),
            "embedding_provider": "lexical", "embedding_model": LEXICAL_MODEL,
            "embedding_dimensions": 256,
        }
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO memories(id,resident_id,document) VALUES(?,?,?)",
                (document["_id"], resident_id, _json(document)),
            )
            self._enqueue("resident_memories", document)
            self._mirror_native(document)
        return document

    def recent(self, resident_id, limit=30):
        resident_id = _resident(resident_id)
        with self._lock:
            rows = self._db.execute(
                "SELECT document FROM memories WHERE resident_id=? ORDER BY rowid DESC LIMIT ?",
                (resident_id, max(0, min(int(limit), 1000))),
            ).fetchall()
        return [json.loads(row[0]) for row in reversed(rows)]

    def _cached_model_path(self):
        # A user-selected local path is allowed; no remote model ID is accepted.
        explicit = self._config.get("local_embedding_path")
        if explicit:
            candidate = Path(explicit).expanduser()
            return candidate if candidate.is_dir() else None
        hub = Path(os.getenv("HF_HUB_CACHE") or
                   (Path(os.getenv("HF_HOME", str(Path.home() / ".cache/huggingface"))) / "hub"))
        snapshots = hub / "models--sentence-transformers--all-MiniLM-L6-v2" / "snapshots"
        if snapshots.is_dir():
            for candidate in sorted(snapshots.iterdir(), reverse=True):
                if (candidate / "modules.json").is_file():
                    return candidate
        return None

    def _load_model(self):
        if self._model_attempted:
            return
        self._model_attempted = True
        model_path = self._cached_model_path()
        if model_path is None:
            self._embedding_error = "No cached local model; lexical recall is active"
            return
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(str(model_path), local_files_only=True, device="cpu")
        except Exception:
            # Provider errors may contain credentials or private paths.
            self._embedding_error = "Local embedding model unavailable; lexical recall is active"

    def _embed(self, text, query=False):
        if self._provider == "voyage":
            if not self._voyage_key:
                self._embedding_error = "Voyage key missing; lexical recall is active"
            else:
                try:
                    import httpx
                    response = httpx.post(
                        "https://api.voyageai.com/v1/embeddings",
                        headers={"Authorization": "Bearer " + self._voyage_key},
                        json={"input": [text], "model": self._voyage_model,
                              "input_type": "query" if query else "document"}, timeout=3.0,
                    )
                    response.raise_for_status()
                    vector = [float(x) for x in response.json()["data"][0]["embedding"]]
                    if not vector or not all(math.isfinite(x) for x in vector):
                        raise ValueError("Invalid vector")
                    self._embedding_error = None
                    self._embedding_provider, self._embedding_model = "voyage", self._voyage_model
                    return vector, "voyage", self._voyage_model
                except Exception:
                    self._embedding_error = "Voyage embedding unavailable; lexical recall is active"
        elif self._provider != "lexical":
            self._load_model()
            if self._model is not None:
                try:
                    vector = [float(x) for x in self._model.encode(text, normalize_embeddings=True)]
                    self._embedding_error = None
                    self._embedding_provider, self._embedding_model = "local", LOCAL_MODEL
                    return vector, "local", LOCAL_MODEL
                except Exception:
                    self._embedding_error = "Local embedding failed; lexical recall is active"
        self._embedding_provider, self._embedding_model = "lexical", LEXICAL_MODEL
        return _lexical(text), "lexical", LEXICAL_MODEL

    def _connect(self):
        if not self._uri or self._auth_failed or time.monotonic() < self._next_connect_at:
            return None
        if self._mongo is not None and self._connected:
            return self._mongo
        try:
            from pymongo import MongoClient
            if self._client is None:
                self._client = MongoClient(
                    self._uri, serverSelectionTimeoutMS=2500, connectTimeoutMS=2500,
                    socketTimeoutMS=2500, timeoutMS=3000, appname="amble-sandbox",
                    connect=False,
                )
            self._client.admin.command("ping")
            self._mongo = self._client[self._database]
            self._connected = True
            self._mongo_error = None
            return self._mongo
        except ImportError as error:
            self._connection_failed(error, "MongoDB driver unavailable; writes remain safely queued locally")
        except Exception as error:
            self._connection_failed(error, "MongoDB unavailable; check the URI, network, and Atlas access settings")
        return None

    def _connection_failed(self, error, message):
        """Keep credentials opaque and avoid retrying rejected authentication."""
        try:
            from pymongo.errors import OperationFailure
            rejected = isinstance(error, OperationFailure) and error.code in (18, 8000)
        except ImportError:
            rejected = False
        self._connected = False
        if rejected:
            self._auth_failed = True
            self._mongo_error = "Atlas rejected the database credentials; update them in Setup"
        else:
            self._next_connect_at = time.monotonic() + 15.0
            self._mongo_error = message

    def _upgrade_embeddings(self, limit):
        with self._lock:
            rows = self._db.execute(
                "SELECT id,document FROM memories WHERE embedding_pending=1 ORDER BY rowid LIMIT ?",
                (limit,),
            ).fetchall()
        upgraded = 0
        for row in rows:
            document = json.loads(row["document"])
            vector, provider, model = self._embed(document["text"])
            document.update(embedding=vector, embedding_provider=provider,
                            embedding_model=model, embedding_dimensions=len(vector))
            # Transient Voyage failures stay pending and retry on a later flush.
            retry = self._provider == "voyage" and provider != "voyage"
            with self._lock, self._db:
                self._db.execute("UPDATE memories SET document=?,embedding_pending=? WHERE id=?",
                                 (_json(document), int(retry), row["id"]))
                self._enqueue("resident_memories", document)
            upgraded += int(provider != "lexical")
            if retry:
                break
        return upgraded

    def flush(self, limit=100):
        """Run in a background worker: enrich vectors and retry durable upserts."""
        limit = max(0, min(int(limit), 1000))
        with self._remote_lock:
            upgraded = self._upgrade_embeddings(limit)
            mongo = self._connect()
            sent = 0
            if mongo is not None:
                with self._lock:
                    pending = self._db.execute("SELECT * FROM outbox ORDER BY seq LIMIT ?", (limit,)).fetchall()
                for row in pending:
                    try:
                        document = json.loads(row["document"])
                        if row["collection"] == "turns":
                            document["ts"] = datetime.fromisoformat(document["ts"])
                            result = mongo["turns"].update_one(
                                {"_id": row["document_id"]}, {"$setOnInsert": document}, upsert=True)
                        else:
                            result = mongo[row["collection"]].replace_one(
                                {"_id": row["document_id"]}, document, upsert=True)
                        if not result.acknowledged:
                            raise RuntimeError("MongoDB write was not acknowledged")
                        with self._lock, self._db:
                            self._db.execute("DELETE FROM outbox WHERE seq=? AND version=?",
                                             (row["seq"], row["version"]))
                        self._connected = True
                        self._mongo_error = None
                        self._last_sync = _now()
                        sent += 1
                    except Exception as error:
                        self._connection_failed(error, "MongoDB write failed; writes remain safely queued locally")
                        break
            return dict(self.status(), sent=sent, embeddings_upgraded=upgraded)

    def recall(self, resident_id, query, limit=6):
        resident_id = _resident(resident_id)
        limit = max(0, min(int(limit), 100))
        if not limit:
            return []
        with self._remote_lock:
            vector, provider, model = self._embed(str(query), query=True)
            documents = {}
            with self._lock:
                rows = self._db.execute("SELECT document FROM memories WHERE resident_id=?", (resident_id,)).fetchall()
            for row in rows:
                document = json.loads(row[0])
                documents[document["_id"]] = document
            self._retrieval_path = "local_semantic" if provider != "lexical" else "local_lexical"
            # Only attempt Atlas on an already verified connection. A down server
            # does not put a reconnect delay in every conversational turn.
            if self._mongo is not None and self._connected:
                try:
                    collection = self._mongo["resident_memories"]
                    if self._vector_index:
                        pipeline = [{"$vectorSearch": {
                            "index": self._vector_index, "path": "embedding", "queryVector": vector,
                            "numCandidates": max(100, limit * 20), "limit": limit,
                            "filter": {"resident_id": resident_id, "embedding_model": model},
                        }}]
                        remote = list(collection.aggregate(pipeline, maxTimeMS=2000))
                        self._vector_status = "available"
                        self._retrieval_path = "atlas_vector_search"
                    else:
                        remote = list(collection.find({"resident_id": resident_id}).limit(2000).max_time_ms(2000))
                        self._retrieval_path = "mongo_local_cosine"
                    for document in remote:
                        # Defense in depth, even if a driver/test double returns
                        # rows violating the mandatory database tenant filter.
                        if document.get("resident_id") == resident_id:
                            documents.setdefault(document["_id"], document)
                except Exception as error:
                    if self._vector_index:
                        self._vector_status = "unavailable"
                    self._connection_failed(error, "MongoDB recall unavailable; using the durable local cache")
            lexical_query = _lexical(str(query))
            results = []
            for document in documents.values():
                if document.get("resident_id") != resident_id:
                    continue
                if document.get("embedding_model") == model:
                    score = _cosine(vector, document.get("embedding", []))
                    mode = "semantic" if provider != "lexical" else "lexical"
                else:
                    score = _cosine(lexical_query, _lexical(document.get("text", "")))
                    mode = "lexical"
                result = dict(document, score=round(score, 6), recall_mode=mode)
                results.append(result)
            results.sort(key=lambda item: (item["score"], item.get("created_at", "")), reverse=True)
            return results[:limit]

    def sync_world(self, snapshot):
        """Queue shared world state, resident snapshots, and immutable receipts."""
        if not isinstance(snapshot, dict):
            raise ValueError("World snapshot must be an object")
        world_id = str(snapshot.get("world_id") or snapshot.get("id") or "sandbox")
        now = _now()
        documents = [("world_state", dict(snapshot, _id=world_id, updated_at=now))]
        residents = snapshot.get("residents", [])
        if isinstance(residents, dict):
            residents = [dict(value, id=key) for key, value in residents.items() if isinstance(value, dict)]
        for resident in residents:
            if not isinstance(resident, dict):
                continue
            identity = resident.get("resident_id") or resident.get("id")
            if not identity:
                continue
            resident_id = _resident(str(identity))
            documents.append(("resident_state", dict(resident, _id=world_id + ":" + resident_id,
                                                       world_id=world_id, resident_id=resident_id, updated_at=now)))
        for event in snapshot.get("events", snapshot.get("feed", [])):
            if not isinstance(event, dict):
                continue
            canonical = json.dumps(event, ensure_ascii=False, sort_keys=True, allow_nan=False)
            event_id = str(event.get("id") or event.get("_id") or
                           hashlib.sha256(canonical.encode("utf-8")).hexdigest())
            documents.append(("world_events", dict(event, _id=world_id + ":" + event_id, world_id=world_id)))
        with self._lock, self._db:
            for collection, document in documents:
                packed = _json(document)
                # Event receipts retain the first observed payload for an ID.
                existing = self._db.execute("SELECT document FROM snapshots WHERE collection=? AND document_id=?",
                                            (collection, document["_id"])).fetchone()
                if collection == "world_events" and existing is not None:
                    continue
                self._db.execute(
                    "INSERT INTO snapshots(collection,document_id,document) VALUES(?,?,?) "
                    "ON CONFLICT(collection,document_id) DO UPDATE SET document=excluded.document",
                    (collection, document["_id"], packed),
                )
                self._enqueue(collection, document)
        return self.status()

    def sync_simulation(self, payload):
        """Durably queue bounded synthetic summaries outside resident memory."""
        from sandbox.economy import atlas_documents
        documents = list(atlas_documents(payload))
        with self._lock, self._db:
            for collection, document in documents:
                packed = _json(document)
                self._db.execute(
                    "INSERT INTO snapshots(collection,document_id,document) VALUES(?,?,?) "
                    "ON CONFLICT(collection,document_id) DO UPDATE SET document=excluded.document",
                    (collection, document["_id"], packed),
                )
                self._enqueue(collection, document)
        return {"queued_documents": len(documents)}

    def status(self):
        with self._lock:
            pending = self._db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
            count = self._db.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            embeddings_pending = self._db.execute("SELECT COUNT(*) FROM memories WHERE embedding_pending=1").fetchone()[0]
        return {
            "configured": bool(self._uri), "connected": self._connected,
            "state": ("auth_failed" if self._auth_failed else "connected" if self._connected
                      else "pending" if self._uri else "local"),
            "auth_failed": self._auth_failed,
            "retry_after_seconds": max(0, math.ceil(self._next_connect_at - time.monotonic())),
            "pending": pending, "memories": count, "embeddings_pending": embeddings_pending,
            "embedding_provider": self._embedding_provider, "embedding_model": self._embedding_model,
            "semantic": self._embedding_provider != "lexical", "embedding_error": self._embedding_error,
            "retrieval_path": self._retrieval_path, "vector_search": self._vector_status,
            "last_sync": self._last_sync, "error": self._mongo_error,
        }

    def close(self):
        with self._remote_lock:
            if self._client is not None:
                self._client.close()
            with self._lock:
                self._db.close()
