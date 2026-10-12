"""Sandbox memory durability, isolation, and offline Atlas protocol checks."""
from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime
import copy
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sandbox.memory import Memory, LEXICAL_MODEL


class FakeCursor(list):
    def limit(self, limit):
        return FakeCursor(self[:limit])

    def max_time_ms(self, _timeout):
        return self


class FakeCollection:
    def __init__(self):
        self.documents = {}
        self.fail_after_write = False
        self.unacknowledged = False
        self.pipeline = None
        self.on_write = None

    def replace_one(self, selector, document, upsert):
        assert selector == {"_id": document["_id"]} and upsert
        self.documents[document["_id"]] = json.loads(json.dumps(document))
        if self.on_write:
            action, self.on_write = self.on_write, None
            action()
        if self.fail_after_write:
            self.fail_after_write = False
            raise RuntimeError("Do not leak mongodb://private:secret@hostname or an API key")
        return types.SimpleNamespace(acknowledged=not self.unacknowledged)

    def update_one(self, selector, change, upsert):
        document = change["$setOnInsert"]
        assert selector == {"_id": document["_id"]} and upsert
        self.documents.setdefault(document["_id"], copy.deepcopy(document))
        return types.SimpleNamespace(acknowledged=not self.unacknowledged)

    def find(self, selector):
        assert "resident_id" in selector
        return FakeCursor(d for d in self.documents.values() if d["resident_id"] == selector["resident_id"])

    def aggregate(self, pipeline, maxTimeMS):
        self.pipeline = pipeline
        # Deliberately return another tenant too to test post-filter defense.
        return list(self.documents.values())


class FakeDatabase:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        return self.collections.setdefault(name, FakeCollection())


class FakeClient:
    database = None
    calls = []
    ping_fails = False
    ping_calls = 0
    auth_error = None

    def __init__(self, uri, **kwargs):
        type(self).calls.append(kwargs)
        self.admin = self

    def command(self, command):
        assert command == "ping"
        type(self).ping_calls += 1
        if self.auth_error is not None:
            raise self.auth_error
        if self.ping_fails:
            raise RuntimeError("mongodb://private:secret@hostname")

    def __getitem__(self, name):
        return self.database

    def close(self):
        pass


