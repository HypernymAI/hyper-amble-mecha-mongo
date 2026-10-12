#!/usr/bin/env python3
"""Validate synthetic resident days; upload only with explicit --apply."""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from sandbox.economy import load_demo

COLLECTION = "simulation_resident_life"
DEFAULT_SOURCE = REPO / "simulations/resident_life/resident_days.jsonl.gz"
MAX_EXPANDED = 80 * 1024 * 1024


def require(condition):
    if not condition:
        raise ValueError("Synthetic resident-life validation failed")


def integer(value):
    require(type(value) is int and value >= 0)
    return value


def ids_hash(ids):
    return hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()


def validate_source(path=DEFAULT_SOURCE, demo=None):
    demo = load_demo() if demo is None else demo
    require(demo.get("available") is True and demo.get("synthetic") is True)
    require(len(demo["residents"]) == 200)
    expected = {row["resident_id"]: row for row in demo["residents"]}
    require(len(expected) == 200)
    source = Path(path)
    require(source.stat().st_size <= 10 * 1024 * 1024)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    rows, seen, expanded = [], set(), 0
    grouped = {rid: {} for rid in expected}
    with gzip.open(source, "rb") as stream:
        while True:
            line = stream.readline(1_000_001)
            if not line:
                break
            expanded += len(line)
            require(len(line) <= 1_000_000 and expanded <= MAX_EXPANDED)
            row = json.loads(line)
            rid, day = row["resident_id"], row["day"]
            require(rid in expected and type(day) is int and 1 <= day <= 50)
            require(row["synthetic"] is True and row["simulation_id"] == demo["simulation_id"])
            require(row["amble_id"] == rid and row["profession"] == expected[rid]["profession"])
            require(row["_id"] == f"{demo['simulation_id']}:{rid}:day:{day:03d}:life:v1")
            require(row["_id"] not in seen and day not in grouped[rid])
            require("embedding" not in row and "embeddings" not in row)
            require(row["provenance"]["dialogue_is_synthetic"] is True)
            require(all(isinstance(row[key], str) and row[key] for key in ("morning", "memory", "night")))
            require(isinstance(row["work_conversation"], list) and all(
                isinstance(turn, dict) and isinstance(turn.get("text"), str) for turn in row["work_conversation"]))
            require(all(type(value) is int and value >= 0 for value in row["ledger"].values()))
            require(all(type(value) is int and value >= 0 for value in row["inventory"].values()))
            seen.add(row["_id"])
            grouped[rid][day] = row
            rows.append(row)
            require(len(rows) <= 10000)
    require(len(rows) == 10000)
    ownership = {item["item_id"]: item["ownership"] for item in demo["catalog"]["items"]}
    prices = {sku["sku_id"]: sku["price_credits"] for sku in demo["catalog"]["products"]}
    for rid, days in grouped.items():
        require(set(days) == set(range(1, 51)))
        final = expected[rid]
        balance = final["starting_credits"]
        earned = spent = jobs = opened = 0
        inventory = Counter()
        for day in range(1, 51):
            row = days[day]
            ledger = row["ledger"]
            require(row["date"] == demo["days"][day - 1]["date"])
            require(ledger["opening_balance"] == balance)
            balance += integer(ledger["credits_earned"]) - integer(ledger["credits_spent"])
            require(balance >= 0 and ledger["closing_balance"] == balance)
            packs = row["pack_openings"]
            require(len(packs) == ledger["packs_opened"] and row.get("packs", packs) == packs)
            require(sum(prices[pack["sku_id"]] for pack in packs) == ledger["credits_spent"])
            for pack in packs:
                require(len(pack["items"]) == {"empty": 0, "one_item": 1, "two_items": 2}[pack["outcome"]])
                for item in pack["items"]:
                    require(item["item_id"] in ownership)
                    if ownership[item["item_id"]] == "permanent":
                        inventory[item["item_id"]] += 1
            require(dict(inventory) == row["inventory"])
            require(set(row["home"]["owned_home_item_ids"]) == set(inventory))
            integer(row["home"]["home_version"])
            earned += ledger["credits_earned"]
            spent += ledger["credits_spent"]
            jobs += ledger["jobs_completed"]
            opened += ledger["packs_opened"]
        require(balance == final["ending_balance"] and earned == final["credits_earned"])
        require(spent == final["credits_spent"] and jobs == final["jobs_completed"] and opened == final["packs_opened"])
        require(dict(inventory) == {key: value for key, value in final["inventory_quantities"].items() if value})
        require(set(inventory) == set(final["owned_home_item_ids"]))
        require(days[50]["home"]["home_version"] == final["home_version"])
    return rows, {"valid": True, "synthetic": True, "simulation_id": demo["simulation_id"],
                  "collection": COLLECTION, "records": len(rows), "residents": len(grouped), "days": 50,
                  "source_compressed_bytes": source.stat().st_size, "source_expanded_bytes": expanded,
                  "source_sha256": source_hash, "ids_sha256": ids_hash(seen),
                  "estimated_uncompressed_storage_bytes": int(expanded * 1.25)}


