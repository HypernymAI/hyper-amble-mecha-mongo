ARCHIVAL NOTE: This document describes the full hackathon package. This public repository is a source excerpt and does not run as a standalone application. Refer to the root README for the hosted demo and omitted dependencies.

# Presents sandbox swarm

The sandbox adds residents, work, shops, homes, and memory to the existing
**AMBLE PRESENTS** scene. Its browser host is rendered from this repository's
retained exhibit and original renderer, with sandbox controls overlaid. There is one shared
town; another person's browser or worker joins that same server.

## Primary host

Double-click **Start Swarm.command**, or run from this clone:

```sh
python3 scripts/swarm_run.py --bootstrap
# After the venv has been created:
venv/bin/python3 scripts/swarm_run.py --backend claude-cli --workers 2
```

`--bootstrap` creates this clone's `venv/` and installs
`requirements-presents.txt` there. It never installs into global Python or
invokes the other launcher. The launcher reads the existing
`presents-package.json`, validates the retained `portable` exhibit, and calls
the original `channel.presents.render` to produce
`data/swarm/presents/hypernym/presents/`. A fresh clone needs no copied site
export. All generated assets, configuration, logs, and town state stay beneath
ignored `data/swarm/`; the original tracked exhibit seeds remain intact.

Provider selection follows explicit `--backend` / `--model`, then saved
Swarm preferences, then the existing Presents environment / repository `.env`
defaults. `--backend codex` uses your own local Codex login; `--backend
claude-cli` uses your own local Claude login. OpenRouter uses your own key.
The existing allowlisted environment loader also supplies `MONGODB_URI` and
`VOYAGE_API_KEY`; saved town values take precedence in the server. Secrets are
never printed or included in join links. No account is bundled.

The server binds `0.0.0.0:3190` by default for shared LAN access. Use
`--host 127.0.0.1` for local-only access, `--port` to avoid an existing service,
or `--no-browser` to skip browser opening. The launcher does not stop other
servers. `--prepare-only` renders the exhibit and exits before installing
dependencies or opening any network/model/database connection, even when
`--bootstrap` is also passed.

The server writes `launch.json` in that directory with a local URL and a LAN
join URL. Open the local URL to reach the existing city. Swarm > Start begins
the host's two configured model workers; Pause prevents new leases while
current work may finish. One turn submits one job while leaving the town
paused afterward. Restarting the server starts paused. Keep the host process
running while visitors or external workers are connected.

Preparing this clone does not establish model access, a connection from
another computer, an internet tunnel, or successful Atlas synchronization.
Those remain separate checks.
The join token grants access to shared town controls and data. Copy the link
from Swarm > Setup and send it privately yourself; no delivery script sends
messages or publishes the town. A LAN URL requires a reachable LAN/VPN path.
Internet use requires a separately configured reachable endpoint, preferably
HTTPS; no tunnel is created by this package.

Setup changes provider and database credentials only from the host computer's
loopback address. Changing models requires pausing and letting current jobs
finish; database credentials can be corrected while residents work. Credentials
are saved in the dedicated runtime `config.json`, never returned in snapshots.
No runtime files belong in Git or in a worker delivery.

The original **Start Presents.command** still starts the native visitor and
Studio flow with its **Amble's mind** panel. **Start Swarm.command** starts
only the shared-town server, not that websocket backend. Its rendered intake
URL is empty so this separate launch does not imply an active native Mind
connection. Chris's original Atlas implementation remains the source for
native memory behavior; the resident adapter uses native recall and explicit
Dream actions in separate resident scopes. This adapter is not a second
implementation of the original Mind panel.

## Work and economy

Open **Jobs** beside Swarm to see the live queue by profession. The original
street now includes a clinic, ledger office, and community construction yard.
Clicking a workplace opens that profession on the same board.

The construction zone occupies the former corner-store footprint, retaining
`place_id: store` and the contributor worksite ID `arm-site`. The construction door opens the SO-101 lab at `#arm`, replaying two recorded
MuJoCo conveyor runs with camera detections and their money ledger. This browser
replays frames; it does not run physics or control hardware. Recorded lab dollars
are separate from town credits. Delivery and drone sites are out of scope.
Convenience purchases remain available from each live resident’s Home panel.

Six residents begin in three fictional professions. Healthcare counts clinic
supply packs, finance subtracts toy market expenses from toy sales, and
construction counts courtyard tiles. These are deterministic bookkeeping
puzzles, not real medical, financial, or engineering advice. Jobs publish
their task data and required answer shape. The server checks the calculation
before issuing a wage, and the same lease cannot earn twice.

Residents may spend fictional credits on Daily packs and Convenience home
furnishings. Purchases check balance and ownership atomically. Accepted work
and purchases produce server receipts; free-form model posts are unverified
chat. One open job per resident bounds the active queue. Expired or failed
leases return the job for retry without paying. Starting credits are 12;
new residents receive their own home, role, and queue slot.

