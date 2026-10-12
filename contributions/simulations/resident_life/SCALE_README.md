ARCHIVAL NOTE: This document describes the full hackathon package. This public repository is a source excerpt and does not run as a standalone application. Refer to the root README for the hosted demo and omitted dependencies.

The scale archive is a separate synthetic town, not the original economy demo.

Simulation ID: synthetic-life-scale-v1-seed-20261011.
Resident IDs: life-scale-000000001 onward (disjoint from amble-*).
Each resident has 50 days and a linked Amble ID identical to that resident ID.
Procedural feelings, dialogue, and memories vary with deterministic resident/day
seeds, occupation tasks, visual details, neighbor questions, and actual pack
outcomes. They are generated fiction; no model run or real human record exists.

Ledger: each starts with 12 credits; completes 1–2 fictional jobs daily; each
job earns an integer 12–20 credits; buys floor(wallet/8) packs at 8 credits;
keeps the 0–7 credit remainder. Each pack has deterministic 1/7 one-item drop
probability, otherwise empty. Item catalog is item-plant, item-mug, item-lamp,
item-chair, item-books, item-rug, item-sofa, all durable home inventory here.
These parameters differ from the original demo and must not share its totals.
Every day stores wallet arithmetic, exact pack instance and item IDs, inventory,
morning/night feelings, work dialogue, and a memory. Stable deterministic IDs
allow deduplication. The compressed archive is local ignored data, never Atlas.

Run or resume, from the Amble repository:
TIKTOKEN_CACHE_DIR=/private/tmp/amble-token-cache venv/bin/python3 data/integrations/amble_mongo/simulations/resident_life/scale.py --output data/integrations/amble_mongo/data/synthetic-resident-life/scale

Completed gzip shards and atomic scale-progress.json report exact measured
cl100k_base narrative tokens, residents, days, bytes, SHA256, speed and estimated
time remaining. A resume starts after the last completed resident range.
A partial shard is overwritten on resume; it never counts toward progress.
Default target: 1 billion actual narrative tokens. Default limit: 110,000 people,
50 days each; compressed output cap: 2GB. Target remains partial until measured
completed shards reach it. Reader status adds the original 1,867,160 narrative
tokens, while retaining explicit per-scenario counts and simulation IDs.

The bounded first-shard verification independently retokenizes 50,000 rows,
checks its SHA256, and checks four boundary residents' wallet/inventory chains:
TIKTOKEN_CACHE_DIR=/private/tmp/amble-token-cache venv/bin/python3 data/integrations/amble_mongo/simulations/resident_life/test_scale.py

Completed result: 1,008,057,948 measured scale narrative tokens, 68,000 residents,
3,400,000 days, 68 shards, 738,676,748 compressed bytes. Combined with the original
fixture: 1,009,925,108 narrative tokens. Every day wallet/inventory and every shard
hash passed validate_scale_archive.py; first 50,000 rows were independently
retokenized. The remaining rows' generated token receipts were summed and
protected by shard SHA256 (not independently retokenized a second time).
scale-proof.json contains all completed shard hashes and validation metadata;
it does not contain the archive. No worker remains active after reaching target.