def synchronize(database, rows, report, replace_one):
    """Only the fixed synthetic collection is writable; source IDs are retained."""
    collection = database[COLLECTION]
    query = {"simulation_id": report["simulation_id"]}
    expected_ids = {row["_id"] for row in rows}
    before_ids = {row["_id"] for row in collection.find(query, {"_id": 1})}
    require(before_ids.issubset(expected_ids))
    result = dict(report, existing_records_before=len(before_ids), existing_ids_sha256=ids_hash(before_ids))
    try:
        stats = database.command("dbStats", scale=1)
        result["database_data_bytes_before"] = int(stats.get("dataSize", 0))
        result["database_storage_bytes_before"] = int(stats.get("storageSize", 0))
        result["projected_data_bytes_upper_estimate"] = result["database_data_bytes_before"] + report["estimated_uncompressed_storage_bytes"]
    except Exception:
        result["database_size_status"] = "unavailable"
    for start in range(0, len(rows), 500):
        batch = [replace_one({"_id": row["_id"], "simulation_id": report["simulation_id"], "synthetic": True},
                             row, upsert=True) for row in rows[start:start + 500]]
        outcome = collection.bulk_write(batch, ordered=True)
        require(outcome.acknowledged)
    after_ids = {row["_id"] for row in collection.find(query, {"_id": 1})}
    require(after_ids == expected_ids)
    require(collection.count_documents(dict(query, synthetic=True)) == len(rows))
    result.update(applied=True, verified_records=len(after_ids), verified_ids_sha256=ids_hash(after_ids))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--config", type=Path, default=REPO / "data/swarm/config.json")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--dry-run", action="store_true", help="Validate only; default, no credentials or network")
    action.add_argument("--apply", action="store_true", help="Explicitly upsert the validated synthetic scenario")
    args = parser.parse_args(argv)
    client = None
    try:
        rows, report = validate_source(args.source)
        if not args.apply:
            print(json.dumps(dict(report, dry_run=True, applied=False), sort_keys=True))
            return 0
        config = json.loads(args.config.read_text())
        uri = config.get("mongodb_uri")
        require(isinstance(uri, str) and bool(uri.strip()))
        from pymongo import MongoClient, ReplaceOne
        client = MongoClient(uri, connectTimeoutMS=3000, serverSelectionTimeoutMS=3000,
                             socketTimeoutMS=10000, timeoutMS=15000, appname="amble-synthetic-life-import")
        client.admin.command("ping")
        database = client[config.get("mongodb_database") or config.get("database") or "amble_sandbox"]
        print(json.dumps(synchronize(database, rows, report, ReplaceOne), sort_keys=True))
        return 0
    except Exception:
        print(json.dumps({"complete": False, "write_status": "unknown_or_partial" if args.apply else "not_attempted",
                          "error": "Resident-life validation or synchronization failed; any partial upload is safe to retry by stable ID"}))
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
