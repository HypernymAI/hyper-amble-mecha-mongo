ARCHIVAL NOTE: This document describes the full hackathon package. This public repository is a source excerpt and does not run as a standalone application. Refer to the root README for the hosted demo and omitted dependencies.

# Optional Agent Engine memory

Chris's 11 October handoff adds `core/agent_engine_memory.py` and hooks in the
existing Atlas record/recall path. The source is integrated; **no Agent Engine
service is running or configured on the demonstration host**. The recorded
demo and verified database evidence use direct Atlas, Voyage, and the native
judge/dream loop. This addition does not change those claims.

The adapter mirrors successful native Atlas turn writes and appends managed
context to the existing memory block, marked as data rather than instructions.
It binds the existing person/resident scope as `user_id`, with agent `amble`
and session `presents`. Native Atlas must also be configured: this is an
additional memory source, not a replacement for the native database.

## Enable after provisioning a service

Use a project venv created with **Python 3.11 or newer**:

```sh
venv/bin/python3 -m pip install -r requirements-agent-engine.txt
```

Configure one of the SDK-supported connection modes in this clone's ignored
`.env`, then restart the desired Presents launcher:

- Local: `AGENTIC_MEMORY_BASE_URL` pointing to an already-running Agent Engine
  orchestration endpoint. A URL alone does not launch the required services.
- Hosted: `AGENTIC_MEMORY_SERVICE_ACCOUNT_TOKEN` and
  `AGENTIC_MEMORY_PROJECT_ID` for an already-provisioned memory project.

Keep credentials out of Git. Both launchers inherit these allowlisted variables.
The optional package is pinned to `agent-engine-sdk-memory==0.11.8`; it requires
Python 3.11+ and is deliberately separate from the base Intel handoff dependencies.

No configuration or missing SDK means a no-op. Three consecutive service errors
disable the adapter until restart. Errors log their type only. SDK network calls
are synchronous; SDK 0.11.8 uses 30-second HTTP timeouts and up to three attempts,
so an unreachable service can delay a call substantially. Live latency, service
authorization, extraction, and semantic/episodic recall remain unverified.
New turns may not immediately appear in consolidated managed memory.

The local regression check uses a fake SDK to verify scope binding, optional
disable behavior, failure handling, and prompt integration. It does not prove a
live service connection. Existing Atlas adapter and surface checks also pass.

Official references: [Python memory SDK](https://www.mongodb.com/docs/agentengine/sdk/python/packages/agent-engine-sdk-memory/)
and [memory service setup](https://www.mongodb.com/docs/agentengine/add-features/memory-only/).

The original contributor ZIP is retained locally under ignored `data/handoffs/`.
Its SHA256 is `a70d1e32c3592abfe7d2b89bb0a015f733d8055645e839ac8ce4db72953f25d4`.
Only the new adapter, Atlas hooks, and launcher allowlist were merged; older UI,
README, and ignore files were not allowed to overwrite the current town.
