ARCHIVAL NOTE: This document describes the full hackathon package. This public repository is a source excerpt and does not run as a standalone application. Refer to the root README for the hosted demo and omitted dependencies.

SYNTHETIC ECONOMY PACKAGE — BOUNDED REPOSITORY INTEGRATION

The generator, validator, pipeline checks, configuration, catalog and original
handoff documentation were copied verbatim from the delivered version 2.0.0.
Original package:
<simulation-output-directory>

demo/ contains only the original target-demo's 50 daily summary rows, 200 final
sample resident states, totals, catalog, parameters, manifest and recorded
validation/timing reports. The original manifest is unchanged and therefore
also lists omitted files. Its PASS report describes the full original dataset;
it does not claim the omitted files were revalidated by this integration.
sandbox/economy.py verifies bundled data hashes, source code hashes, record
counts, scenario identity and accounting before exposing the bounded payload.

The scenario is a synthetic weighted cohort projection: 20,000 trajectories
represent five million residents across 50 days. The 200 illustrative sample
residents are included in those totals. They are not an additional population.
No real model runs or lived swarm earnings are represented. The separate
teammate-provided earnings export remains pending.

OPTIONAL ORIGINAL ASSETS (not copied into this repository)
target-demo/sample_daily.jsonl: 10,000 individual sample days, 6,037,615 bytes.
target-demo/sample_events.jsonl.gz: 54,805 sample events, 1,779,669 bytes.
target-demo/ranked_wallets.csv.gz: 20,000 weighted ranks, 187,519 bytes.
target-demo/trajectory_audit.jsonl.gz: 20,000 trajectories, 917,970 bytes.
Hashes and all remaining original file sizes are retained in demo/manifest.json.
Do not run the original full-dataset validator against this intentionally
partial demo directory. Use the original full target-demo or generate a fresh
complete dataset and validate that instead. Do not invent missing event rows.

RUN A NEW COMPLETE DATASET (Python 3.11+; isolated environment)
  python3.11 -m venv .simulation-venv
  .simulation-venv/bin/python -m pip install -r requirements-simulation.txt
  .simulation-venv/bin/python generate.py --out /tmp/amble-economy-new-preview
  .simulation-venv/bin/python validate.py /tmp/amble-economy-new-preview

For supplied sorted CSV/CSV.gz earnings, use generate.py --earnings PATH
--source-simulation-id SOURCE_ID --population COUNT --sample-size 200 --out DIR.
See EARNINGS_HANDOFF.txt for the full schema and completeness requirements.
A 200-resident sample requires --population 200, not the target preset's
five-million-resident default. No full-scale external import has been run.

UI AND ATLAS BOUNDARY
Runtime loading is Python 3.9-compatible and standard-library-only. The UI must
label this a synthetic simulation and rank residents by cumulative earnings,
not their leftover cash. Scenario outputs use simulation_runs,
simulation_daily_summaries and simulation_residents. They never update lived
resident_state, world_state, balances, conversation turns or memory embeddings.
Each Atlas document keeps synthetic:true, world_id, simulation_id, record grain
and provenance. Summary and sample values describe overlapping activity and
must not be added together. The module prepares documents; it does not upload.
