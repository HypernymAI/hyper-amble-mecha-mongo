#!/usr/bin/env python3
"""Local synthetic economy and funded loot generator. No network/model/database service calls."""
import argparse
import bisect
import csv
import gzip
import hashlib
import io
import json
import platform
import re
import resource
import sqlite3
import sys
import time
from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

VERSION = "2.0.0"
HERE = Path(__file__).resolve().parent


def encoded(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


@contextmanager
def writer(path):
    """Deterministic gzip headers; UTF-8 and LF on all platforms."""
    with open(path, "wb") as raw:
        if str(path).endswith(".gz"):
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6) as compressed:
                with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
                    yield text
        else:
            with io.TextIOWrapper(raw, encoding="utf-8", newline="") as text:
                yield text


def rng(seed, domain):
    value = int.from_bytes(hashlib.sha256(f"{seed}:{domain}".encode()).digest()[:16], "big")
    return np.random.Generator(np.random.PCG64(value))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, name):
    require(type(value) is int and value >= 0, f"{name} must be a nonnegative integer")
    return value


def read_settings(args):
    p = json.loads(args.parameters.read_text())
    catalog = json.loads(args.catalog.read_text())
    require(p.get("synthetic") is True and catalog.get("synthetic") is True, "Parameters and catalog must declare synthetic:true")
    p["seed"] = args.seed if args.seed is not None else p["seed"]
    p["days"] = args.days if args.days is not None else p["days"]
    if args.purchase_sku:
        p["purchase_sku"] = args.purchase_sku
    integer(p["starting_credits"], "starting_credits")
    integer(p["days"], "days")
    require(p["days"] > 0, "days must be positive")
    date.fromisoformat(p["start_date"])
    require(p["purchase_probability_when_affordable"] == 1, "The income-ordered policy requires purchase probability 1")
    products = {x["sku_id"]: x for x in catalog["products"]}
    items = {x["item_id"]: x for x in catalog["items"]}
    require(len(products) == len(catalog["products"]) and len(items) == len(catalog["items"]), "Duplicate catalog IDs")
    for x in catalog["products"]:
        require(integer(x["price_credits"], "price_credits") > 0, "Prices must be positive")
        require(x["unlock_criteria"] is None, "This generator supports unlocked SKUs only")
        require(all(c["item_id"] in items for c in x["item_contents"]), "Unknown content item")
        if x["kind"] == "pack":
            require(x["ownership"] == "consumable", "Selected pack model requires repeatable consumable containers")
            probs = [x["outcome_probabilities"][k] for k in ("empty", "one_item", "two_items")]
            require(all(0 <= z <= 1 for z in probs) and abs(sum(probs) - 1) < 1e-12, "Pack odds must sum to 1")
            require(x["item_contents"] and all(c["weight"] > 0 for c in x["item_contents"]), "Positive content weights required")
    require(all(x["ownership"] in ("consumable", "permanent") for x in items.values()), "Unknown item ownership mode")
    require(p["purchase_sku"] in products and products[p["purchase_sku"]]["kind"] == "pack", "purchase_sku must be a pack")
    require(p["wealth_bin_lower_bounds"][0] == 0 and p["wealth_bin_lower_bounds"] == sorted(set(p["wealth_bin_lower_bounds"])), "Invalid wealth bins")
    for role, values in p["professions"].items():
        require(role in ("healthcare", "finance", "construction"), "Only the three fictional sandbox professions are supported")
        require(values["share"] > 0 and values["wage_cycle"], f"Invalid profession {role}")
        for wage in values["wage_cycle"]:
            integer(wage, "wage")
    for profile in p["demo_activity_profiles"]:
        require(profile["share"] > 0, "Profile shares must be positive")
        for key in ("active_probability", "second_job_probability"):
            require(0 <= profile[key] <= 1, f"Invalid {key}")
    return p, catalog, products, items


