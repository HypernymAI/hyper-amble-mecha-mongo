ARCHIVAL NOTE: This document describes the full hackathon package. This public repository is a source excerpt and does not run as a standalone application. Refer to the root README for the hosted demo and omitted dependencies.

AMBLE PRESENTS — SYNTHETIC EARNINGS, SPENDING AND PACK OPENINGS
Simulation/generator version 2.0.0. All data is synthetic.

INTENDED USE
The teammate's earnings are the intended authoritative input. They have not
arrived. target-demo/ is a separately identified, reproducible cohort demo,
not 250 million real agent/model runs or a claim that the supplied-input
pipeline ran at that size. EARNINGS_HANDOFF.txt is the copyable request to him.
INTEGRATION_NOTES.txt describes safe joins and overlapping data views.

RUN (from this folder; Python 3.11+ on macOS/Linux, NumPy 2.3.5)
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt

Fast default preview: 50,000 residents, 1,000 cohorts, 50 days, 200 details.
  .venv/bin/python generate.py --out my-preview
  .venv/bin/python validate.py my-preview --report my-preview/validation_report.json

Target demo: 5,000,000 residents, 20,000 cohorts, 50 days, 200 details.
  .venv/bin/python generate.py --preset target --out my-target
  .venv/bin/python validate.py my-target --report my-target/validation_report.json

Use his earnings when received (sorted CSV/CSV.gz, see the handoff contract):
  .venv/bin/python generate.py --preset target --population 5000000 \
    --earnings /path/to/earnings.csv.gz --source-simulation-id HIS_SOURCE_ID \
    --out supplied-income
  .venv/bin/python validate.py supplied-income \
    --report supplied-income/validation_report.json

Bounded reproducibility, external fixture and rejection checks:
  .venv/bin/python check_pipeline.py --report pipeline_checks-new.json

An existing nonempty output directory is rejected. Use a fresh directory
after errors or for another run. No network, credentials, model calls,
MongoDB connection or app startup occurs inside these scripts. Installing
dependencies is separate. The delivered run used bundled Python 3.12.14
and NumPy 2.3.5, not the host's default Python 3.9.

EDITABLE ASSUMPTIONS
parameters.json is the economy configuration; catalog.json defines products,
possible item contents, item ownership and probabilities. Use --parameters,
--catalog, --seed or --purchase-sku to select alternatives.

- Everyone starts with 12 credits. No debt, taxes, interest, death, migration,
  resale, refunds or peer transfers. Wages issue credits; purchases transfer
  credits from households to an aggregate shop account. Items have no cash
  valuation. Starting grants are issued once and are not earnings.
- Demo profession shares are equal in expectation. Healthcare, finance and
  construction are fictional inventory/budget/tile-count jobs, not advice.
  Each profession follows the same 14,16,18,12 wage cycle by cumulative job
  sequence. No task/model is actually executed.
- Demo activity profiles: occasional 20% share, 65% active probability,
  10% chance of a second job when active; regular 55%/85%/25%; frequent
  25%/97%/50%. Inactive days have zero jobs; active days have one or two.
  These probabilities are assumptions, not inferred resident behavior.
- Supplied-input mode uses his daily earnings and jobs, not the demo wage
  rule. Optional job_wages preserves individual wages. Without it, detailed
  jobs receive an explicitly labeled even allocation of each daily total.
- One common pack SKU is used by everyone. Default daily-breakfast costs 8.
  After daily wages, purchase probability is 1 when affordable. Buy all
  affordable packs and open them immediately. Unspent credits carry forward.
  Thus total packs = floor((12 + cumulative earnings) / price). Higher total
  earnings guarantee at least as many packs, with ties. The ranked wallet
  export orders cumulative earnings, not liquid credits left after spending.
- Daily alternative packs cost 16 (plants) and 24 (books). Convenience lamp,
  chair, rug and sofa cost 18,32,44,65 as direct permanent products. Their
  catalog is available for integration; this default does not auto-buy them.
- Every pack is a consumable container: 90% empty, 9% one item, 1% two items.
  For each nonempty slot, draw independently with replacement from the
  selected SKU's weighted item table. Breakfast weights are pastry 40,
  mug 20, plant 15, books 10, lamp 8, chair 4, rug 2, sofa 1. A two-slot
  pack can contain a duplicate. These are possible contents, not guaranteed
  contents. Purchases, openings, and items are distinct records.
- A first permanent copy furnishes the sampled home. Duplicate permanent
  copies remain in inventory. Pastries are consumed immediately. No item
  drops restore credits; more packs mean more expected drops, not guaranteed
  individual item-count order. All catalog products are unlocked. The current
  generator rejects non-null unlock criteria instead of silently ignoring them.
- 500 million openings is a benchmark, not a forced count or cap. Report
  actual paid openings and excess/shortfall. At 8 credits each, the benchmark
  costs 4 billion credits; 60 million comes from starting wallets. Individual
  wallet remainders also reduce feasible purchasing capacity.

SANDBOX PROVENANCE AND DELIBERATE CHANGE
Only sandbox/state.py was read for
sandbox context. Its SHA-256 is recorded in parameters.json. It supplies the
12-credit grant, wage cycle, roles and original seven SKU names/prices.
That sandbox permanently owns ALL seven products and prohibits repeats.
Nick's clarified request changes Daily packs into repeatable, mostly empty
loot containers. Contents, opening probabilities and activity/spending
policies are new simulation assumptions. The sandbox file was not imported,
executed or modified; the Amble app was not started or changed.

