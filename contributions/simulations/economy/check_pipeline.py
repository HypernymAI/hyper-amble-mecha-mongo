#!/usr/bin/env python3
"""Bounded local checks of reproducibility, external earnings, and input rejection."""
import argparse
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(report):
    start = time.perf_counter()
    results = []
    def command(argv, expected=0):
        r = subprocess.run([sys.executable, *map(str, argv)], capture_output=True, text=True)
        if (r.returncode == 0) != (expected == 0):
            raise RuntimeError(f"Unexpected exit {r.returncode}: {argv}\n{r.stdout}\n{r.stderr}")
        return r
    def write_csv(path, rows):
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["resident_id","day","profession","jobs_completed","credits_earned","synthetic","job_wages"])
            w.writeheader()
            w.writerows(rows)
    with tempfile.TemporaryDirectory(prefix="amble-pipeline-") as tmp_name:
        tmp = Path(tmp_name)
        # Unequal weights exercise all population-remainder and sample member paths.
        for name in ("repeat-a", "repeat-b"):
            command([HERE/"generate.py", "--population", "1003", "--cohorts", "201", "--out", tmp/name])
            command([HERE/"validate.py", tmp/name])
        a = json.loads((tmp/"repeat-a"/"manifest.json").read_text())
        b = json.loads((tmp/"repeat-b"/"manifest.json").read_text())
        if a != b or any(sha(tmp/"repeat-a"/name) != sha(tmp/"repeat-b"/name) for name in a["files"]):
            raise RuntimeError("Deterministic dataset reproduction failed")
        results.append({"check":"Two same-seed 1,003-resident / 201-cohort / 50-day runs; unequal integer weights; all data and manifest byte-identical", "status":"PASS"})
        rows = []
        roles = ("healthcare", "finance", "construction")
        for i in range(200):
            for day in range(1,51):
                jobs = 0 if i == 0 else (i+day)%3
                wages = [7+i%31+j+day%3 for j in range(jobs)]
                rows.append({"resident_id":f"amble-{i+1:09d}","day":day,"profession":roles[i%3],"jobs_completed":jobs,"credits_earned":sum(wages),"synthetic":"true","job_wages":json.dumps(wages) if i%2 == 0 else ""})
        source = tmp/"earnings.csv"
        write_csv(source, rows)
        command([HERE/"generate.py", "--earnings", source, "--source-simulation-id", "fixture-only", "--population", "200", "--retain-trajectories", "--out", tmp/"external"])
        result = command([HERE/"validate.py", tmp/"external"])
        external = json.loads((tmp/"external"/"economy_totals.json").read_text())
        expected_earned = sum(r["credits_earned"] for r in rows)
        expected_packs = sum((12+sum(r["credits_earned"] for r in rows if r["resident_id"] == f"amble-{i+1:09d}"))//8 for i in range(200))
        if external["credits_earned"] != expected_earned or external["packs_opened"] != expected_packs:
            raise RuntimeError("External source conservation independent check failed")
        results.append({"check":"10,000-row external CSV fixture, 200 residents, 50 days, zero-income resident, mixed explicit and inferred per-job wages, retained-path full validator", "status":"PASS", "credits_earned":expected_earned,"funded_pack_openings":expected_packs})
        # Production storage setting omits full supplied trajectories; surface its verification limit.
        command([HERE/"generate.py", "--earnings", source, "--population", "200", "--out", tmp/"external-compact"])
        compact = json.loads(command([HERE/"validate.py", tmp/"external-compact"]).stdout)
        if compact["status"] != "PASS_WITH_UNVERIFIED_SOURCE_REPLAY" or not compact["skipped_or_unverified"]:
            raise RuntimeError("External validation scope not surfaced")
        results.append({"check":"External compact mode reports omitted full source replay explicitly", "status":"PASS"})
        mutations = {
            "negative_earnings": [{**rows[0],"credits_earned":-1},*rows[1:]],
            "duplicate_day": [rows[0],rows[0],*rows[1:]],
            "missing_day": rows[1:],
            "profession_change": [rows[0],{**rows[1],"profession":"finance"},*rows[2:]],
            "non_synthetic": [{**rows[0],"synthetic":"false"},*rows[1:]],
            "bad_job_wages": [{**rows[0],"job_wages":"[999]"},*rows[1:]],
            "resident_count_mismatch": rows[:-50]
        }
        for name, changed in mutations.items():
            path = tmp/(name+".csv")
            write_csv(path, changed)
            result = command([HERE/"generate.py","--earnings",path,"--population","200","--out",tmp/name], expected=1)
            results.append({"check":"Reject "+name,"status":"PASS","error":result.stderr.strip().splitlines()[-1]})
        # Covers catalog edits while retaining the purchasing-order proof.
        command([HERE/"generate.py", "--purchase-sku", "daily-books", "--population", "200", "--cohorts", "200", "--out", tmp/"books"])
        command([HERE/"validate.py", tmp/"books"])
        results.append({"check":"24-credit Daily Reading pack and its alternate item table", "status":"PASS"})
        command([HERE/"generate.py", "--population", "0", "--out", tmp/"zero"], expected=1)
        results.append({"check":"Reject zero population", "status":"PASS"})
    result = {"synthetic":True,"status":"PASS","generator_sha256":sha(HERE/"generate.py"),"validator_sha256":sha(HERE/"validate.py"),"check_script_sha256":sha(Path(__file__)),"seconds":round(time.perf_counter()-start,6),"checks":results,"unverified":["250,000,000-row teammate earnings file is not available; its full import throughput, disk needs and results have not been measured", "Actual empirical realism and real model/agent behavior"]}
    if report:
        report.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report",type=Path)
    run(ap.parse_args().report)