**Simulation** reads the checked, compact economy bundle in
`simulations/economy/demo/`. It represents five million residents over 50 days
with weighted synthetic cohorts and 200 illustrative residents already included
in the totals. These are not live model runs or the external contributors'
earnings. Repeatable packs, empty openings, and item drops belong to this
separate scenario; the live seven-item catalog retains its existing behavior.
Source generation, an earnings CSV importer, and validation scripts are bundled
alongside it. Generation needs a separate Python 3.11+ environment with NumPy;
the running web server reads the bounded results with the standard library.

The host durably queues 251 synthetic records for Atlas: one `simulation_runs`
document, 50 `simulation_daily_summaries`, and 200 `simulation_residents`.
Every record retains `synthetic: true`, its simulation/world identifiers, and
provenance. Stable IDs make retries idempotent. These collections never update
live wallets, resident conversations, or learned memories. Pending contributor
site metadata is also visible in the shared `world_state` snapshot.

## Two local memory layers; Atlas status is explicit

`world.sqlite3` is the authority for shared residents, balances, home items,
leases, purchases, and activity. `memories.sqlite3` retains each resident's
conversation/import records and queues shared world snapshots and receipts
for optional MongoDB synchronization. Recall always filters to the selected
resident; assembled prior job prompts are excluded from subsequent prompts.
The town context includes a bounded neighbor roster and recent events.

Local semantic retrieval uses an already-cached
`sentence-transformers/all-MiniLM-L6-v2` model when its package and cache are
available. The sandbox does not download that model. Without it, lexical
recall remains available and is reported as lexical. Voyage embeddings are
optional and require their own local configuration and credential.

Atlas needs valid database credentials, reachable network/access settings,
and the `pymongo` dependency. While unavailable, writes stay in the local
queue. A configured URI alone does not prove synchronization. Setup health
reports connection, queued writes, embedding mode, and retrieval mode. Atlas
vector search additionally requires the configured vector index to exist;
without an index the implementation can retrieve resident documents and
rank locally. This delivery does not include or verify database credentials,
Atlas access, or remote vector search.

Host web/database dependencies are installed by the launcher from the same
`requirements-presents.txt` used by the original app. To install them manually:

```sh
venv/bin/pip install -r requirements-presents.txt
```

## Chris: browser, worker, or imported conversation

Chris can open the private join link in a browser without installing a worker.
The browser shows the same Presents city and can chat with a resident through
the primary host. To contribute model turns using Chris's own account, build
the standalone worker ZIP:

```sh
venv/bin/python3 scripts/package_swarm_worker.py
```

The default output is a content-addressed ZIP under
`data/deliveries/presents-swarm-2026-10-11/`. It contains only an explicit source
allowlist, launchers, instructions, an import example, and a SHA-256 manifest.
No owner login, API key, `.env`, database, transcript, browser asset, or town
token is copied. Nick supplies the join link separately. The ZIP includes
`Start Worker.command` for macOS and Terminal/WSL instructions. Native Windows
is not supported by the current Unix-oriented model transport.

The worker needs Python 3.11+ and a current Claude Code or Codex CLI, installed
and authenticated on Chris's computer. Account-backed worker paths require
no third-party Python packages. It claims jobs from `/api/lease`, asks its
local CLI to produce the answer, and submits to `/api/complete`; the primary
server owns validation, wages, memory, and purchases. It sends the task,
selected memories, and shared town context to Chris's chosen model provider.
It does not send CLI credentials to the primary host. Codex may stage its own
local authentication in a temporary local runtime; it is never put in the ZIP.

The same worker is available in a full checkout:

```sh
venv/bin/python3 scripts/swarm_worker.py --server http://HOST:3190 --backend claude-cli --name chris
```

That command prompts for the town token. The packaged launcher instead asks
for the complete join link in a hidden prompt. Use a distinct worker name per
computer/process. `--once` exits after one completed submission attempt, but
waits while the town is paused. Stopping one worker does not stop the host's
workers or the city. A printed connection line is not a successful job check;
an accepted completion receipt is.

For conversation import, choose a resident > Memory > Import sandbox
conversation. The file can be this JSON object or its `messages` array:

```json
{
  "messages": [
    {"role": "user", "text": "In this fictional town, I like reading corners."},
    {"role": "assistant", "text": "I will keep a reading corner in mind for home."}
  ]
}
```

Allowed roles are `user`, `assistant`, and `system`; limits are 100 messages,
18,000 characters per message, and 100,000 request bytes. Import only messages
intended for this sandbox. The selected resident receives imported memory;
imports do not create wages, purchases, accepted work, or changes to Amble's
personal memory. The API form adds `resident_id` alongside `messages` and
posts to `/api/import` with the town token in `X-Swarm-Token`.

## Verification boundaries

```sh
venv/bin/python3 scripts/swarm_run.py --prepare-only --no-browser
venv/bin/python3 tests/test_swarm_state.py
venv/bin/python3 tests/test_elsewhere_scene.py
venv/bin/python3 scripts/package_swarm_worker.py
```

The package builder checks Python syntax, exact archive scope, SHA-256
contents, ZIP integrity, and common credential patterns. In the extracted
worker folder, `python3 launch_worker.py --check` checks imports and CLI
presence without making an inference request. None of these checks proves
visual quality, login validity, remote inference, Atlas access, or a network
connection from Chris's computer.