def demo_trajectories(p, population, cohorts):
    r = rng(p["seed"], "income")
    roles = list(p["professions"])
    role_weights = np.array([p["professions"][x]["share"] for x in roles], dtype=float)
    profiles = p["demo_activity_profiles"]
    profile_weights = np.array([x["share"] for x in profiles], dtype=float)
    first = 1
    for idx in range(cohorts):
        weight = population // cohorts + (idx < population % cohorts)
        role = str(r.choice(roles, p=role_weights / role_weights.sum()))
        profile = profiles[int(r.choice(len(profiles), p=profile_weights / profile_weights.sum()))]
        jobs = 0
        path = []
        for _ in range(p["days"]):
            n = (1 + int(r.random() < profile["second_job_probability"])) if r.random() < profile["active_probability"] else 0
            cycle = p["professions"][role]["wage_cycle"]
            earned = sum(cycle[(jobs + j) % len(cycle)] for j in range(n))
            jobs += n
            path.append([n, earned, None])
        yield {"trajectory_id": f"cohort-{idx + 1:06d}", "profession": role, "profile": profile["id"], "population_weight": int(weight), "first_population_index": first, "path": path}
        first += weight


def external_trajectories(path, p):
    opener = gzip.open if str(path).endswith(".gz") else open
    prior_id = None
    count = 0
    current = None
    with opener(path, "rt", encoding="utf-8-sig", newline="") as f:
        rows = csv.DictReader(f)
        require(set(("resident_id", "day", "profession", "jobs_completed", "credits_earned", "synthetic")).issubset(rows.fieldnames or []), "Missing required CSV columns; see EARNINGS_HANDOFF.txt")
        for line, row in enumerate(rows, 2):
            rid = row["resident_id"]
            require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", rid) is not None, f"Invalid resident ID at line {line}")
            require(row["synthetic"].lower() in ("true", "1"), f"Input must explicitly be synthetic at line {line}")
            require(row["profession"] in p["professions"], f"Unknown profession at line {line}")
            if current is None or rid != current["trajectory_id"]:
                if current:
                    require(len(current["path"]) == p["days"], f"Incomplete resident {prior_id}")
                    yield current
                require(prior_id is None or rid > prior_id, f"Input must be sorted by resident_id, day: line {line}")
                count += 1
                current = {"trajectory_id": rid, "profession": row["profession"], "profile": "supplied_earnings", "population_weight": 1, "first_population_index": count, "path": []}
                prior_id = rid
            require(row["profession"] == current["profession"], f"Profession changed for {rid}")
            day, jobs, earned = (int(row[x]) for x in ("day", "jobs_completed", "credits_earned"))
            require(day == len(current["path"]) + 1 and day <= p["days"], f"Missing, duplicate, or unordered day for {rid}")
            require(0 <= jobs <= 10000 and 0 <= earned <= 10**12 and (jobs > 0 or earned == 0), f"Invalid jobs/earnings at line {line}")
            wages = json.loads(row["job_wages"]) if row.get("job_wages", "").strip() else None
            if wages is not None:
                require(isinstance(wages, list) and len(wages) == jobs and all(type(x) is int and x >= 0 for x in wages) and sum(wages) == earned, f"Invalid job_wages at line {line}")
            current["path"].append([jobs, earned, wages])
        if current:
            require(len(current["path"]) == p["days"], f"Incomplete resident {prior_id}")
            yield current


