"""Synthetic replication is durable and never becomes a lived resident memory."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sandbox.economy import load_demo
from sandbox.memory import Memory


def main():
    payload = load_demo()
    assert payload["available"]
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "memory.sqlite3"
        memory = Memory(path, {"embedding_provider": "lexical", "mongodb_uri": ""})
        memory.sync_simulation(payload)
        memory.sync_simulation(payload)
        rows = memory._db.execute("SELECT collection,document FROM outbox").fetchall()
        assert len(rows) == 251, "stable IDs must coalesce duplicate deliveries"
        assert {row[0] for row in rows} == {"simulation_runs", "simulation_daily_summaries", "simulation_residents"}
        assert all(json.loads(row[1])["synthetic"] is True for row in rows)
        assert memory.status()["memories"] == 0
        assert memory._db.execute("SELECT COUNT(*) FROM native_mirrors").fetchone()[0] == 0
        assert memory.recent("aya") == []
        memory.close()
        reopened = Memory(path, {"embedding_provider": "lexical", "mongodb_uri": ""})
        assert reopened.status()["pending"] == 251, "offline replication must survive restart"
        reopened.close()
    print("PASS synthetic Atlas outbox: stable IDs, isolated collections, zero lived memories, durable restart")


if __name__ == "__main__":
    main()
