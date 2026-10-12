"""Offline validation and destination isolation for synthetic life delivery."""
from __future__ import annotations

from pathlib import Path
import sys
import types
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.sync_resident_life import COLLECTION, synchronize, validate_source


class FakeCollection:
    def __init__(self):
        self.rows = {}
        self.batches = []

    def find(self, query, projection):
        return [{"_id": key} for key, row in self.rows.items() if row["simulation_id"] == query["simulation_id"]]

    def bulk_write(self, operations, ordered):
        assert ordered
        self.batches.append(len(operations))
        for query, row, upsert in operations:
            assert upsert and query["synthetic"] is True and query["_id"] == row["_id"]
            self.rows[row["_id"]] = row
        return types.SimpleNamespace(acknowledged=True)

    def count_documents(self, query):
        return sum(row["synthetic"] is True and row["simulation_id"] == query["simulation_id"] for row in self.rows.values())


class FakeDatabase:
    def __init__(self):
        self.collection = FakeCollection()

    def __getitem__(self, name):
        assert name == COLLECTION
        return self.collection

    def command(self, name, **kwargs):
        assert name == "dbStats"
        return {"dataSize": 123, "storageSize": 456}


class TestResidentLifeSync(unittest.TestCase):
    def test_real_bounded_fixture_and_idempotent_destination(self):
        rows, report = validate_source()
        self.assertEqual(report["records"], 10000)
        self.assertEqual(report["residents"], 200)
        self.assertLess(report["source_expanded_bytes"], 80 * 1024 * 1024)
        database = FakeDatabase()
        replace = lambda query, row, upsert: (query, row, upsert)
        first = synchronize(database, rows, report, replace)
        second = synchronize(database, rows, report, replace)
        self.assertEqual(first["verified_records"], 10000)
        self.assertEqual(second["existing_records_before"], 10000)
        self.assertEqual(second["verified_ids_sha256"], report["ids_sha256"])
        self.assertEqual(database.collection.batches, [500] * 40)


if __name__ == "__main__":
    unittest.main()