METHOD AND LIMITS
The target demo independently generates 20,000 income/activity trajectories
and assigns each a population weight of 250. It updates 1,000,000 cohort-days,
representing 250,000,000 resident-days. This is a sampling-based weighted
projection, not five million independent life histories. Arbitrary populations
use integer weights differing by at most one; weights always sum exactly.
Accounting is exact within the projection. No empirical calibration or
confidence intervals are claimed.

Choose 200 distinct trajectories uniformly and one resident uniformly within
each selected trajectory. Their IDs, balances, event chains, inventories and
homes are individual. Their income matches the linked trajectory. They are
included in population totals, not additional residents. Unequal cohort sizes
make this an illustrative sample, not an unbiased population estimator.

Sample openings are generated individually. Subtract their counts from each
day's total openings, then draw the remaining outcome counts with NumPy
multinomial and draw item counts across the resulting slots. Add the sample
counts back exactly once. This gives seeded stochastic counts conditional on
funded openings without creating 500 million events. Aggregate item counts
are drops, not unique owners. Unsampled resident inventories/home states and
individual bulk opening IDs are intentionally not materialized.

Supplied-input mode streams one resident's 50 days at a time with weight 1.
It hashes the input file, then reads it, and uses a local temporary SQLite
sort for ranked wallets. Full daily input trajectories are omitted by default
to conserve storage; --retain-trajectories retains a compressed audit copy.
Without that copy, the validator explicitly reports that independent full
source replay was not performed. The generator still checks every row's
ordering, completeness, role, integer values, synthetic flag and wage sums.
External processing time scales with input rows; full-scale time/storage
has NOT been benchmarked. No claim is made that the cohort runtime applies.

FILES IN EACH DATASET
daily_summaries.json/.jsonl/.csv: 50 daily records, alternative encodings.
  JSON includes profession rollups, exact weighted liquid-wealth histograms,
  pack counts by SKU, outcome/item counts and cumulative economy accounts.
pack_outcomes.csv: day x pack SKU counts, including unused SKUs with zeros.
item_drops.csv: day x item counts, including duplicates and consumables.
ranked_wallets.csv.gz: one row per cohort in demo, per resident in source mode;
  descending earnings, population_weight and weighted rank_start/rank_end.
trajectory_audit.jsonl.gz: demo cohort paths; external only when requested.
  path entries are [jobs_completed, credits_earned, optional_job_wages].
sample_residents.jsonl: 200 final individual states and linked ranks.
sample_daily.jsonl: 10,000 individual daily ledgers, including zero-job days.
sample_events.jsonl.gz: init -> job -> wage -> pack purchase -> opening ->
  item receipt -> first-copy home placement; empty openings remain explicit.
  Timestamps are assigned synthetic UTC times, not execution telemetry.
catalog.json/.jsonl and parameters.json: effective catalog/config snapshots.
economy_totals.json: whole-scenario financial and opening totals.
manifest.json: IDs, seed, version, code hashes, data hashes/counts, method.
run_metrics.json: measured generation wall time, peak RSS and artifact sizes.
validation_report.json: actual independent checks and unverified scope.

REPRODUCIBILITY AND IMPORT
Seed 20261011; NumPy PCG64 uses separately derived random streams. Simulation
ID fingerprints parameters, catalog, generator hash, source hash and NumPy
version. Event IDs and gzip headers are deterministic. Pin the versions for
byte reproduction. Timing metrics and validation elapsed times are sidecars
and are not expected to reproduce. The manifest hashes deterministic data;
its own hash and delivery sidecars are covered by the package SHA256SUMS.txt.

Every data row is synthetic and shares world_id/simulation_id. Use supplied
resident IDs without renaming. Preserve source_simulation_id and input hash
as provenance; the spending scenario has its own simulation_id. Do not append
the demo to his source as if both were additional earnings. Do not add sample,
cohort and summary totals together. Compressed JSONL can be streamed with
gzip -dc. CSV is UTF-8 with a single header and integer credits. No Atlas
upload has been performed. See INTEGRATION_NOTES.txt for collection keys.

VERIFIED DELIVERED RUN
target-demo: 5,000,000 residents; exactly 50 days; 250,000,000 resident-days;
20,000 weighted trajectories; 200 detail residents; 10,000 sample days;
54,805 detailed events. 516,695,000 funded openings; 465,030,282 empty;
56,835,483 item drops. 16,695,000 openings above the 500m benchmark.
Initial credits 60,000,000 + earned 4,088,671,000 = final household credits
15,111,000 + shop credits 4,133,560,000.
Generation 3.224487 seconds; peak generator RSS 50,937,856 bytes.
Data plus manifest before timing/report sidecars: 9,462,345 bytes (9.46 MB).
Independent target validation: PASS in 2.725442 seconds. Preview also PASS.
pipeline_checks.json records same-seed byte reproduction, an exact 10,000-row
external fixture, alternate pack SKU, and seven invalid-input rejection cases
plus zero population. Those bounded checks passed in 9.02626 seconds.
His full 250-million-row earnings file remains pending; these are demo results.
