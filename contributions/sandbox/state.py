"""Authoritative, fictional town state; no Amble runtime or owner-data imports.

Every mutation runs in one SQLite transaction. ``complete`` and ``purchase``
return ``{ok: bool, ...}`` receipts; failures include an actionable ``error``.
Only a structurally exact, deterministically checked answer earns a wage.
Model messages are inert text, never commands. Snapshot collections are bounded
views over retained history, and there is at most one open job per resident.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional


ROLES = ("healthcare", "finance", "construction")
COLORS = {"healthcare": "#6bbcaf", "finance": "#e6b45b", "construction": "#b79ae3"}
CATALOG = (
    {"id": "daily-breakfast", "name": "Breakfast basket", "shop": "Daily", "price": 8, "icon": "🥐", "kind": "pack", "description": "A breakfast corner for your home."},
    {"id": "daily-plants", "name": "Little garden pack", "shop": "Daily", "price": 16, "icon": "🪴", "kind": "pack", "description": "Three cheerful plants for a sunny shelf."},
    {"id": "daily-books", "name": "Reading pack", "shop": "Daily", "price": 24, "icon": "📚", "kind": "pack", "description": "A stack of books and a quiet afternoon."},
    {"id": "convenience-lamp", "name": "Warm lamp", "shop": "Convenience", "price": 18, "icon": "💡", "kind": "furnishing", "description": "A warm pool of light beside the bed."},
    {"id": "convenience-chair", "name": "Comfy chair", "shop": "Convenience", "price": 32, "icon": "🪑", "kind": "furnishing", "description": "Your favorite seat after work."},
    {"id": "convenience-rug", "name": "Woven rug", "shop": "Convenience", "price": 44, "icon": "🧶", "kind": "furnishing", "description": "A colorful rug to make the room your own."},
    {"id": "convenience-sofa", "name": "Cloud sofa", "shop": "Convenience", "price": 65, "icon": "🛋️", "kind": "furnishing", "description": "Room for a friend and a long conversation."},
)
_ITEMS = {item["id"]: item for item in CATALOG}
_SEEDS = (("aya", "Aya", "healthcare"), ("june", "June", "healthcare"),
          ("milo", "Milo", "finance"), ("bea", "Bea", "finance"),
          ("kit", "Kit", "construction"), ("rowan", "Rowan", "construction"))


def _json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _text(value: Any, limit: int = 1200) -> str:
    return str(value or "").strip()[:limit]


class State:
    """A single simulation database. New towns start paused with six residents."""

    def __init__(self, path: Any, *, lease_seconds: float = 180.0) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.lease_seconds = max(0.01, float(lease_seconds))
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, timeout=30, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS residents (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
                color TEXT NOT NULL, credits INTEGER NOT NULL CHECK(credits >= 0),
                jobs_completed INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, resident_id TEXT NOT NULL REFERENCES residents(id),
                sequence INTEGER NOT NULL, payload TEXT NOT NULL, expected TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'available', created_at REAL NOT NULL,
                completed_at REAL, UNIQUE(resident_id, sequence)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS one_open_job ON jobs(resident_id)
                WHERE status IN ('available','leased');
            CREATE TABLE IF NOT EXISTS leases (
                id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
                resident_id TEXT NOT NULL REFERENCES residents(id), worker_id TEXT NOT NULL,
                status TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL,
                response TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS one_worker_lease ON leases(worker_id)
                WHERE status = 'active';
            CREATE UNIQUE INDEX IF NOT EXISTS one_job_lease ON leases(job_id)
                WHERE status = 'active';
            CREATE TABLE IF NOT EXISTS workers (
                id TEXT PRIMARY KEY, status TEXT NOT NULL, resident_id TEXT,
                last_seen REAL NOT NULL, error TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS ownership (
                resident_id TEXT NOT NULL REFERENCES residents(id), item_id TEXT NOT NULL,
                purchased_at REAL NOT NULL, PRIMARY KEY(resident_id, item_id)
            );
            CREATE TABLE IF NOT EXISTS purchases (
                request_id TEXT PRIMARY KEY, resident_id TEXT NOT NULL, item_id TEXT NOT NULL,
                response TEXT NOT NULL, created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS feed (
                id INTEGER PRIMARY KEY AUTOINCREMENT, resident_id TEXT, kind TEXT NOT NULL,
                text TEXT NOT NULL, details TEXT NOT NULL, created_at REAL NOT NULL
            );
        """)
        with self._transaction():
            if self._db.execute("SELECT 1 FROM meta WHERE key='initialized'").fetchone() is None:
                self._db.execute("INSERT INTO meta VALUES ('running','false')")
                for resident_id, name, role in _SEEDS:
                    self._insert_resident(resident_id, name, role)
                self._event(None, "system", "The town is ready. Six residents are settling in.")
                self._db.execute("INSERT INTO meta VALUES ('initialized','true')")

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                yield
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            else:
                self._db.execute("COMMIT")

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _event(self, resident_id: Optional[str], kind: str, text: str, **details: Any) -> dict:
        now = time.time()
        cursor = self._db.execute(
            "INSERT INTO feed (resident_id,kind,text,details,created_at) VALUES (?,?,?,?,?)",
            (resident_id, kind, _text(text), _json(details), now))
        return {"id": cursor.lastrowid, "resident_id": resident_id, "kind": kind,
                "text": _text(text), "created_at": now, **details}

    def _insert_resident(self, resident_id: str, name: str, role: str) -> None:
        self._db.execute("INSERT INTO residents VALUES (?,?,?,?,?,0,?)",
                         (resident_id, name, role, COLORS[role], 12, time.time()))
        self._new_job(resident_id, role, 1)

    def _new_job(self, resident_id: str, role: str, sequence: int) -> None:
        # Integer-only bookkeeping tasks: fictional supplies, budgets, and plans.
        n = sequence + sum(ord(c) for c in resident_id) % 7
        if role == "healthcare":
            title = "Prepare the clinic supply tally"
            task = {"supply": "bandage packs", "boxes": 2 + n % 5,
                    "packs_per_box": 6 + n % 4, "loose_packs": n % 6}
            expected = {"packs_total": task["boxes"] * task["packs_per_box"] + task["loose_packs"]}
            description = "Count the fictional clinic's bandage packs: boxes × packs_per_box + loose_packs. This is inventory bookkeeping, not medical advice."
            shape = {"packs_total": "integer"}
        elif role == "finance":
            title = "Balance the neighborhood market budget"
            task = {"sales_credits": 90 + n * 7, "supply_cost": 25 + n % 9,
                    "stall_cost": 12 + n % 5}
            expected = {"remaining_credits": task["sales_credits"] - task["supply_cost"] - task["stall_cost"]}
            description = "Calculate the fictional market's remaining credits: sales_credits − supply_cost − stall_cost."
            shape = {"remaining_credits": "integer"}
        else:
            title = "Count tiles for the community courtyard"
            task = {"rows": 3 + n % 6, "tiles_per_row": 5 + n % 7,
                    "spare_tiles": 2 + n % 4}
            expected = {"tiles_needed": task["rows"] * task["tiles_per_row"] + task["spare_tiles"]}
            description = "Calculate the fictional courtyard's tile order: rows × tiles_per_row + spare_tiles."
            shape = {"tiles_needed": "integer"}
        job_id = "job-" + uuid.uuid4().hex[:16]
        payload = {"id": job_id, "resident_id": resident_id, "role": role, "title": title,
                   "description": description, "task": task, "reward": 12 + sequence % 4 * 2,
                   "answer_schema": shape, "sequence": sequence,
                   "response_format": {"answer": shape, "message": "short first-person message about your result", "buy_item_id": "optional catalog item id; omit to save credits"}}
        self._db.execute("INSERT INTO jobs (id,resident_id,sequence,payload,expected,created_at) VALUES (?,?,?,?,?,?)",
                         (job_id, resident_id, sequence, _json(payload), _json(expected), time.time()))

    def _resident(self, resident_id: str) -> Optional[dict]:
        row = self._db.execute("SELECT * FROM residents WHERE id=?", (resident_id,)).fetchone()
        if row is None:
            return None
        resident = dict(row)
        lease = self._db.execute("SELECT id,job_id,worker_id FROM leases WHERE resident_id=? AND status='active'", (resident_id,)).fetchone()
        resident["status"] = "working" if lease else "idle"
        resident["lease_id"] = lease["id"] if lease else None
        resident["worker_id"] = lease["worker_id"] if lease else None
        items = self._db.execute("SELECT item_id,purchased_at FROM ownership WHERE resident_id=? ORDER BY purchased_at", (resident_id,)).fetchall()
        resident["home"] = {"items": [{**_ITEMS[item["item_id"]], "purchased_at": item["purchased_at"]} for item in items]}
        return resident

    def _heartbeat(self, worker_id: str, status: str = "idle", resident_id: Optional[str] = None, error: str = "") -> None:
        self._db.execute("""INSERT INTO workers (id,status,resident_id,last_seen,error) VALUES (?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET status=excluded.status,resident_id=excluded.resident_id,
            last_seen=excluded.last_seen,error=excluded.error""", (worker_id, status, resident_id, time.time(), _text(error, 300)))

    def heartbeat(self, worker_id: str, status: str = "idle", resident_id: Optional[str] = None, error: str = "") -> dict:
        """Record worker liveness; a heartbeat does not extend a bounded lease."""
        if not isinstance(worker_id, str) or not worker_id.strip() or len(worker_id) > 100:
            return {"ok": False, "error": "worker_id must contain 1–100 characters"}
        with self._transaction():
            self._heartbeat(worker_id, _text(status, 40), resident_id, error)
        return {"ok": True, "worker_id": worker_id}

    def _expire(self) -> None:
        for lease in self._db.execute("SELECT * FROM leases WHERE status='active' AND expires_at<=?", (time.time(),)).fetchall():
            response = {"ok": False, "lease_id": lease["id"], "error": "Lease expired; request a fresh lease before submitting work."}
            self._db.execute("UPDATE leases SET status='expired',response=? WHERE id=?", (_json(response), lease["id"]))
            self._db.execute("UPDATE jobs SET status='available' WHERE id=?", (lease["job_id"],))
            self._db.execute("UPDATE workers SET status='expired',resident_id=NULL,error=? WHERE id=?", (response["error"], lease["worker_id"]))
            self._event(lease["resident_id"], "recovery", "A timed-out job is available again; no credits were awarded.", job_id=lease["job_id"], lease_id=lease["id"])

    def snapshot(self) -> dict:
        with self._transaction():
            self._expire()
            residents = [self._resident(row[0]) for row in self._db.execute("SELECT id FROM residents ORDER BY created_at,id").fetchall()]
            jobs = []
            for row in self._db.execute("SELECT * FROM jobs ORDER BY (status='completed'),created_at DESC LIMIT 80").fetchall():
                jobs.append({**json.loads(row["payload"]), "status": row["status"], "created_at": row["created_at"], "completed_at": row["completed_at"]})
            feed = [{"id": row["id"], "resident_id": row["resident_id"], "kind": row["kind"], "text": row["text"], "created_at": row["created_at"], **json.loads(row["details"])}
                    for row in self._db.execute("SELECT * FROM feed ORDER BY id DESC LIMIT 120").fetchall()]
            workers = [dict(row) for row in self._db.execute("SELECT * FROM workers ORDER BY id").fetchall()]
            running = self._db.execute("SELECT value FROM meta WHERE key='running'").fetchone()[0] == "true"
            return {"residents": residents, "jobs": jobs, "feed": feed, "catalog": [dict(item) for item in CATALOG],
                    "workers": workers, "running": running, "roles": list(ROLES), "server_time": time.time(),
                    "stats": {"residents": len(residents), "jobs_completed": sum(r["jobs_completed"] for r in residents),
                              "credits": sum(r["credits"] for r in residents), "active_workers": sum(w["status"] == "working" for w in workers)}}

    def set_running(self, running: bool) -> dict:
        if not isinstance(running, bool):
            return {"ok": False, "error": "running must be a boolean"}
        with self._transaction():
            previous = self._db.execute("SELECT value FROM meta WHERE key='running'").fetchone()[0]
            self._db.execute("UPDATE meta SET value=? WHERE key='running'", ("true" if running else "false",))
            if (previous == "true") != running:
                self._event(None, "system", "The town is working." if running else "The town is paused. Current jobs may finish.")
        return {"ok": True, "running": running}

    def add_resident(self, name: str, role: str) -> dict:
        if role not in ROLES:
            return {"ok": False, "error": "Choose healthcare, finance, or construction."}
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 40:
            return {"ok": False, "error": "A resident name must contain 1–40 characters."}
        with self._transaction():
            if self._db.execute("SELECT count(*) FROM residents").fetchone()[0] >= 48:
                return {"ok": False, "error": "This bounded town supports at most 48 residents."}
            resident_id = "resident-" + uuid.uuid4().hex[:12]
            self._insert_resident(resident_id, name.strip(), role)
            self._event(resident_id, "arrival", name.strip() + " moved into town.")
            return {"ok": True, **self._resident(resident_id)}

    def post(self, resident_id: str, text: str, kind: str = "chat") -> dict:
        if kind != "chat":
            return {"ok": False, "error": "Resident posts use kind='chat'; work and purchase receipts are generated by the server."}
        if not isinstance(text, str) or not text.strip():
            return {"ok": False, "error": "Write a nonempty message."}
        with self._transaction():
            if self._resident(resident_id) is None:
                return {"ok": False, "error": "Resident not found."}
            return {"ok": True, **self._event(resident_id, "chat", text, verified=False)}

    def _lease_view(self, lease: sqlite3.Row) -> dict:
        job = self._db.execute("SELECT payload FROM jobs WHERE id=?", (lease["job_id"],)).fetchone()
        return {"id": lease["id"], "lease_id": lease["id"], "worker_id": lease["worker_id"],
                "resident": self._resident(lease["resident_id"]), "job": json.loads(job[0]), "expires_at": lease["expires_at"]}

    def lease(self, worker_id: str, resident_id: Optional[str] = None) -> Optional[dict]:
        if not isinstance(worker_id, str) or not worker_id.strip() or len(worker_id) > 100:
            return None
        with self._transaction():
            self._expire()
            active = self._db.execute("SELECT * FROM leases WHERE worker_id=? AND status='active'", (worker_id,)).fetchone()
            if active:
                self._heartbeat(worker_id, "working", active["resident_id"])
                return self._lease_view(active)
            self._heartbeat(worker_id)
            if self._db.execute("SELECT value FROM meta WHERE key='running'").fetchone()[0] != "true":
                return None
            query = "SELECT * FROM jobs WHERE status='available'"
            params = ()
            if resident_id is not None:
                query += " AND resident_id=?"
                params = (resident_id,)
            job = self._db.execute(query + " ORDER BY created_at,id LIMIT 1", params).fetchone()
            if job is None:
                return None
            now = time.time()
            lease_id = "lease-" + uuid.uuid4().hex
            self._db.execute("INSERT INTO leases VALUES (?,?,?,?, 'active',?,?,NULL)",
                             (lease_id, job["id"], job["resident_id"], worker_id, now, now + self.lease_seconds))
            self._db.execute("UPDATE jobs SET status='leased' WHERE id=?", (job["id"],))
            self._heartbeat(worker_id, "working", job["resident_id"])
            return self._lease_view(self._db.execute("SELECT * FROM leases WHERE id=?", (lease_id,)).fetchone())

    def _owned_lease(self, lease_id: str, worker_id: str) -> tuple:
        lease = self._db.execute("SELECT * FROM leases WHERE id=?", (lease_id,)).fetchone()
        if lease is None or lease["worker_id"] != worker_id:
            return None, {"ok": False, "error": "Lease not found for this worker."}
        if lease["status"] != "active":
            return None, {**json.loads(lease["response"]), "idempotent": True}
        return lease, None

    def _release(self, lease: sqlite3.Row, error: str) -> dict:
        response = {"ok": False, "lease_id": lease["id"], "resident_id": lease["resident_id"],
                    "job_id": lease["job_id"], "reward": 0, "error": _text(error, 500)}
        self._db.execute("UPDATE leases SET status='released',response=? WHERE id=?", (_json(response), lease["id"]))
        self._db.execute("UPDATE jobs SET status='available' WHERE id=?", (lease["job_id"],))
        self._heartbeat(lease["worker_id"], "error", None, error)
        self._event(lease["resident_id"], "retry", "The job needs another attempt; no wage was paid.", job_id=lease["job_id"], error=response["error"])
        return response

    def release(self, lease_id: str, worker_id: str, error: str) -> dict:
        with self._transaction():
            self._expire()
            lease, previous = self._owned_lease(lease_id, worker_id)
            return previous if previous is not None else self._release(lease, error or "Worker released the job; request a fresh lease.")

    def complete(self, lease_id: str, worker_id: str, result: dict) -> dict:
        with self._transaction():
            self._expire()
            lease, previous = self._owned_lease(lease_id, worker_id)
            if previous is not None:
                return previous
            job_row = self._db.execute("SELECT * FROM jobs WHERE id=?", (lease["job_id"],)).fetchone()
            job, expected = json.loads(job_row["payload"]), json.loads(job_row["expected"])
            answer = result.get("answer") if isinstance(result, dict) else None
            valid = isinstance(answer, dict) and answer.keys() == expected.keys()
            valid = valid and all(type(answer[key]) is int and answer[key] == value for key, value in expected.items())
            if not valid:
                return self._release(lease, "Answer did not match the job data. Recalculate the stated formula and return only the integer fields in answer_schema; request a fresh lease.")
            if not isinstance(result.get("message"), str) or not result["message"].strip() or len(result["message"]) > 1200:
                return self._release(lease, "Include a nonempty message of at most 1200 characters; request a fresh lease.")
            buy_item = result.get("buy_item_id")
            if buy_item is not None and not isinstance(buy_item, str):
                return self._release(lease, "buy_item_id must be a catalog item id string or omitted; request a fresh lease.")
            self._db.execute("UPDATE jobs SET status='completed',completed_at=? WHERE id=?", (time.time(), job["id"]))
            self._db.execute("UPDATE residents SET credits=credits+?,jobs_completed=jobs_completed+1 WHERE id=?", (job["reward"], lease["resident_id"]))
            receipt = self._event(lease["resident_id"], "work", job["title"] + " completed.", job_id=job["id"], lease_id=lease_id,
                                  answer=answer, reward=job["reward"], verified=True)
            self._event(lease["resident_id"], "chat", result["message"], verified=False, job_id=job["id"])
            response = {"ok": True, "lease_id": lease_id, "resident_id": lease["resident_id"], "job_id": job["id"],
                        "reward": job["reward"], "receipt_id": receipt["id"], "answer": answer}
            if buy_item:
                response["purchase"] = self._purchase(lease["resident_id"], buy_item, "completion:" + lease_id)
            response["credits"] = self._db.execute("SELECT credits FROM residents WHERE id=?", (lease["resident_id"],)).fetchone()[0]
            self._db.execute("UPDATE leases SET status='completed',response=? WHERE id=?", (_json(response), lease_id))
            self._heartbeat(worker_id, "idle")
            self._new_job(lease["resident_id"], job["role"], job_row["sequence"] + 1)
            return response

    def _purchase(self, resident_id: str, item_id: str, request_id: str) -> dict:
        prior = self._db.execute("SELECT * FROM purchases WHERE request_id=?", (request_id,)).fetchone()
        if prior is not None:
            if prior["resident_id"] != resident_id or prior["item_id"] != item_id:
                return {"ok": False, "error": "request_id already belongs to a different purchase."}
            return {**json.loads(prior["response"]), "idempotent": True}
        resident = self._db.execute("SELECT credits FROM residents WHERE id=?", (resident_id,)).fetchone()
        item = _ITEMS.get(item_id)
        response = {"ok": False, "request_id": request_id, "resident_id": resident_id, "item_id": item_id}
        if resident is None:
            response["error"] = "Resident not found."
        elif item is None:
            response["error"] = "Choose an item from the catalog."
        elif self._db.execute("SELECT 1 FROM ownership WHERE resident_id=? AND item_id=?", (resident_id, item_id)).fetchone():
            response["error"] = "This home already owns that item."
        elif resident["credits"] < item["price"]:
            response["error"] = "Not enough credits; finish more jobs before purchasing."
        else:
            self._db.execute("UPDATE residents SET credits=credits-? WHERE id=?", (item["price"], resident_id))
            self._db.execute("INSERT INTO ownership VALUES (?,?,?)", (resident_id, item_id, time.time()))
            receipt = self._event(resident_id, "purchase", "Bought " + item["name"] + " from " + item["shop"] + ".", item_id=item_id, price=item["price"], verified=True)
            response.update(ok=True, price=item["price"], credits=resident["credits"] - item["price"], item=dict(item), receipt_id=receipt["id"])
        self._db.execute("INSERT INTO purchases VALUES (?,?,?,?,?)", (request_id, resident_id, item_id, _json(response), time.time()))
        return response

    def purchase(self, resident_id: str, item_id: str, request_id: str) -> dict:
        if not all(isinstance(value, str) and value.strip() for value in (resident_id, item_id, request_id)) or len(request_id) > 160:
            return {"ok": False, "error": "Provide resident_id, item_id, and a stable request_id (at most 160 characters)."}
        if request_id.startswith("completion:"):
            return {"ok": False, "error": "The completion request_id prefix is reserved for wage receipts."}
        with self._transaction():
            return self._purchase(resident_id, item_id, request_id)