class FakeOperationFailure(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


class TestSwarmMemory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "memory.sqlite3"
        self.env = patch.dict(os.environ, {"MONGODB_URI": "", "SANDBOX_MONGODB_URI": "", "VOYAGE_API_KEY": ""})
        self.env.start()
        self.config = {"embedding_provider": "lexical"}
        self.memory = Memory(self.path, self.config)
        FakeClient.database, FakeClient.calls, FakeClient.ping_fails = FakeDatabase(), [], False
        FakeClient.ping_calls, FakeClient.auth_error = 0, None
        self.driver = patch.dict(sys.modules, {
            "pymongo": types.SimpleNamespace(MongoClient=FakeClient),
            "pymongo.errors": types.SimpleNamespace(OperationFailure=FakeOperationFailure),
        })
        self.driver.start()

    def tearDown(self):
        self.memory.close()
        self.driver.stop()
        self.env.stop()
        self.tmp.cleanup()

    def connect(self, **extra):
        self.memory.configure(dict(self.config, mongodb_uri="mongodb://private:secret@hostname", **extra))

    def test_record_is_local_durable_with_real_float_vectors(self):
        with patch.object(self.memory, "_embed", side_effect=AssertionError("No model or network in record")):
            first = self.memory.record("alba", "user", "Orchard peaches grow in the sunlight")
            self.memory.record("alba", "assistant", "I'll remember the orchard")
        self.assertEqual(len(first["embedding"]), 256)
        self.assertTrue(all(isinstance(value, float) for value in first["embedding"]))
        self.assertEqual(first["embedding_model"], LEXICAL_MODEL)
        self.memory.close()
        self.memory = Memory(self.path, self.config)
        self.assertEqual([row["role"] for row in self.memory.recent("alba")], ["user", "assistant"])
        self.assertEqual(self.memory.status()["pending"], 4)
        self.assertEqual(self.memory.recent("alba")[0]["embedding"], first["embedding"])

    def test_resident_isolation_and_lexical_ranking(self):
        self.memory.record("alba", "user", "apples orchard apples")
        self.memory.record("alba", "user", "deep space rockets")
        self.memory.record("beau", "user", "apples orchard private secret")
        recalled = self.memory.recall("alba", "apples orchard", limit=10)
        self.assertEqual(len(recalled), 2)
        self.assertEqual(recalled[0]["text"], "apples orchard apples")
        self.assertTrue(all(row["resident_id"] == "alba" for row in recalled))
        self.assertTrue(all(row["recall_mode"] == "lexical" for row in recalled))
        self.assertFalse(self.memory.status()["semantic"])
        self.assertEqual(self.memory.status()["retrieval_path"], "local_lexical")

    def test_empty_identity_is_always_rejected(self):
        for identity in (None, "", "   "):
            for operation in (lambda: self.memory.record(identity, "user", "hi"),
                              lambda: self.memory.recent(identity), lambda: self.memory.recall(identity, "hi")):
                with self.assertRaises(ValueError):
                    operation()

    def test_offline_flush_keeps_outbox_and_safe_status(self):
        self.memory.record("alba", "user", "Local memory persists")
        status = self.memory.flush()
        self.assertFalse(status["connected"])
        self.assertEqual(status["state"], "local")
        self.assertEqual(status["pending"], 2)
        self.connect()
        FakeClient.ping_fails = True
        status = self.memory.flush()
        self.assertFalse(status["connected"])
        self.assertEqual(status["state"], "pending")
        self.assertEqual(status["pending"], 2)
        self.assertNotIn("secret", json.dumps(status))
        self.assertNotIn("hostname", json.dumps(status))
        self.assertLessEqual(FakeClient.calls[-1]["serverSelectionTimeoutMS"], 3000)
        self.assertLessEqual(FakeClient.calls[-1]["timeoutMS"], 3000)

    def test_missing_driver_does_not_lose_outbox(self):
        self.connect()
        self.memory.record("alba", "user", "still here")
        with patch.dict(sys.modules, {"pymongo": None}):
            status = self.memory.flush()
        self.assertEqual(status["pending"], 2)
        self.assertFalse(status["connected"])
        self.assertIn("driver unavailable", status["error"])

    def test_uncertain_write_retry_is_idempotent(self):
        self.connect()
        record = self.memory.record("alba", "user", "persist once")
        collection = FakeClient.database["resident_memories"]
        collection.fail_after_write = True
        with patch("sandbox.memory.time.monotonic", return_value=1000):
            failed = self.memory.flush()
        self.assertEqual(failed["pending"], 2)
        self.assertFalse(failed["connected"])
        self.assertNotIn("secret", json.dumps(failed))
        with patch("sandbox.memory.time.monotonic", return_value=1016):
            succeeded = self.memory.flush()
        self.assertEqual(succeeded["pending"], 0)
        self.assertEqual(succeeded["sent"], 2)
        self.assertTrue(succeeded["connected"])
        self.assertEqual(list(collection.documents), [record["_id"]])

    def test_rejected_authentication_waits_for_configuration(self):
        self.memory.record("alba", "user", "local memory stays available")
        for code in (18, 8000):
            self.connect()
            FakeClient.auth_error = FakeOperationFailure("private:secret@hostname", code)
            before = FakeClient.ping_calls
            first = self.memory.flush()
            second = self.memory.flush()
            self.assertEqual(FakeClient.ping_calls, before + 1)
            self.assertEqual(first["state"], "auth_failed")
            self.assertTrue(second["auth_failed"])
            self.assertFalse(second["connected"])
            self.assertEqual(second["error"], "Atlas rejected the database credentials; update them in Setup")
            self.assertNotIn("secret", json.dumps(second))
            self.assertNotIn("hostname", json.dumps(second))
            self.assertEqual(len(self.memory.recent("alba")), 1)
            self.assertEqual(second["pending"], 2)
        FakeClient.auth_error = None
        self.connect()
        self.assertFalse(self.memory.status()["auth_failed"])
        self.assertTrue(self.memory.flush()["connected"])
        self.assertEqual(self.memory.status()["pending"], 0)

    def test_network_failure_backs_off_without_blocking_local_records(self):
        self.connect()
        FakeClient.ping_fails = True
        with patch("sandbox.memory.time.monotonic", return_value=1000):
            first = self.memory.flush()
            self.memory.record("alba", "user", "written during network outage")
            second = self.memory.flush()
        self.assertEqual(FakeClient.ping_calls, 1)
        self.assertEqual(first["retry_after_seconds"], 15)
        self.assertEqual(second["pending"], 2)
        FakeClient.ping_fails = False
        with patch("sandbox.memory.time.monotonic", return_value=1016):
            self.assertTrue(self.memory.flush()["connected"])
        self.assertEqual(FakeClient.ping_calls, 2)

    def test_unacknowledged_write_remains_pending(self):
        self.connect()
        self.memory.record("alba", "user", "never silently discard")
        FakeClient.database["resident_memories"].unacknowledged = True
        self.assertEqual(self.memory.flush()["pending"], 2)

    def test_embedding_upgrade_persists_locally_and_in_mongo(self):
        self.connect()
        record = self.memory.record("alba", "user", "meaningful memory")
        with patch.object(self.memory, "_embed", return_value=([0.25, 0.5, 0.75], "local", "test-model")):
            self.assertEqual(self.memory.flush()["embeddings_upgraded"], 1)
        local = self.memory.recent("alba")[0]
        remote = FakeClient.database["resident_memories"].documents[record["_id"]]
        self.assertEqual(local["embedding"], [0.25, 0.5, 0.75])
        self.assertEqual(remote["embedding"], local["embedding"])
        self.assertEqual(remote["embedding_dimensions"], 3)

    def test_atlas_vector_search_always_filters_identity_and_model(self):
        self.connect(vector_index="sandbox_vector")
        self.memory.record("alba", "user", "garden")
        self.memory.record("beau", "user", "garden secret")
        self.memory.flush()
        results = self.memory.recall("alba", "garden")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["resident_id"], "alba")
        stage = FakeClient.database["resident_memories"].pipeline[0]["$vectorSearch"]
        self.assertEqual(stage["filter"], {"resident_id": "alba", "embedding_model": LEXICAL_MODEL})
        self.assertEqual(stage["path"], "embedding")
        self.assertEqual(self.memory.status()["retrieval_path"], "atlas_vector_search")

    def test_shared_world_and_residents_are_durable_distinct_collections(self):
        snapshot = {"id": "world-a", "residents": [{"id": "alba", "energy": 50}, {"id": "beau"}],
                    "events": [{"id": "event-1", "action": "planted"}]}
        self.memory.sync_world(snapshot)
        self.memory.sync_world(snapshot)
        self.assertEqual(self.memory.status()["pending"], 4)
        self.connect()
        result = self.memory.flush()
        self.assertEqual(result["pending"], 0)
        self.assertEqual(len(FakeClient.database["resident_state"].documents), 2)
        self.assertEqual(len(FakeClient.database["world_events"].documents), 1)
        self.assertIn("world-a", FakeClient.database["world_state"].documents)
        self.memory.sync_world(snapshot)
        self.assertEqual(self.memory.status()["pending"], 3)  # no repeated event receipt

    def test_world_update_during_network_write_is_not_dropped(self):
        self.connect()
        self.memory.sync_world({"id": "w", "tick": 1})
        FakeClient.database["world_state"].on_write = lambda: self.memory.sync_world({"id": "w", "tick": 2})
        self.assertEqual(self.memory.flush()["pending"], 1)
        self.assertEqual(self.memory.flush()["pending"], 0)
        self.assertEqual(FakeClient.database["world_state"].documents["w"]["tick"], 2)

    def test_world_feed_generates_event_receipts(self):
        self.memory.sync_world({"id": "w", "feed": [{"id": "event-1", "action": "planted"}]})
        self.connect()
        self.memory.flush()
        self.assertIn("w:event-1", FakeClient.database["world_events"].documents)

    def test_native_turn_mirror_preserves_dream_state(self):
        self.connect(world_id="world-a")
        record = self.memory.record("alba", "user", "remember the garden", kind="job_prompt")
        self.memory.flush()
        turns = FakeClient.database["turns"].documents
        self.assertEqual(len(turns), 1)
        turn = next(iter(turns.values()))
        self.assertEqual(turn["scope"], "sandbox:world-a:resident:alba")
        self.assertEqual(turn["source_memory_id"], record["_id"])
        self.assertIsInstance(turn["ts"], datetime)
        self.assertIsNotNone(turn["ts"].tzinfo)
        turn["dreamed"] = True
        with self.memory._lock, self.memory._db:
            self.memory._enqueue("turns", dict(turn, dreamed=False, ts=turn["ts"].isoformat()))
        self.memory.flush()
        self.assertTrue(next(iter(turns.values()))["dreamed"])
        self.connect(world_id="world-a")
        self.memory.flush()
        self.assertEqual(len(turns), 1)
        self.assertTrue(next(iter(turns.values()))["dreamed"])

    def test_legacy_cache_backfills_native_turns_once(self):
        record = self.memory.record("alba", "assistant", "old cached reply", kind="import")
        with self.memory._lock, self.memory._db:
            # Simulate a pre-integration cache whose resident memory was synced.
            self.memory._db.execute("DELETE FROM native_mirrors")
            self.memory._db.execute("DELETE FROM outbox")
        self.connect()
        self.memory.flush()
        turns = FakeClient.database["turns"].documents
        self.assertEqual(len(turns), 1)
        self.assertEqual(next(iter(turns.values()))["source_memory_id"], record["_id"])
        self.memory.close()
        self.memory = Memory(self.path, dict(self.config, mongodb_uri="mongodb://private:secret@hostname"))
        self.memory.flush()
        self.assertEqual(len(turns), 1)

    def test_no_cached_model_never_downloads(self):
        self.memory.configure({"embedding_provider": "local"})
        self.memory.record("alba", "user", "offline words")
        with patch.object(self.memory, "_cached_model_path", return_value=None), \
                patch.dict(sys.modules, {"sentence_transformers": None}):
            result = self.memory.flush()
        self.assertFalse(result["semantic"])
        self.assertEqual(result["embedding_provider"], "lexical")
        self.assertIn("No cached local model", result["embedding_error"])

    def test_voyage_failure_remains_pending_without_secrets(self):
        self.memory.configure({"embedding_provider": "voyage", "voyage_api_key": "private-api-key"})
        self.memory.record("alba", "user", "retry embeddings")
        with patch("httpx.post", side_effect=RuntimeError("private-api-key")):
            result = self.memory.flush()
        self.assertEqual(result["embeddings_pending"], 1)
        self.assertEqual(result["embedding_provider"], "lexical")
        self.assertNotIn("private-api-key", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
