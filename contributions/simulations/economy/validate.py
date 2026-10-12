#!/usr/bin/env python3
"""Independent artifact/accounting validator; uses the Python standard library only."""
import argparse
import bisect
import csv
import gzip
import hashlib
import json
import sqlite3
import tempfile
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path


def check(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1024*1024), b""):
            h.update(b)
    return h.hexdigest()


def jsonl(path):
    op = gzip.open if str(path).endswith(".gz") else open
    with op(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def csvrows(path):
    op = gzip.open if str(path).endswith(".gz") else open
    with op(path, "rt", encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


def validate(root):
    started = time.perf_counter()
    m = json.loads((root/"manifest.json").read_text())
    p = m["parameters"]
    n, dcount, sample_n = p["population"], p["days"], p["detailed_sample_size"]
    sim, world = m["simulation_id"], m["world_id"]
    skipped, checks = [], []
    for name, entry in m["files"].items():
        path = root/name
        check(path.is_file() and path.stat().st_size == entry["bytes"] and sha(path) == entry["sha256"], f"Hash/size mismatch: {name}")
        if entry["records"] is not None:
            rows = csvrows(path) if ".csv" in name else jsonl(path) if ".jsonl" in name else json.loads(path.read_text())
            check(sum(1 for _ in rows) == entry["records"], f"Record count: {name}")
    code = Path(__file__).resolve().parent
    check(sha(code/"generate.py") == m["generator_sha256"], "Generator hash does not match tested dataset")
    check(sha(Path(__file__)) == m["validator_sha256"], "Validator hash does not match manifest")
    checks.append("Manifest data hashes, sizes, declared counts, generator and validator hashes")
    catalog = json.loads((root/"catalog.json").read_text())
    products = {x["sku_id"]: x for x in catalog["products"]}
    item_table = {x["item_id"]: x for x in catalog["items"]}
    sku = products[p["purchase_sku"]]
    price = sku["price_credits"]
    check(price > 0, "Positive pack price")
    def common(row):
        check(row.get("synthetic") is True and row.get("simulation_id") == sim and row.get("world_id") == world, "Record provenance mismatch")
    daily = list(jsonl(root/"daily_summaries.jsonl"))
    check(daily == json.loads((root/"daily_summaries.json").read_text()), "JSON and JSONL summaries disagree")
    check(len(daily) == dcount and len({x["_id"] for x in daily}) == dcount, "Daily count or unique IDs")
    starting = n*p["starting_credits"]
    previous = starting
    earned_total = spent_total = jobs_total = opened_total = active_total = empty_total = drop_total = 0
    for i, row in enumerate(daily):
        common(row)
        check(row["day"] == i+1 and row["date"] == (date.fromisoformat(p["start_date"])+timedelta(days=i)).isoformat(), "Daily ordering/date")
        check(row["population"] == row["resident_days"] == n and row["cumulative_resident_days"] == (i+1)*n, "Resident-day population")
        check(0 <= row["active_ambles"] <= n and row["jobs_completed"] >= row["active_ambles"], "Active resident/jobs bounds")
        check(row["opening_household_credits"] == previous, "Daily opening continuity")
        check(previous + row["credits_earned"] - row["credits_spent"] == row["closing_household_credits"] >= 0, "Daily cash reconciliation")
        check(sum(row["packs_bought_by_sku"].values()) == row["packs_opened"], "Every purchased pack opened once")
        check(sum(products[k]["price_credits"]*v for k,v in row["packs_bought_by_sku"].items()) == row["credits_spent"], "Price-times-quantity spend")
        check(all(v == 0 for v in row["furnishings_bought_by_sku"].values()), "Default direct furniture policy")
        check(all(v >= 0 for v in row["pack_outcomes"].values()) and sum(row["pack_outcomes"].values()) == row["packs_opened"], "Opening outcomes partition")
        check(sum(row["item_drops_by_id"].values()) == row["pack_outcomes"]["one_item"]+2*row["pack_outcomes"]["two_items"], "Item drop slot reconciliation")
        earned_total += row["credits_earned"]
        spent_total += row["credits_spent"]
        jobs_total += row["jobs_completed"]
        opened_total += row["packs_opened"]
        active_total += row["active_ambles"]
        empty_total += row["pack_outcomes"]["empty"]
        drop_total += sum(row["item_drops_by_id"].values())
        check(row["cumulative_credits_earned"] == earned_total and row["cumulative_shop_credits"] == spent_total, "Cumulative ledgers")
        check(row["total_credits_issued_including_initial"] == starting+earned_total == row["closing_household_credits"]+spent_total, "Whole economy conservation")
        h = row["wealth"]["histogram"]
        check(sum(x["population"] for x in h) == n and all(x["population"] >= 0 for x in h), "Histogram population")
        check(0 <= row["wealth"]["min"] <= row["wealth"]["max"] < price, "Affordable-spend wallet bounds")
        check(abs(row["wealth"]["mean"]*n-row["closing_household_credits"]) < 1e-6, "Wealth mean")
        for metric in ("population", "active_ambles", "jobs_completed", "credits_earned", "credits_spent"):
            check(sum(x[metric] for x in row["by_profession"].values()) == row[metric], "Profession rollup: "+metric)
        check(sum(x["closing_balance"] for x in row["by_profession"].values()) == row["closing_household_credits"], "Profession balances")
        previous = row["closing_household_credits"]
    totals = {"population": n, "days": dcount, "resident_days": n*dcount, "initial_household_credits": starting, "credits_earned": earned_total, "credits_spent": spent_total, "ending_household_credits": previous, "ending_shop_credits": spent_total, "jobs_completed": jobs_total, "packs_opened": opened_total, "active_resident_days": active_total, "empty_openings": empty_total, "item_drops": drop_total, "opening_target": p["target_pack_openings"], "openings_short_of_target": max(0,p["target_pack_openings"]-opened_total), "openings_above_target": max(0,opened_total-p["target_pack_openings"])}
    check(m["totals"] == totals, "Manifest totals")
    reported = json.loads((root/"economy_totals.json").read_text())
    common(reported)
    check(all(reported[k] == v for k,v in totals.items()), "Economy totals file")
    checks.append("Population, daily/role cash ledgers, issuance/shop conservation, histogram, SKU prices, opening and item counts")
    # Verify ranked wallets independently; use a disk unique index for large supplied populations.
    wallets, selected_paths = {}, {}
    residents = list(jsonl(root/"sample_residents.jsonl"))
    check(len(residents) == sample_n and len({x["resident_id"] for x in residents}) == sample_n, "Sample count/IDs")
    sample_by_tid = {x["trajectory_id"]: x for x in residents}
    check(len(sample_by_tid) == sample_n, "One sampled member per trajectory")
    wallet_sums = Counter()
    last_earned = last_packs = None
    rank, wallet_count = 1, 0
    with tempfile.TemporaryDirectory(prefix="amble-validation-") as tmp:
        db = sqlite3.connect(Path(tmp)/"ids.sqlite")
        db.execute("CREATE TABLE ids (id TEXT PRIMARY KEY)")
        for row in csvrows(root/"ranked_wallets.csv.gz"):
            check(row["synthetic"] == "true" and row["world_id"] == world and row["simulation_id"] == sim, "Wallet provenance")
            db.execute("INSERT INTO ids VALUES (?)", (row["trajectory_id"],))
            values = {k: int(row[k]) for k in ("population_weight", "rank_start", "rank_end", "credits_earned", "credits_spent", "ending_balance", "jobs_completed", "packs_opened")}
            w = values["population_weight"]
            check(w > 0 and values["rank_start"] == rank and values["rank_end"] == rank+w-1, "Contiguous weighted ranking")
            check(p["starting_credits"]+values["credits_earned"]-values["credits_spent"] == values["ending_balance"] >= 0, "Wallet conservation")
            check(values["packs_opened"] == (p["starting_credits"]+values["credits_earned"])//price and values["credits_spent"] == values["packs_opened"]*price, "Lifetime affordable pack capacity")
            if last_earned is not None:
                check(values["credits_earned"] <= last_earned and values["packs_opened"] <= last_packs, "Earnings-to-pack rank monotonicity")
            last_earned, last_packs = values["credits_earned"], values["packs_opened"]
            for k in ("credits_earned", "credits_spent", "ending_balance", "jobs_completed", "packs_opened"):
                wallet_sums[k] += values[k]*w
            if row["trajectory_id"] in sample_by_tid:
                wallets[row["trajectory_id"]] = values
            rank += w
            wallet_count += 1
        db.close()
    check(rank-1 == n and wallet_count == p["representative_trajectories"], "Weighted wallet population")
    for a,b in (("credits_earned","credits_earned"),("credits_spent","credits_spent"),("ending_balance","ending_household_credits"),("jobs_completed","jobs_completed"),("packs_opened","packs_opened")):
        check(wallet_sums[a] == totals[b], "Wallet vs aggregate totals: "+a)
    checks.append("Unique wallet IDs, nonnegative balances, weighted totals, full descending earnings/pack ranking")
    # Independently reconstruct all cohort daily ledgers from compact paths.
    if m["method"]["trajectory_audit_included"]:
        expected = [{"population":0,"active_ambles":0,"jobs_completed":0,"credits_earned":0,"credits_spent":0,"closing_household_credits":0,"packs_opened":0,"bins":[0]*len(p["wealth_bin_lower_bounds"]),"roles":{r:Counter() for r in p["professions"]}} for _ in range(dcount)]
        audit_ids = set()
        for t in jsonl(root/"trajectory_audit.jsonl.gz"):
            common(t)
            check(t["trajectory_id"] not in audit_ids and len(t["path"]) == dcount, "Unique/complete trajectory")
            audit_ids.add(t["trajectory_id"])
            balance, sequence = p["starting_credits"], 0
            total_e = total_p = 0
            for i,(jobs,earned,wages) in enumerate(t["path"]):
                check(type(jobs) is int and type(earned) is int and jobs >= 0 and earned >= 0, "Trajectory integer values")
                if p["mode"] == "weighted_cohort_demo":
                    cycle = p["professions"][t["profession"]]["wage_cycle"]
                    check(earned == sum(cycle[(sequence+j)%len(cycle)] for j in range(jobs)) and jobs <= 2, "Profession/sequence wages")
                if wages is not None:
                    check(len(wages) == jobs and sum(wages) == earned, "Supplied per-job wages")
                sequence += jobs
                balance += earned
                opened = balance//price
                spent = opened*price
                balance -= spent
                total_e += earned
                total_p += opened
                w = t["population_weight"]
                for key,value in (("population",1),("active_ambles",int(jobs>0)),("jobs_completed",jobs),("credits_earned",earned),("credits_spent",spent),("closing_household_credits",balance),("packs_opened",opened)):
                    expected[i][key] += value*w
                    expected[i]["roles"][t["profession"]][key] += value*w
                expected[i]["bins"][bisect.bisect_right(p["wealth_bin_lower_bounds"],balance)-1] += w
            check(t["starting_credits"] == p["starting_credits"] and t["ending_balance"] == balance and t["credits_earned"] == total_e and t["packs_opened"] == total_p and t["credits_spent"] == total_p*price, "Trajectory final state")
            if t["trajectory_id"] in sample_by_tid:
                selected_paths[t["trajectory_id"]] = t
        check(len(audit_ids) == wallet_count, "Trajectory count")
        for i,e in enumerate(expected):
            for key in ("population","active_ambles","jobs_completed","credits_earned","credits_spent","closing_household_credits","packs_opened"):
                check(e[key] == daily[i][key], f"Reconstructed daily {key} day {i+1}")
            check(e["bins"] == [x["population"] for x in daily[i]["wealth"]["histogram"]], "Reconstructed wealth distribution")
            for role, role_values in e["roles"].items():
                for key in ("population","active_ambles","jobs_completed","credits_earned","credits_spent"):
                    check(role_values[key] == daily[i]["by_profession"][role][key], "Reconstructed profession rollup")
        checks.append("All retained trajectory days reconstructed independently, including profession wages and wealth bins")
    else:
        skipped.append("Full per-day reconstruction from external source: source paths not retained; source-file correctness beyond generator's streaming checks is not independently rechecked here")
    # Replay every detailed event, including references, inventory, empty openings and home placement.
    states = {r["resident_id"]:{"balance":0,"seq":0,"last":None,"time":None,"inventory":Counter(),"home":set(),"version":0,"jobs":0,"earned":0,"spent":0,"opened":0} for r in residents}
    events, packs, instances, job_ids = {}, set(), set(), set()
    purchases, opening_drops = Counter(), Counter()
    sample_days = defaultdict(Counter)
    sample_outcomes = [Counter() for _ in range(dcount)]
    sample_items = [Counter() for _ in range(dcount)]
    for e in jsonl(root/"sample_events.jsonl.gz"):
        common(e)
        rid, eid = e["resident_id"], e["event_id"]
        check(eid == e["_id"] and eid not in events and rid in states, "Unique event/resident IDs")
        s = states[rid]
        check(e["event_sequence"] == s["seq"]+1 and e["previous_event_id"] == s["last"], "Per-resident event chain")
        check(eid == f"{sim}:{rid}:event:{e['event_sequence']:08d}", "Stable event ID format")
        when = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
        check(e["timestamp"].endswith("Z") and (s["time"] is None or when > s["time"]), "Strictly increasing UTC timestamp")
        check(1 <= e["day"] <= dcount and when.date() == date.fromisoformat(p["start_date"])+timedelta(days=e["day"]-1), "Event day/date")
        resident = next(x for x in residents if x["resident_id"] == rid)
        check(e["profession"] == resident["profession"] and e["trajectory_id"] == resident["trajectory_id"] and e["population_weight"] == 1, "Sample identity/state ownership")
        check(e["balance_before"] == s["balance"] and e["balance_after"] == s["balance"]+e["credits_delta"] >= 0, "Event balance accounting")
        sd = sample_days[(rid,e["day"])]
        kind = e["event_type"]
        if kind == "resident_initialized":
            check(s["seq"] == 0 and e["credits_delta"] == p["starting_credits"], "Initial grant")
        elif kind == "job_completed":
            check(e["credits_delta"] == 0 and e["job_sequence"] == s["jobs"]+1 and e["model_run"] is False, "Synthetic job sequence")
            check(e["job_id"] not in job_ids and e["job_id"] == f"{sim}:{rid}:job:{e['job_sequence']:08d}", "Unique stable job ID")
            job_ids.add(e["job_id"])
            s["jobs"] += 1
            sd["jobs_completed"] += 1
        elif kind == "wage":
            job = events[e["source_job_event_id"]]
            check(job["event_type"] == "job_completed" and job["resident_id"] == rid and job["job_id"] == e["job_id"] and e["previous_event_id"] == job["event_id"] and e["credits_delta"] >= 0, "Wage/job reference")
            if p["mode"] == "weighted_cohort_demo":
                cycle = p["professions"][e["profession"]]["wage_cycle"]
                check(e["credits_delta"] == cycle[(job["job_sequence"]-1)%len(cycle)], "Detailed profession wage")
            sd["credits_earned"] += e["credits_delta"]
            s["earned"] += e["credits_delta"]
        elif kind == "pack_purchase":
            check(e["sku_id"] == p["purchase_sku"] and e["quantity"] > 0 and e["unit_price_credits"] == price and -e["credits_delta"] == price*e["quantity"], "Detailed purchase debit")
            check(e["balance_before"]//price == e["quantity"], "All affordable packs bought")
            if e["latest_wage_event_id"]:
                ref = events[e["latest_wage_event_id"]]
                check(ref["event_type"] == "wage" and ref["resident_id"] == rid, "Purchase wage reference")
            s["spent"] -= e["credits_delta"]
            sd["credits_spent"] -= e["credits_delta"]
            purchases[eid] = e["quantity"]
        elif kind == "pack_opening":
            purchase = events[e["source_purchase_event_id"]]
            check(e["credits_delta"] == 0 and e["pack_instance_id"] not in packs and purchase["resident_id"] == rid and purchase["event_type"] == "pack_purchase" and purchase["sku_id"] == e["sku_id"], "Unique opening/purchase reference")
            packs.add(e["pack_instance_id"])
            purchases[e["source_purchase_event_id"]] -= 1
            check(len(e["items"]) == {"empty":0,"one_item":1,"two_items":2}[e["outcome"]], "Opening item count")
            s["opened"] += 1
            sd["packs_opened"] += 1
            sample_outcomes[e["day"]-1][e["outcome"]] += 1
            for item in e["items"]:
                check(item["item_id"] in {x["item_id"] for x in sku["item_contents"]} and item["item_instance_id"] not in instances, "Catalog/unique item instance")
                instances.add(item["item_instance_id"])
        elif kind == "item_received":
            opening = events[e["source_opening_event_id"]]
            check(opening["resident_id"] == rid and {"item_id":e["item_id"],"item_instance_id":e["item_instance_id"]} in opening["items"], "Item/opening reference")
            opening_drops[e["item_instance_id"]] += 1
            permanent = item_table[e["item_id"]]["ownership"] == "permanent"
            check(e["credits_delta"] == 0 and e["inventory_quantity_before"] == s["inventory"][e["item_id"]] and e["consumed_immediately"] == (not permanent), "Item inventory/consumption")
            if permanent:
                s["inventory"][e["item_id"]] += 1
            check(e["inventory_quantity_after"] == s["inventory"][e["item_id"]], "Duplicate inventory quantity")
            sample_items[e["day"]-1][e["item_id"]] += 1
        elif kind == "home_change":
            item = events[e["source_item_event_id"]]
            check(e["credits_delta"] == 0 and item["resident_id"] == rid and item["item_id"] == e["item_id"] and item["source_opening_event_id"] == e["source_opening_event_id"], "Home item reference")
            check(e["item_id"] not in s["home"] and item_table[e["item_id"]]["ownership"] == "permanent" and s["inventory"][e["item_id"]] == 1, "First permanent copy placement")
            check(e["home_version_before"] == s["version"] and e["home_version_after"] == s["version"]+1, "Home version")
            s["version"] += 1
            s["home"].add(e["item_id"])
            check(sorted(s["home"]) == e["owned_home_item_ids"], "Home ownership")
        else:
            check(False, "Unexpected event type")
        s["balance"],s["seq"],s["last"],s["time"] = e["balance_after"],e["event_sequence"],eid,when
        events[eid] = e
    check(all(v == 0 for v in purchases.values()), "All purchased packs opened exactly once")
    check(set(opening_drops) == instances and all(v == 1 for v in opening_drops.values()), "Each declared item received exactly once")
    day_seen = set()
    last_balance = {r["resident_id"]:p["starting_credits"] for r in residents}
    day_order = Counter()
    for row in jsonl(root/"sample_daily.jsonl"):
        common(row)
        key = (row["resident_id"],row["day"])
        check(row["_id"] == f"{sim}:{row['resident_id']}:day:{row['day']:03d}", "Stable unique sample day ID")
        check(key not in day_seen and row["day"] == day_order[row["resident_id"]]+1, "Unique ordered sample days")
        day_seen.add(key)
        day_order[row["resident_id"]] += 1
        sd = sample_days[key]
        for k in ("jobs_completed","credits_earned","credits_spent","packs_opened"):
            check(row[k] == sd[k], "Sample day events vs ledger: "+k)
        check(row["opening_balance"] == last_balance[row["resident_id"]] and row["closing_balance"] == row["opening_balance"]+row["credits_earned"]-row["credits_spent"], "Sample daily balance continuity")
        last_balance[row["resident_id"]] = row["closing_balance"]
        if selected_paths:
            path_day = selected_paths[row["trajectory_id"]]["path"][row["day"]-1]
            check(path_day[:2] == [row["jobs_completed"],row["credits_earned"]], "Detailed sample linked to aggregate trajectory")
    check(len(day_seen) == sample_n*dcount, "Complete sample day count")
    for r in residents:
        common(r)
        s,w = states[r["resident_id"]],wallets[r["trajectory_id"]]
        check(r["ending_balance"] == s["balance"] == w["ending_balance"] and r["last_event_id"] == s["last"], "Resident final balance and event")
        for key, state_key in (("credits_earned","earned"),("credits_spent","spent"),("jobs_completed","jobs"),("packs_opened","opened")):
            check(r[key] == s[state_key] == w[key], "Resident final totals: "+key)
        check(r["home_version"] == s["version"] and r["owned_home_item_ids"] == sorted(s["home"]) and r["inventory_quantities"] == dict(s["inventory"]), "Resident final inventory/home")
        check(w["rank_start"] <= r["earnings_order_rank"] <= w["rank_end"], "Sample rank link")
    for i in range(dcount):
        check(all(v <= daily[i]["pack_outcomes"][k] for k,v in sample_outcomes[i].items()), "Included sample outcome counts")
        check(all(v <= daily[i]["item_drops_by_id"][k] for k,v in sample_items[i].items()), "Included sample item counts")
    checks.append("Every sample event replayed: stable IDs, strict UTC times, wages, purchases, empty openings, item references, duplicates and homes; all sample days and final residents reconcile")
    for row in csvrows(root/"daily_summaries.csv"):
        j = daily[int(row["day"])-1]
        for k,v in row.items():
            if k in j and not isinstance(j[k], (dict,list)):
                check(v == ("true" if j[k] is True else str(j[k])), "Daily CSV parity: "+k)
        check(int(row["empty_openings"]) == j["pack_outcomes"]["empty"] and int(row["item_drops"]) == sum(j["item_drops_by_id"].values()), "CSV loot parity")
    for row in csvrows(root/"pack_outcomes.csv"):
        j = daily[int(row["day"])-1]
        multiplier = int(row["sku_id"] == p["purchase_sku"])
        check(row["synthetic"] == "true" and row["simulation_id"] == sim, "Pack CSV provenance")
        check(int(row["packs_opened"]) == int(row["packs_bought"]) == j["packs_opened"]*multiplier, "Pack CSV counts")
        for k in ("empty","one_item","two_items"):
            check(int(row[k]) == j["pack_outcomes"][k]*multiplier, "Pack CSV outcomes")
    for row in csvrows(root/"item_drops.csv"):
        check(row["synthetic"] == "true" and row["simulation_id"] == sim and int(row["item_drops"]) == daily[int(row["day"])-1]["item_drops_by_id"][row["item_id"]], "Item CSV parity")
    checks.append("JSON/JSONL/CSV cross-format parity")
    return {"synthetic":True,"simulation_id":sim,"status":"PASS" if not skipped else "PASS_WITH_UNVERIFIED_SOURCE_REPLAY","validation_seconds":round(time.perf_counter()-started,6),"generator_sha256":m["generator_sha256"],"validator_sha256":m["validator_sha256"],"daily_summaries":dcount,"sample_residents":sample_n,"sample_events":len(events),"sample_days":len(day_seen),"representative_trajectories":wallet_count,"represented_resident_days":n*dcount,"checks":checks,"skipped_or_unverified":skipped,"does_not_prove":"Empirical realism, actual model runs, unmaterialized individual loot inventories, or performance of a 250m-row external input not supplied"}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dataset", type=Path)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    try:
        result = validate(args.dataset)
    except (ValueError, KeyError, sqlite3.IntegrityError) as error:
        result = {"status":"FAIL","error":str(error)}
    if args.report:
        args.report.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result["status"].startswith("PASS") else 1)
