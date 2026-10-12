"""Bounded synthetic economy provenance, accounting and delivery isolation."""
from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sandbox import economy


class TestSwarmEconomy(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.package = Path(self.temp.name) / "economy"
        shutil.copytree(economy.PACKAGE, self.package)

    def tearDown(self):
        self.temp.cleanup()

    def rewrite(self, name, transform):
        path = self.package / "demo" / name
        value = ([json.loads(line) for line in path.read_text().splitlines()]
                 if name.endswith(".jsonl") else json.loads(path.read_text()))
        transform(value)
        raw = (("\n".join(json.dumps(row) for row in value) + "\n") if name.endswith(".jsonl")
               else json.dumps(value)).encode()
        path.write_bytes(raw)
        manifest_path = path.parent / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"][name].update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        if name.endswith(".jsonl"):
            manifest["files"][name]["records"] = len(value)
        manifest_path.write_text(json.dumps(manifest))

    def assert_unavailable(self):
        payload = economy.load_demo(self.package)
        self.assertFalse(payload["available"])
        self.assertTrue(payload["synthetic"])
        self.assertNotIn("summary", payload)
        self.assertNotIn("days", payload)
        self.assertEqual(list(economy.atlas_documents(payload)), [])

    def test_bundled_counts_finances_and_provenance(self):
        payload = economy.load_demo(self.package)
        self.assertTrue(payload["available"])
        self.assertEqual(len(payload["days"]), 50)
        self.assertEqual(len(payload["residents"]), 200)
        self.assertEqual(payload["summary"]["population"], 5000000)
        self.assertEqual(payload["summary"]["packs_opened"], 516695000)
        provenance = payload["provenance"]
        self.assertTrue(provenance["bundle_verified"])
        self.assertEqual(provenance["income_mode"], "weighted_cohort_demo")
        self.assertEqual(provenance["representative_trajectories"], 20000)
        self.assertTrue(provenance["no_model_runs"])
        self.assertTrue(provenance["sample_included_not_additive"])
        self.assertIsNone(provenance["source_earnings_sha256"])
        self.assertIn("omitted histories were not revalidated", provenance["validation_scope"])
        json.dumps(payload, allow_nan=False)

    def test_atlas_documents_are_separate_stable_and_nonmutating(self):
        payload = economy.load_demo(self.package)
        before = copy.deepcopy(payload)
        docs = list(economy.atlas_documents(payload))
        self.assertEqual(len(docs), 251)
        self.assertEqual({collection for collection, row in docs},
                         {"simulation_runs", "simulation_daily_summaries", "simulation_residents"})
        ids = [row["_id"] for _, row in docs]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(value.startswith("simulation:" + payload["simulation_id"] + ":") for value in ids))
        self.assertTrue(all(row["synthetic"] is True for _, row in docs))
        self.assertEqual(ids, [row["_id"] for _, row in economy.atlas_documents(payload)])
        docs[0][1]["summary"]["credits_earned"] = 0
        self.assertEqual(payload, before)

    def test_hash_corruption_is_unavailable_not_zero(self):
        path = self.package / "demo" / "daily_summaries.jsonl"
        path.write_bytes(path.read_bytes() + b"\n")
        self.assert_unavailable()

    def test_invalid_manifest_shape_is_safely_unavailable(self):
        (self.package / "demo" / "manifest.json").write_text("[]")
        self.assert_unavailable()

    def test_wrong_day_count_rejected_even_with_matching_hash(self):
        self.rewrite("daily_summaries.jsonl", lambda rows: rows.pop())
        self.assert_unavailable()

    def test_duplicate_resident_rejected_even_with_matching_hash(self):
        self.rewrite("sample_residents.jsonl", lambda rows: rows.__setitem__(1, rows[0]))
        self.assert_unavailable()

    def test_non_synthetic_or_cross_scenario_data_rejected(self):
        self.rewrite("sample_residents.jsonl", lambda rows: rows[0].update(synthetic=False))
        self.assert_unavailable()

    def test_cross_world_data_rejected(self):
        self.rewrite("daily_summaries.jsonl", lambda rows: rows[0].update(world_id="lived-world"))
        self.assert_unavailable()

    def test_accounting_error_rejected_even_with_matching_hash(self):
        self.rewrite("daily_summaries.jsonl", lambda rows: rows[0].update(credits_earned=0))
        self.assert_unavailable()

    def test_nonfinite_number_rejected_even_with_matching_hash(self):
        self.rewrite("daily_summaries.jsonl", lambda rows: rows[0]["wealth"].update(mean=float("nan")))
        self.assert_unavailable()

    def test_source_code_hash_is_part_of_provenance(self):
        path = self.package / "generate.py"
        path.write_bytes(path.read_bytes() + b"\n")
        self.assert_unavailable()

    def test_delivery_rejects_non_synthetic_payload(self):
        payload = economy.load_demo(self.package)
        payload["synthetic"] = False
        with self.assertRaises(ValueError):
            list(economy.atlas_documents(payload))

    def test_stdlib_loader_never_imports_lived_state_or_mutates_files(self):
        source = Path(economy.__file__).read_text()
        imports = {node.module.split(".")[0] for node in ast.walk(ast.parse(source))
                   if isinstance(node, ast.ImportFrom)}
        imports.update(alias.name.split(".")[0] for node in ast.walk(ast.parse(source))
                       if isinstance(node, ast.Import) for alias in node.names)
        self.assertTrue(imports.issubset({"__future__", "copy", "hashlib", "json", "math", "pathlib"}))
        def contents():
            return {str(path.relative_to(self.package)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in self.package.rglob("*") if path.is_file()}
        before = contents()
        list(economy.atlas_documents(economy.load_demo(self.package)))
        self.assertEqual(contents(), before)


if __name__ == "__main__":
    unittest.main()
