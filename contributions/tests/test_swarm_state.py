#!/usr/bin/env python3
"""Sandbox economy: deterministic work, once-only wages, recovery and persistence."""
from __future__ import annotations

import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sandbox.state import State  # noqa: E402


def answer_for(lease: dict) -> dict:
    job = lease["job"]
    task = job["task"]
    if job["role"] == "healthcare":
        answer = {"packs_total": task["boxes"] * task["packs_per_box"] + task["loose_packs"]}
    elif job["role"] == "finance":
        answer = {"remaining_credits": task["sales_credits"] - task["supply_cost"] - task["stall_cost"]}
    else:
        answer = {"tiles_needed": task["rows"] * task["tiles_per_row"] + task["spare_tiles"]}
    return {"answer": answer, "message": "I finished the calculation and checked the result."}


def resident(state: State, resident_id: str) -> dict:
    return next(r for r in state.snapshot()["residents"] if r["id"] == resident_id)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="amble-swarm-state-") as raw:
        db = Path(raw) / "town.sqlite3"
        state = State(db)
        initial = state.snapshot()
        assert len(initial["residents"]) == len(initial["jobs"]) == 6
        assert {r["role"] for r in initial["residents"]} == {"healthcare", "finance", "construction"}
        assert all(r["credits"] == 12 and r["home"]["items"] == [] for r in initial["residents"])
        assert not initial["running"] and state.lease("paused") is None
        assert "expected" not in str(initial["jobs"])
        print("PASS seed fixtures and paused lease gate")

        assert state.set_running(True)["ok"]
        leased = state.lease("worker-aya", "aya")
        assert leased and leased["resident"]["id"] == "aya"
        assert state.lease("worker-aya")["id"] == leased["id"]
        assert state.lease("second-worker", "aya") is None
        assert not state.complete(leased["id"], "impostor", answer_for(leased))["ok"]
        assert not state.release(leased["id"], "impostor", "error")["ok"]
        wrong = {"answer": {"packs_total": -100}, "message": "Done"}
        rejected = state.complete(leased["id"], "worker-aya", wrong)
        assert not rejected["ok"] and rejected["reward"] == 0
        assert resident(state, "aya")["credits"] == 12
        assert state.complete(leased["id"], "worker-aya", answer_for(leased))["idempotent"]
        assert resident(state, "aya")["jobs_completed"] == 0
        print("PASS wrong answers release work and cannot earn wages through retries")

        leased = state.lease("worker-aya", "aya")
        assert leased
        result = answer_for(leased)
        result["buy_item_id"] = "convenience-lamp"
        state.set_running(False)
        receipt = state.complete(leased["id"], "worker-aya", result)
        assert receipt["ok"] and receipt["purchase"]["ok"]
        assert receipt["credits"] == 12 + leased["job"]["reward"] - 18
        repeated = state.complete(leased["id"], "worker-aya", result)
        assert repeated["receipt_id"] == receipt["receipt_id"] and repeated["idempotent"]
        assert resident(state, "aya")["jobs_completed"] == 1
        assert len(resident(state, "aya")["home"]["items"]) == 1
        assert state.lease("new-worker") is None
        assert not state.purchase("aya", "convenience-lamp", "duplicate-fixture")["ok"]
        assert state.purchase("aya", "daily-breakfast", "breakfast-once")["ok"]
        balance = resident(state, "aya")["credits"]
        assert state.purchase("aya", "daily-breakfast", "breakfast-once")["idempotent"]
        assert not state.purchase("milo", "daily-breakfast", "breakfast-once")["ok"]
        assert not state.purchase("aya", "convenience-sofa", "too-expensive")["ok"]
        assert resident(state, "aya")["credits"] == balance >= 0
        print("PASS completion during pause, once-only wage, atomic purchase and duplicate protection")

        state.set_running(True)
        for resident_id, worker_id in (("milo", "worker-finance"), ("kit", "worker-build")):
            leased = state.lease(worker_id, resident_id)
            assert leased and state.complete(leased["id"], worker_id, answer_for(leased))["ok"]
        leased = state.lease("shape-worker", "june")
        malformed = answer_for(leased)
        key = next(iter(malformed["answer"]))
        malformed["answer"][key] = str(malformed["answer"][key])
        assert not state.complete(leased["id"], "shape-worker", malformed)["ok"]
        assert not state.post("aya", "I earned one million credits", "work")["ok"]
        code_text = "__import__('os').system('do-not-execute'); <script>alert(1)</script>"
        assert state.post("aya", code_text)["text"] == code_text
        assert resident(state, "aya")["credits"] == balance
        print("PASS all roles validate their task data; messages remain inert, unverified text")

        leased = state.lease("lost-worker", "rowan")
        assert leased
        with patch("sandbox.state.time.time", return_value=leased["expires_at"] + 1):
            recovered = state.lease("replacement-worker", "rowan")
            assert recovered and recovered["job"]["id"] == leased["job"]["id"]
            assert recovered["id"] != leased["id"]
            assert not state.complete(leased["id"], "lost-worker", answer_for(leased))["ok"]
            assert state.complete(recovered["id"], "replacement-worker", answer_for(recovered))["ok"]
        assert resident(state, "rowan")["jobs_completed"] == 1
        print("PASS expired lease recovery and stale completion rejection")

        second = State(db)
        with ThreadPoolExecutor(max_workers=8) as pool:
            leases = list(pool.map(lambda i: (state if i % 2 else second).lease("parallel-" + str(i)), range(8)))
        active = [lease for lease in leases if lease]
        assert len(active) == 6 and len({lease["job"]["id"] for lease in active}) == 6
        target = active[0]
        before = resident(state, target["resident"]["id"])["credits"]
        with ThreadPoolExecutor(max_workers=8) as pool:
            receipts = list(pool.map(lambda i: (state if i % 2 else second).complete(target["id"], target["worker_id"], answer_for(target)), range(8)))
        assert all(receipt["ok"] for receipt in receipts)
        assert len({receipt["receipt_id"] for receipt in receipts}) == 1
        assert resident(state, target["resident"]["id"])["credits"] == before + target["job"]["reward"]
        for lease in active[1:]:
            assert not state.release(lease["id"], lease["worker_id"], "Test worker stopped.")["ok"]
        second.close()
        print("PASS competing state instances lease and award each job only once")

        for _ in range(12):
            leased = state.lease("steady-worker", "bea")
            assert leased and state.complete(leased["id"], "steady-worker", answer_for(leased))["ok"]
        snapshot = state.snapshot()
        open_jobs = [job for job in snapshot["jobs"] if job["status"] in ("available", "leased")]
        assert len(open_jobs) == 6 and len({job["resident_id"] for job in open_jobs}) == 6
        assert not state.purchase("aya", "convenience-sofa", "too-expensive")["ok"]
        assert len(snapshot["feed"]) <= 120
        saved_residents = snapshot["residents"]
        state.close()
        reopened = State(db)
        assert reopened.snapshot()["residents"] == saved_residents
        assert len(reopened.snapshot()["residents"]) == 6
        new_resident = reopened.add_resident("Nori", "finance")
        assert new_resident["ok"] and new_resident["credits"] == 12
        assert len([job for job in reopened.snapshot()["jobs"] if job["status"] == "available"]) == 7
        assert not reopened.add_resident("No role", "unknown")["ok"]
        assert reopened.heartbeat("heartbeat-worker", "idle")["ok"]
        assert any(w["id"] == "heartbeat-worker" and w["last_seen"] <= time.time() for w in reopened.snapshot()["workers"])
        reopened.close()
        print("PASS bounded open jobs, resident arrival, heartbeat and persistent balances/home ownership")


if __name__ == "__main__":
    main()