class Detail:
    def __init__(self, resident_id, trajectory, shared, p, sku, items, event_file, day_file, sample_stats, source_mode):
        self.rid, self.t, self.shared, self.p, self.sku, self.items = resident_id, trajectory, shared, p, sku, items
        self.ef, self.df, self.stats, self.source_mode = event_file, day_file, sample_stats, source_mode
        self.rng = rng(p["seed"], "detail:" + resident_id)
        self.balance = self.seq = self.jobs = self.pack_seq = self.home_version = 0
        self.inventory, self.home = Counter(), set()
        self.last_event = self.last_wage = None
        self.earned = self.spent = 0
        self.day, self.second = 1, 0
        self.emit("resident_initialized", p["starting_credits"], credit_source="synthetic_initial_grant")

    def emit(self, kind, delta=0, **extra):
        self.seq += 1
        eid = f"{self.shared['simulation_id']}:{self.rid}:event:{self.seq:08d}"
        when = datetime.combine(date.fromisoformat(self.p["start_date"]), datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=self.day-1, seconds=self.second)
        require(self.second < 86400, "Detailed day exceeds timestamp capacity; lower sample workload")
        row = {**self.shared, "_id": eid, "event_id": eid, "resident_id": self.rid, "trajectory_id": self.t["trajectory_id"], "population_weight": 1, "profession": self.t["profession"], "day": self.day, "timestamp": when.isoformat().replace("+00:00", "Z"), "event_sequence": self.seq, "event_type": kind, "previous_event_id": self.last_event, "balance_before": self.balance, "credits_delta": delta, "balance_after": self.balance + delta, **extra}
        self.balance += delta
        require(self.balance >= 0, "Negative sample wallet")
        self.ef.write(encoded(row) + "\n")
        self.last_event = eid
        self.second += 1
        return eid

    def step(self, d, n, earned, wages, expected_openings):
        self.day, self.second = d+1, 3600
        opening_balance = self.balance
        role = self.t["profession"]
        if self.source_mode:
            if wages is None:
                wages = [earned // n + (i < earned % n) for i in range(n)] if n else []
                allocation = "synthetic_even_split_of_supplied_daily_total"
            else:
                allocation = "supplied_job_wages"
        else:
            cycle = self.p["professions"][role]["wage_cycle"]
            wages = [cycle[(self.jobs + i) % len(cycle)] for i in range(n)]
            allocation = "sandbox_sequence_wage"
        for wage in wages:
            self.jobs += 1
            jid = f"{self.shared['simulation_id']}:{self.rid}:job:{self.jobs:08d}"
            je = self.emit("job_completed", job_id=jid, job_sequence=self.jobs, job_kind={"healthcare": "fictional_clinic_supply_tally", "finance": "fictional_market_budget", "construction": "fictional_courtyard_tile_count"}[role], model_run=False, wage_allocation_method=allocation)
            self.last_wage = self.emit("wage", int(wage), job_id=jid, source_job_event_id=je, wage_allocation_method=allocation)
        self.earned += earned
        qty = self.balance // self.sku["price_credits"]
        require(qty == expected_openings, "Sample diverged from trajectory")
        require(qty <= 10000, "More than 10,000 sample openings in one day; reduce sample workload")
        purchase_id = None
        if qty:
            cost = qty * self.sku["price_credits"]
            purchase_id = self.emit("pack_purchase", -cost, sku_id=self.sku["sku_id"], quantity=qty, unit_price_credits=self.sku["price_credits"], latest_wage_event_id=self.last_wage, funding_note="Fungible wallet; latest wage is a causal reference, not exclusive funding")
            self.spent += cost
        probs = self.sku["outcome_probabilities"]
        choices = self.sku["item_contents"]
        weights = np.array([x["weight"] for x in choices], dtype=float)
        for _ in range(qty):
            self.pack_seq += 1
            u = self.rng.random()
            slots = 0 if u < probs["empty"] else 1 if u < probs["empty"] + probs["one_item"] else 2
            pack_id = f"{self.shared['simulation_id']}:{self.rid}:pack:{self.pack_seq:08d}"
            drops = [{"item_id": choices[int(self.rng.choice(len(choices), p=weights/weights.sum()))]["item_id"], "item_instance_id": f"{pack_id}:item:{s+1}"} for s in range(slots)]
            oe = self.emit("pack_opening", pack_instance_id=pack_id, source_purchase_event_id=purchase_id, sku_id=self.sku["sku_id"], outcome=("empty", "one_item", "two_items")[slots], items=drops)
            self.stats[d]["outcomes"][slots] += 1
            for item in drops:
                item_id = item["item_id"]
                permanent = self.items[item_id]["ownership"] == "permanent"
                before = self.inventory[item_id]
                if permanent:
                    self.inventory[item_id] += 1
                ie = self.emit("item_received", **item, source_opening_event_id=oe, ownership=self.items[item_id]["ownership"], inventory_quantity_before=before, inventory_quantity_after=self.inventory[item_id], consumed_immediately=not permanent)
                self.stats[d]["items"][item_id] += 1
                if permanent and item_id not in self.home:
                    old = self.home_version
                    self.home_version += 1
                    self.home.add(item_id)
                    self.emit("home_change", item_id=item_id, source_item_event_id=ie, source_opening_event_id=oe, change="place_first_copy", home_version_before=old, home_version_after=self.home_version, owned_home_item_ids=sorted(self.home))
        record = {**self.shared, "_id": f"{self.shared['simulation_id']}:{self.rid}:day:{d+1:03d}", "resident_id": self.rid, "trajectory_id": self.t["trajectory_id"], "profession": role, "day": d+1, "date": (date.fromisoformat(self.p["start_date"]) + timedelta(days=d)).isoformat(), "opening_balance": opening_balance, "jobs_completed": n, "credits_earned": earned, "credits_spent": qty*self.sku["price_credits"], "closing_balance": self.balance, "packs_opened": qty, "purchase_event_id": purchase_id, "latest_event_id": self.last_event, "home_version": self.home_version, "owned_home_item_ids": sorted(self.home)}
        self.df.write(encoded(record) + "\n")

    def final(self, rank):
        return {**self.shared, "_id": f"{self.shared['simulation_id']}:{self.rid}", "resident_id": self.rid, "trajectory_id": self.t["trajectory_id"], "profession": self.t["profession"], "population_weight": 1, "trajectory_population_weight": self.t["population_weight"], "illustrative_sample": True, "earnings_order_rank": rank, "starting_credits": self.p["starting_credits"], "credits_earned": self.earned, "credits_spent": self.spent, "ending_balance": self.balance, "jobs_completed": self.jobs, "packs_opened": self.pack_seq, "home_version": self.home_version, "owned_home_item_ids": sorted(self.home), "inventory_quantities": dict(self.inventory), "last_event_id": self.last_event}


def run(args):
    started = time.perf_counter()
    p, catalog, products, items = read_settings(args)
    population = args.population if args.population is not None else (5_000_000 if args.preset == "target" else 50_000)
    cohorts = min(args.cohorts if args.cohorts is not None else (20_000 if args.preset == "target" else 1000), population)
    if args.earnings:
        cohorts = population
    require(1 <= args.sample_size <= cohorts <= population and population <= 100_000_000, "Require 1 <= sample size <= trajectories <= population <= 100m")
    require(not args.out.exists() or not any(args.out.iterdir()), "Output directory must be absent or empty; use a new --out")
    args.out.mkdir(parents=True, exist_ok=True)
    source_hash = digest(args.earnings) if args.earnings else None
    generator_hash = digest(Path(__file__))
    mode = "supplied_synthetic_earnings" if args.earnings else "weighted_cohort_demo"
    effective = {**p, "population": population, "representative_trajectories": cohorts, "detailed_sample_size": args.sample_size, "mode": mode, "source_earnings_sha256": source_hash, "source_simulation_id": args.source_simulation_id, "simulation_version": VERSION}
    identity = {"parameters": effective, "catalog": catalog, "generator_sha256": generator_hash, "numpy_version": np.__version__}
    simulation_id = "sim-" + hashlib.sha256(encoded(identity).encode()).hexdigest()[:20]
    shared = {"synthetic": True, "world_id": p["world_id"], "simulation_id": simulation_id}
    sample_indices = sorted(int(x) for x in rng(p["seed"], "sample-selection").choice(cohorts, size=args.sample_size, replace=False))
    sample_set = set(sample_indices)
    sample_rng = rng(p["seed"], "sample-members")
    sku = products[p["purchase_sku"]]
    bounds = p["wealth_bin_lower_bounds"]
    days = [{"jobs": 0, "active": 0, "earned": 0, "spent": 0, "closing": 0, "opened": 0, "min": None, "max": 0, "bins": [0]*len(bounds), "roles": {r: {"population": 0, "active_ambles": 0, "jobs_completed": 0, "credits_earned": 0, "credits_spent": 0, "closing_balance": 0} for r in p["professions"]}} for _ in range(p["days"])]
    sample_stats = [{"outcomes": [0, 0, 0], "items": Counter()} for _ in days]
    detail_objects = {}
    db_path = args.out / ".wallet-sort.sqlite"
    db = sqlite3.connect(db_path)
    db.execute("PRAGMA journal_mode=OFF")
    db.execute("PRAGMA synchronous=OFF")
    db.execute("PRAGMA temp_store=FILE")
    db.execute("CREATE TABLE wallets (id TEXT, profession TEXT, weight INTEGER, first_index INTEGER, earned INTEGER, spent INTEGER, balance INTEGER, jobs INTEGER, packs INTEGER)")
    retain_audit = not args.earnings or args.retain_trajectories
    counts = {}
    audit_path = args.out / "trajectory_audit.jsonl.gz"
    with writer(args.out / "sample_events.jsonl.gz") as ef, writer(args.out / "sample_daily.jsonl") as df:
        audit_context = writer(audit_path) if retain_audit else None
        af = audit_context.__enter__() if audit_context else None
        count, represented = 0, 0
        try:
            stream = external_trajectories(args.earnings, p) if args.earnings else demo_trajectories(p, population, cohorts)
            for idx, t in enumerate(stream):
                require(idx < cohorts, "Input has more residents than --population")
                weight, role = t["population_weight"], t["profession"]
                detail = None
                if idx in sample_set:
                    offset = int(sample_rng.integers(weight))
                    rid = t["trajectory_id"] if args.earnings else f"amble-{t['first_population_index'] + offset:09d}"
                    detail = Detail(rid, t, shared, p, sku, items, ef, df, sample_stats, bool(args.earnings))
                    detail_objects[t["trajectory_id"]] = detail
                balance = p["starting_credits"]
                total_earned = total_jobs = total_packs = 0
                for d, (jobs, earned, wages) in enumerate(t["path"]):
                    balance += earned
                    opened = balance // sku["price_credits"]
                    spent = opened * sku["price_credits"]
                    balance -= spent
                    total_jobs += jobs
                    total_earned += earned
                    total_packs += opened
                    s = days[d]
                    for key, value in (("jobs", jobs), ("active", int(jobs>0)), ("earned", earned), ("spent", spent), ("closing", balance), ("opened", opened)):
                        s[key] += value * weight
                    s["min"] = balance if s["min"] is None else min(s["min"], balance)
                    s["max"] = max(s["max"], balance)
                    s["bins"][bisect.bisect_right(bounds, balance)-1] += weight
                    for key, value in (("population", 1), ("active_ambles", int(jobs>0)), ("jobs_completed", jobs), ("credits_earned", earned), ("credits_spent", spent), ("closing_balance", balance)):
                        s["roles"][role][key] += value * weight
                    if detail:
                        detail.step(d, jobs, earned, wages, opened)
                total_spent = total_packs * sku["price_credits"]
                db.execute("INSERT INTO wallets VALUES (?,?,?,?,?,?,?,?,?)", (t["trajectory_id"], role, weight, t["first_population_index"], total_earned, total_spent, balance, total_jobs, total_packs))
                if af:
                    af.write(encoded({**shared, "_id": f"{simulation_id}:{t['trajectory_id']}", **t, "starting_credits": p["starting_credits"], "credits_earned": total_earned, "credits_spent": total_spent, "ending_balance": balance, "packs_opened": total_packs}) + "\n")
                count += 1
                represented += weight
                if count % 10000 == 0:
                    db.commit()
            require(count == cohorts and represented == population, f"Input resident count {count}, expected {cohorts}")
        finally:
            if audit_context:
                audit_context.__exit__(*sys.exc_info())
    db.commit()
    if retain_audit:
        counts[audit_path.name] = cohorts
    counts["sample_events.jsonl.gz"] = sum(x.seq for x in detail_objects.values())
    counts["sample_daily.jsonl"] = args.sample_size * p["days"]
    ranks = {}
    fields = ["synthetic", "world_id", "simulation_id", "trajectory_id", "profession", "population_weight", "rank_start", "rank_end", "credits_earned", "credits_spent", "ending_balance", "jobs_completed", "packs_opened"]
    with writer(args.out / "ranked_wallets.csv.gz") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        rank = 1
        for tid, role, weight, first, earned, spent, balance, jobs, packs in db.execute("SELECT * FROM wallets ORDER BY earned DESC, id ASC"):
            w.writerow({**shared, "synthetic": "true", "trajectory_id": tid, "profession": role, "population_weight": weight, "rank_start": rank, "rank_end": rank+weight-1, "credits_earned": earned, "credits_spent": spent, "ending_balance": balance, "jobs_completed": jobs, "packs_opened": packs})
            if tid in detail_objects:
                detail = detail_objects[tid]
                ranks[tid] = rank if args.earnings else rank + int(detail.rid.split("-")[-1]) - first
            rank += weight
    counts["ranked_wallets.csv.gz"] = cohorts
    db.close()
    db_path.unlink()
    with writer(args.out / "sample_residents.jsonl") as f:
        for tid in sorted(detail_objects):
            f.write(encoded(detail_objects[tid].final(ranks[tid])) + "\n")
    counts["sample_residents.jsonl"] = args.sample_size
    loot_rng = rng(p["seed"], "bulk-loot")
    outcome_keys = ("empty", "one_item", "two_items")
    outcome_probs = [sku["outcome_probabilities"][k] for k in outcome_keys]
    content = sku["item_contents"]
    item_weights = np.array([x["weight"] for x in content], dtype=float)
    summaries, outcome_rows, item_rows = [], [], []
    earned_total = spent_total = jobs_total = opened_total = active_total = drop_total = empty_total = 0
    opening = population * p["starting_credits"]
    for d, s in enumerate(days):
        sample_outcomes = sample_stats[d]["outcomes"]
        bulk_n = s["opened"] - sum(sample_outcomes)
        bulk = [int(x) for x in loot_rng.multinomial(bulk_n, outcome_probs)]
        outcomes = [bulk[i] + sample_outcomes[i] for i in range(3)]
        slots = bulk[1] + 2*bulk[2]
        bulk_items = loot_rng.multinomial(slots, item_weights/item_weights.sum())
        drops = Counter({x["item_id"]: int(bulk_items[i]) for i, x in enumerate(content)})
        drops.update(sample_stats[d]["items"])
        earned_total += s["earned"]
        spent_total += s["spent"]
        jobs_total += s["jobs"]
        opened_total += s["opened"]
        active_total += s["active"]
        drop_total += sum(drops.values())
        empty_total += outcomes[0]
        day = d+1
        day_date = (date.fromisoformat(p["start_date"]) + timedelta(days=d)).isoformat()
        histogram = [{"lower_inclusive": b, "upper_exclusive": bounds[i+1] if i+1 < len(bounds) else None, "population": s["bins"][i]} for i, b in enumerate(bounds)]
        summaries.append({**shared, "_id": f"{simulation_id}:day:{day:03d}", "day": day, "date": day_date, "population": population, "resident_days": population, "cumulative_resident_days": day*population, "active_ambles": s["active"], "jobs_completed": s["jobs"], "opening_household_credits": opening, "credits_earned": s["earned"], "credits_spent": s["spent"], "closing_household_credits": s["closing"], "cumulative_credits_earned": earned_total, "cumulative_shop_credits": spent_total, "total_credits_issued_including_initial": population*p["starting_credits"]+earned_total, "packs_bought_by_sku": {k: s["opened"] if k == sku["sku_id"] else 0 for k, v in products.items() if v["kind"] == "pack"}, "furnishings_bought_by_sku": {k: 0 for k, v in products.items() if v["kind"] == "furnishing"}, "packs_opened": s["opened"], "pack_outcomes": dict(zip(outcome_keys, outcomes)), "item_drops_by_id": {k: drops[k] for k in items}, "wealth": {"measure": "liquid_credits_after_daily_spending", "min": s["min"], "max": s["max"], "mean": s["closing"]/population, "histogram": histogram}, "by_profession": s["roles"], "aggregate_method": "weighted_cohort_projection" if not args.earnings else "exact_supplied_earnings_wallets_with_synthetic_loot", "sample_included_not_additive": True})
        for k, v in products.items():
            if v["kind"] == "pack":
                outcome_rows.append({**shared, "day": day, "date": day_date, "sku_id": k, "packs_bought": s["opened"] if k == sku["sku_id"] else 0, "packs_opened": s["opened"] if k == sku["sku_id"] else 0, **dict(zip(outcome_keys, outcomes if k == sku["sku_id"] else [0,0,0]))})
        for k in items:
            item_rows.append({**shared, "day": day, "date": day_date, "item_id": k, "item_drops": drops[k], "ownership": items[k]["ownership"]})
        opening = s["closing"]
    dump(args.out / "daily_summaries.json", summaries)
    with writer(args.out / "daily_summaries.jsonl") as f:
        f.writelines(encoded(x)+"\n" for x in summaries)
    counts["daily_summaries.json"] = counts["daily_summaries.jsonl"] = len(summaries)
    flat_fields = ["synthetic", "world_id", "simulation_id", "day", "date", "population", "resident_days", "active_ambles", "jobs_completed", "opening_household_credits", "credits_earned", "credits_spent", "closing_household_credits", "cumulative_credits_earned", "cumulative_shop_credits", "packs_opened"]
    flat = [{**{k: x[k] for k in flat_fields}, **{f"bought_{k}": v for k,v in x["packs_bought_by_sku"].items()}, "wealth_min": x["wealth"]["min"], "wealth_max": x["wealth"]["max"], "wealth_mean": x["wealth"]["mean"], "empty_openings": x["pack_outcomes"]["empty"], "item_drops": sum(x["item_drops_by_id"].values())} for x in summaries]
    for name, rows in (("daily_summaries.csv", flat), ("pack_outcomes.csv", outcome_rows), ("item_drops.csv", item_rows)):
        with writer(args.out / name) as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            for row in rows:
                w.writerow({**row, "synthetic": "true"})
        counts[name] = len(rows)
    dump(args.out / "parameters.json", {**shared, **effective})
    dump(args.out / "catalog.json", {**shared, **catalog})
    with writer(args.out / "catalog.jsonl") as f:
        for product in catalog["products"]:
            f.write(encoded({**shared, "_id": f"{simulation_id}:sku:{product['sku_id']}", **product}) + "\n")
    counts["catalog.jsonl"] = len(catalog["products"])
    totals = {"population": population, "days": p["days"], "resident_days": population*p["days"], "active_resident_days": active_total, "jobs_completed": jobs_total, "initial_household_credits": population*p["starting_credits"], "credits_earned": earned_total, "credits_spent": spent_total, "ending_household_credits": summaries[-1]["closing_household_credits"], "ending_shop_credits": spent_total, "packs_opened": opened_total, "empty_openings": empty_total, "item_drops": drop_total, "opening_target": p["target_pack_openings"], "openings_short_of_target": max(0, p["target_pack_openings"]-opened_total), "openings_above_target": max(0, opened_total-p["target_pack_openings"])}
    dump(args.out / "economy_totals.json", {**shared, **totals})
    files = {x.name: {"sha256": digest(x), "bytes": x.stat().st_size, "records": counts.get(x.name)} for x in sorted(args.out.iterdir()) if x.is_file()}
    manifest = {**shared, "simulation_version": VERSION, "generator_version": VERSION, "generator_sha256": generator_hash, "validator_sha256": digest(HERE/"validate.py") if (HERE/"validate.py").exists() else None, "numpy_version": np.__version__, "python_version": platform.python_version(), "prng": "NumPy PCG64, separate SHA-256-derived income/sample/member/detail/bulk streams", "seed": p["seed"], "parameters": effective, "files": files, "totals": totals, "source_earnings": {"sha256": source_hash, "rows_expected": population*p["days"] if args.earnings else None, "job_wages_missing_policy": "synthetic even split within supplied job count"}, "method": {"income": mode, "estimates": not bool(args.earnings), "representative_trajectories": cohorts, "weighted_population": population, "trajectory_audit_included": retain_audit, "sample_method": "Uniform distinct trajectories; one uniform member each. Sample is included in population and loot totals. Cohort weights may differ by one; sample is illustrative, not a separate unbiased estimator.", "loot": "Exact seeded multinomial draws for remaining opening outcomes and item slots per day, plus explicit included sample outcomes. Items independent with replacement. No 500m individual IDs fabricated.", "ranking": "Descending total earned credits, trajectory ID tie-break, then member index. Same starting credits and SKU for every resident make cumulative pack counts monotonic in earnings.", "wealth": "Liquid credits only. Exact weighted fixed-bin histogram; no item valuation. Pack drops cannot affect balances.", "cash_equation": "initial credits + cumulative wages = household balances + shop balances", "target_policy": "500m is a benchmark, not forced or capped. Open only paid packs; report actual, shortfall or excess.", "no_model_runs": True, "fictional_jobs_only": True}, "hash_scope": "files covers all deterministic dataset artifacts, excluding this manifest and runtime/validation sidecars. Generator/validator separately hashed. Run metrics vary by machine/run."}
    dump(args.out / "manifest.json", manifest)
    elapsed = time.perf_counter() - started
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    metrics = {**shared, "generation_seconds": round(elapsed, 6), "peak_rss_bytes": rss if sys.platform == "darwin" else rss*1024, "artifact_bytes_before_metrics": sum(x.stat().st_size for x in args.out.iterdir() if x.is_file()), "artifact_sizes_before_metrics": {x.name: x.stat().st_size for x in sorted(args.out.iterdir()) if x.is_file()}, "timing_scope": "settings, optional source hashing, simulation, sample events, wallet disk sort, serialization, gzip and manifest hashing; excludes validation", "python": sys.version, "numpy": np.__version__, "external_source_run": bool(args.earnings)}
    dump(args.out / "run_metrics.json", metrics)
    print(encoded({"output": str(args.out), "simulation_id": simulation_id, "generation_seconds": metrics["generation_seconds"], "bytes_before_metrics": metrics["artifact_bytes_before_metrics"], "totals": totals}))


def main():
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--preset", choices=("preview", "target"), default="preview")
    a.add_argument("--out", type=Path, default=Path("preview"))
    a.add_argument("--parameters", type=Path, default=HERE/"parameters.json")
    a.add_argument("--catalog", type=Path, default=HERE/"catalog.json")
    a.add_argument("--population", type=int)
    a.add_argument("--cohorts", type=int)
    a.add_argument("--days", type=int)
    a.add_argument("--sample-size", type=int, default=200)
    a.add_argument("--seed", type=int)
    a.add_argument("--purchase-sku")
    a.add_argument("--earnings", type=Path, help="Authoritative synthetic daily earnings CSV or CSV.gz sorted resident_id,day")
    a.add_argument("--source-simulation-id", help="Provenance ID from the earnings producer's manifest, if supplied")
    a.add_argument("--retain-trajectories", action="store_true", help="Also retain compact full input paths in external mode (additional storage)")
    args = a.parse_args()
    try:
        run(args)
    except (ValueError, KeyError) as exc:
        a.error(str(exc))


if __name__ == "__main__":
    main()
