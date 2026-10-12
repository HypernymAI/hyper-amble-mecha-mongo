"""Resident-scoped Chris memory integration without MongoDB or inference."""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sandbox.atlas_adapter import AtlasAdapter


class TestAtlasAdapter(unittest.TestCase):
    def setUp(self):
        self.database = object()
        self.adapter = AtlasAdapter({"world_id": "w", "database": "amble_sandbox"},
                                    database_getter=lambda: self.database)
        self.native = self.adapter._module()
        self.native._ensure_indexes = Mock()

    def test_separate_scopes_and_namespace(self):
        self.assertEqual(self.adapter.scope("alba"), "sandbox:w:resident:alba")
        self.assertNotEqual(self.adapter.scope("alba"), self.adapter.scope("beau"))
        self.assertEqual(self.native.DB_NAME, "amble_sandbox")
        self.assertIs(self.native.db(), self.database)
        self.native._ensure_indexes.assert_called_once_with(self.database)
        for value in ("", " ", None):
            with self.assertRaises(ValueError):
                self.adapter.scope(value)
        self.assertEqual(self.adapter.scope("owner"), "sandbox:w:resident:owner")
        other = AtlasAdapter({"world_id": "w:resident:x"}, database_getter=lambda: None)
        self.assertNotEqual(self.adapter.scope("x:resident:y"), other.scope("y"))

    def test_recall_and_mind_reuse_native_api_with_resident_scope(self):
        recalled = {"memories": [{"id": "m", "kind": "fact", "when": "2026-10-11", "text": "Garden"}],
                    "lessons": [], "mode": "text"}
        self.native.recall = Mock(return_value=recalled)
        self.native.mind = Mock(return_value={"enabled": True, "memories": []})
        self.assertEqual(self.adapter.recall("alba", "garden"), recalled)
        self.native.recall.assert_called_once_with("sandbox:w:resident:alba", "garden")
        self.adapter.mind("beau")
        self.native.mind.assert_called_once_with("sandbox:w:resident:beau")
        self.assertIn("Garden", self.adapter.prompt_block(recalled))
        self.assertFalse(self.adapter.status()["busy"])

    def test_no_global_scope_backfill_or_environment_mutation(self):
        with patch.dict("os.environ", {"VOYAGE_API_KEY": "unchanged-environment-secret"}):
            adapter = AtlasAdapter({"voyage_api_key": "configured-secret", "embedding_model": "voyage-3.5-lite"},
                                   database_getter=lambda: None)
            module = adapter._module()
            self.assertEqual(module._voyage_key(), "configured-secret")
            self.assertEqual(__import__("os").environ["VOYAGE_API_KEY"], "unchanged-environment-secret")
            dangerous_database = Mock()
            module._backfill_once(dangerous_database)
            self.assertEqual(dangerous_database.mock_calls, [])
            self.assertNotIn("secret", json.dumps(adapter.status()))

    def test_native_source_is_preserved(self):
        path = Path(__file__).resolve().parents[1] / "core" / "atlas_memory.py"
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        self.adapter._module()
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
        self.assertNotEqual(self.native.__name__, "core.atlas_memory")

    def test_native_provider_environment_is_independent_of_local_vectors(self):
        with patch.dict("os.environ", {"VOYAGE_MODEL": "chris-native-model", "VOYAGE_BASE_URL": "https://fixture.invalid/v1"}):
            adapter = AtlasAdapter({"embedding_provider": "local", "embedding_model": "local-384-model"},
                                   database_getter=lambda: None)
            module = adapter._module()
            self.assertEqual(module.os.environ["VOYAGE_MODEL"], "chris-native-model")
            self.assertEqual(module.os.environ["VOYAGE_BASE_URL"], "https://fixture.invalid/v1")
        adapter = AtlasAdapter({"voyage_model": "explicit-native-model"}, database_getter=lambda: None)
        self.assertEqual(adapter._module().os.environ["VOYAGE_MODEL"], "explicit-native-model")

    def test_explicit_dream_is_awaited_and_bound_to_resident(self):
        calls = []

        async def dream(scope, *, backend, model):
            await asyncio.sleep(0)
            calls.append((scope, backend, model))
            return {"memories": 1}

        self.native.dream = dream
        self.assertEqual(asyncio.run(self.adapter.dream("alba", backend="fixture", model="fixture-model")), {"memories": 1})
        self.assertEqual(calls, [("sandbox:w:resident:alba", "fixture", "fixture-model")])
        self.assertEqual(self.native._dreaming, set())
        self.assertFalse(self.adapter.status()["busy"])

    def test_malformed_dream_never_reaches_writer(self):
        async def stream(**kwargs):
            yield "invalid dream with private-secret"

        bridge = types.SimpleNamespace(stream=stream)
        self.native._dream_gather = Mock(return_value=([{"_id": "t", "role": "user", "text": "Garden"}], [], [], []))
        self.native._dream_write = Mock()
        with patch.dict(sys.modules, {"bridges.model_bridge": bridge}):
            result = asyncio.run(self.adapter.dream("alba", backend="fixture", model="fixture"))
        self.assertIn("error", result)
        self.assertNotIn("private-secret", json.dumps(result))
        self.native._dream_write.assert_not_called()
        self.assertEqual(self.native._dreaming, set())

    def test_parser_requires_all_three_lists(self):
        for invalid in ("{}", '{"memories":[],"lessons":[]}', '{"memories":{},"lessons":[],"retire":[]}'):
            with self.assertRaises(ValueError):
                self.native._parse(invalid)
        self.assertEqual(self.native._parse('{"memories":[],"lessons":[],"retire":[]}'),
                         {"memories": [], "lessons": [], "retire": []})

    def test_configuration_cannot_close_database_during_work(self):
        self.adapter._start()
        try:
            with self.assertRaises(ValueError):
                self.adapter.configure({"database": "other"})
        finally:
            self.adapter._finish()
        self.adapter.configure({"database": "other"})
        self.assertEqual(self.adapter._module().DB_NAME, "other")

    def test_failures_are_soft_and_secret_free(self):
        self.native.recall = Mock(side_effect=RuntimeError("mongodb://private:secret@hostname"))
        self.native.mind = Mock(side_effect=RuntimeError("private-secret"))
        self.assertEqual(self.adapter.recall("alba", "hi")["memories"], [])
        self.assertFalse(self.adapter.mind("alba")["enabled"])
        self.assertNotIn("secret", json.dumps(self.adapter.status()))


if __name__ == "__main__":
    unittest.main()
