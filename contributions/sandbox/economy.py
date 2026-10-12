"""Bounded, verified synthetic economy data; never changes the lived swarm."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1] / "simulations" / "economy"
DATA_FILES = ("daily_summaries.jsonl", "sample_residents.jsonl", "economy_totals.json",
              "catalog.json", "parameters.json")
MAX_FILE_BYTES = 1_000_000


def _check(condition):
    if not condition:
        raise ValueError("Synthetic economy validation failed")


def _read(path):
    _check(path.is_file() and path.stat().st_size <= MAX_FILE_BYTES)
    return path.read_bytes()


def _integer(value):
    _check(type(value) is int and value >= 0)
    return value


def _identity(row, simulation_id, world_id):
    _check(isinstance(row, dict) and row.get("synthetic") is True)
    _check(row.get("simulation_id") == simulation_id and row.get("world_id") == world_id)


def _finite(value):
    if isinstance(value, float):
        _check(math.isfinite(value))
    elif isinstance(value, dict):
        for child in value.values():
            _finite(child)
    elif isinstance(value, list):
        for child in value:
            _finite(child)


def _validate(summary, days, residents, catalog, parameters, simulation_id, world_id):
    _finite([summary, days, residents, catalog, parameters])
    _identity(summary, simulation_id, world_id)
    _check(len(days) == 50 and len(residents) == 200 and summary["days"] == 50)
    population = _integer(summary["population"])
    _check(population >= len(residents) and summary["resident_days"] == population * 50)
    _check(catalog.get("synthetic") is True and parameters.get("synthetic") is True)
    products = {row["sku_id"]: row for row in catalog["products"]}
    items = {row["item_id"]: row for row in catalog["items"]}
    _check(len(products) == len(catalog["products"]) and len(items) == len(catalog["items"]))
    starting = _integer(parameters["starting_credits"])
    balance = _integer(summary["initial_household_credits"])
    _check(balance == population * starting)
    earned = spent = opened = empty = drops = jobs = 0
    day_ids = set()
    for number, row in enumerate(days, 1):
        _identity(row, simulation_id, world_id)
        _check(row["day"] == number and row["population"] == population)
        _integer(row["active_ambles"])
        _integer(row["wealth"]["min"])
        _integer(row["wealth"]["max"])
        _check(type(row["wealth"]["mean"]) in (int, float))
        _check(row["_id"] == simulation_id + ":day:" + format(number, "03d"))
        _check(row["_id"] not in day_ids and row["sample_included_not_additive"] is True)
        day_ids.add(row["_id"])
        _check(row["opening_household_credits"] == balance)
        day_earned, day_spent = _integer(row["credits_earned"]), _integer(row["credits_spent"])
        balance += day_earned - day_spent
        _check(balance >= 0 and row["closing_household_credits"] == balance)
        quantities = dict(row["packs_bought_by_sku"])
        quantities.update(row["furnishings_bought_by_sku"])
        _check(all(key in products for key in quantities))
        _check(sum(_integer(quantity) * _integer(products[key]["price_credits"])
                   for key, quantity in quantities.items()) == day_spent)
        day_opened = _integer(row["packs_opened"])
        _check(sum(row["packs_bought_by_sku"].values()) == day_opened)
        outcomes = row["pack_outcomes"]
        _check(sum(_integer(value) for value in outcomes.values()) == day_opened)
        day_drops = sum(_integer(value) for value in row["item_drops_by_id"].values())
        _check(set(row["item_drops_by_id"]).issubset(items))
        _check(day_drops == outcomes["one_item"] + 2 * outcomes["two_items"])
        earned += day_earned
        spent += day_spent
        opened += day_opened
        empty += outcomes["empty"]
        drops += day_drops
        jobs += _integer(row["jobs_completed"])
        _check(row["cumulative_credits_earned"] == earned and row["cumulative_shop_credits"] == spent)
        _check(sum(_integer(bucket["population"]) for bucket in row["wealth"]["histogram"]) == population)
        _check(set(row["by_profession"]) == set(parameters["professions"]))
        for field, total in (("population", population), ("active_ambles", row["active_ambles"]),
                             ("jobs_completed", row["jobs_completed"]), ("credits_earned", day_earned),
                             ("credits_spent", day_spent), ("closing_balance", balance)):
            _check(sum(_integer(role[field]) for role in row["by_profession"].values()) == total)
    for key, value in (("credits_earned", earned), ("credits_spent", spent), ("packs_opened", opened),
                       ("empty_openings", empty), ("item_drops", drops), ("jobs_completed", jobs),
                       ("ending_household_credits", balance), ("ending_shop_credits", spent)):
        _check(summary[key] == value)
    _check(summary["initial_household_credits"] + earned == balance + spent)
    resident_ids = set()
    for row in residents:
        _identity(row, simulation_id, world_id)
        rid = row["resident_id"]
        _check(isinstance(rid, str) and rid and rid not in resident_ids)
        resident_ids.add(rid)
        _check(row["_id"] == simulation_id + ":" + rid)
        _check(row["illustrative_sample"] is True and row["population_weight"] == 1)
        _check(row["starting_credits"] == starting)
        _check(starting + _integer(row["credits_earned"]) - _integer(row["credits_spent"])
               == _integer(row["ending_balance"]))
        _check(1 <= _integer(row["earnings_order_rank"]) <= population)
        _integer(row["jobs_completed"])
        _integer(row["home_version"])
        _check(_integer(row["packs_opened"]) * products[parameters["purchase_sku"]]["price_credits"]
               == row["credits_spent"])
        _check(set(row["owned_home_item_ids"]).issubset(items))
        _check(set(row["inventory_quantities"]).issubset(items))
        for item, quantity in row["inventory_quantities"].items():
            _integer(quantity)
        _check(all(row["inventory_quantities"].get(item, 0) >= 1 for item in row["owned_home_item_ids"]))


def load_demo(package_path=None):
    """Return the validated 50-day/200-resident demo, or an explicit unavailable state."""
    package = Path(package_path) if package_path is not None else PACKAGE
    root = package / "demo"
    try:
        manifest = json.loads(_read(root / "manifest.json"))
        _check(manifest.get("synthetic") is True)
        simulation_id, world_id = manifest["simulation_id"], manifest["world_id"]
        _check(isinstance(simulation_id, str) and simulation_id.startswith("sim-"))
        _check(isinstance(world_id, str) and bool(world_id))
        verified = {}
        data = {}
        for name in DATA_FILES:
            raw = _read(root / name)
            expected = manifest["files"][name]
            digest = hashlib.sha256(raw).hexdigest()
            _check(len(raw) == expected["bytes"] and digest == expected["sha256"])
            if name.endswith(".jsonl"):
                rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
                _check(len(rows) == expected["records"])
                data[name] = rows
            else:
                data[name] = json.loads(raw)
            verified[name] = digest
        for filename, field in (("generate.py", "generator_sha256"), ("validate.py", "validator_sha256")):
            digest = hashlib.sha256(_read(package / filename)).hexdigest()
            _check(digest == manifest[field])
            verified[filename] = digest
        summary, days, residents = (data[name] for name in
                                    ("economy_totals.json", "daily_summaries.jsonl", "sample_residents.jsonl"))
        _validate(summary, days, residents, data["catalog.json"], data["parameters.json"], simulation_id, world_id)
        report = json.loads(_read(root / "validation_report.json"))
        _check(report["synthetic"] is True and report["simulation_id"] == simulation_id)
        _check(manifest["method"]["income"] == "weighted_cohort_demo")
        provenance = {
            "bundle_verified": True, "bundled_data_sha256": verified,
            "simulation_version": manifest["simulation_version"], "seed": manifest["seed"],
            "income_mode": manifest["method"]["income"], "estimates": manifest["method"]["estimates"],
            "representative_trajectories": manifest["method"]["representative_trajectories"],
            "no_model_runs": manifest["method"]["no_model_runs"],
            "sample_included_not_additive": True, "sample_method": manifest["method"]["sample_method"],
            "source_simulation_id": manifest["parameters"].get("source_simulation_id"),
            "source_earnings_sha256": manifest["parameters"].get("source_earnings_sha256"),
            "original_validation": report,
            "validation_scope": "Bundled hashes, 50 daily accounts, and 200 final sample states; omitted histories were not revalidated",
            "optional_assets": [name for name in manifest["files"] if name not in DATA_FILES],
            "parameters": data["parameters.json"],
        }
        return {"available": True, "synthetic": True, "simulation_id": simulation_id, "world_id": world_id,
                "summary": summary, "days": days, "residents": residents,
                "catalog": data["catalog.json"], "provenance": provenance}
    except (OSError, ValueError, KeyError, TypeError, AttributeError, UnicodeError, RecursionError):
        return {"available": False, "synthetic": True,
                "error": "The synthetic economy bundle is unavailable or failed validation"}


def atlas_documents(payload):
    """Prepare only simulation collections; callers own explicit Atlas delivery."""
    if not payload.get("available"):
        return
    _check(payload.get("synthetic") is True and payload["provenance"]["bundle_verified"] is True)
    simulation_id, world_id = payload["simulation_id"], payload["world_id"]
    _validate(payload["summary"], payload["days"], payload["residents"], payload["catalog"],
              payload["provenance"]["parameters"], simulation_id, world_id)
    common = {"synthetic": True, "simulation_id": simulation_id, "world_id": world_id}
    yield "simulation_runs", dict(common, _id="simulation:" + simulation_id + ":run",
                                  record_grain="scenario", summary=copy.deepcopy(payload["summary"]),
                                  provenance=copy.deepcopy(payload["provenance"]), catalog=copy.deepcopy(payload["catalog"]))
    for row in payload["days"]:
        document = copy.deepcopy(row)
        document.update(_id="simulation:" + simulation_id + ":day:" + format(row["day"], "03d"),
                        source_id=row["_id"], record_grain="weighted_population_day")
        yield "simulation_daily_summaries", document
    for row in payload["residents"]:
        document = copy.deepcopy(row)
        document.update(_id="simulation:" + simulation_id + ":resident:" + row["resident_id"],
                        source_id=row["_id"], record_grain="illustrative_sample_final_state",
                        sample_included_not_additive=True)
        yield "simulation_residents", document
