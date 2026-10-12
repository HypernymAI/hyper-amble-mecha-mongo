ARCHIVAL NOTE: This document describes the full hackathon package. This public repository is a source excerpt and does not run as a standalone application. Refer to the root README for the hosted demo and omitted dependencies.

Synthetic resident lives, grounded in the economy target-demo.

resident_days.jsonl.gz contains 200 existing immutable residents × 50 days.
Every record includes morning and night feelings, workplace dialogue, a synthetic
memory note, exact pack outcomes/instance IDs, home inventory, wallet arithmetic,
and links to the original daily record and event IDs. Feelings and dialogue are
procedural fiction, never actual conversations or lived memory. No model calls,
Atlas writes, or runtime Amble memory ingestion occur here.

Use reader.get_resident_day(resident_id, day) for one day, or None if missing.
reader.corpus_status() reads bounded ignored progress, falling back to the bundled
measured fixture metadata. The fixture is self-contained; original source paths
are needed only to regenerate it. A home inventory excludes immediately consumed
food, using exact item_received inventory_quantity_after ledger values.

Run from the amble_mongo repository:
venv/bin/python3 simulations/resident_life/test_resident_life.py

The original 200-resident fixture narrative fields contain 1,867,160 tiktoken 0.14.0 cl100k_base tokens.
The original fixture alone does not achieve the 1,000,000,000-token target.
See SCALE_README.md for the independently generated disjoint scale scenario
and corpus_status() for current combined measured progress. Repeated reflection stress shards
were stopped and retained only in ignored package data, with their own rejected
stress manifest; they are excluded from this useful corpus count. Generating more
original-demo resident-days requires additional exact source ledger histories. The
generator refuses to pad the target with repeated paragraphs or invented events.

To regenerate the exact bounded fixture, supply the original source directory:
venv/bin/python3 simulations/resident_life/generate.py --source /path/to/target-demo

scale.py is the only expansion generator; see SCALE_README.md.
