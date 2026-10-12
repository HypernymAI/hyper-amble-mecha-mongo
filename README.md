# Hyper Amble Mecha Mongo

## [Explore the full demo → mongodb.amble.channel](https://mongodb.amble.channel/hypernym/presents/#now)

**By Nick, Chris & Ted.**

Amble Presents is a town of agents that work, remember, earn credits, open packs and make a home. This hackathon brought together MongoDB Atlas memory, resident simulations and a mechanical-arm replay inside Presents.

**This repository does not run as a standalone application.** It contains selected new open-source contributions from the hackathon. The complete Amble application, hosted-demo build, recorded media and datasets are not included. Use the full demo above. More soon.

The hosted version includes the post-submission navigation and avatar polish. Its interactive town presents the published demo snapshot; visiting it does not start model workers or connect your browser directly to our Atlas database.

## Contributors

- **Nick** — Amble, Presents, town/swarm integration and the demo experience.
- **Chris** — Atlas/Voyage memory, reply evaluation and the optional Agent Engine memory adapter.
- **Ted** — the SO-101 mechanical-arm handoff and replay contribution.

## Open-source contributions

| Area | Source excerpt |
| --- | --- |
| Atlas memory and evaluation | [Memory adapter](contributions/core/atlas_memory.py), [reply judge](contributions/core/reply_judge.py), [Agent Engine adapter](contributions/core/agent_engine_memory.py) |
| Shared world and resident memory | [Sandbox modules](contributions/sandbox) |
| Swarm workers and integration | [Worker/server tools](contributions/scripts), [town UI](contributions/web/static/presents) |
| Synthetic lives and economy | [Simulation generators, readers and checks](contributions/simulations) |
| Mechanical-arm replay | [Application glue and notices](contributions/web/static/presents/arm-lab) |

The excerpt intentionally omits dependencies from the original Amble application, mixed original/new files, generated datasets, third-party robot models and vendor bundles. Included tests and historical handoff notes describe the full development environment; they are not a promise that this excerpt can launch it. Agent Engine Memory is optional adapter code, not a claim that its service is deployed.

## License and terms

The source and documentation included here are provided under the [MIT License](LICENSE). [Terms and scope](TERMS.md) explain what is included and what the license does not cover. The full Amble application and demo assets are not relicensed by this excerpt.

[Provenance](PROVENANCE.json) records the source revision, file hashes and small documentation/path adaptations. This is a new, curated public release; it is not a mirror of the full submission repository or its Git history.

More Amble source and documentation are planned for a later release; its scope and license will be announced separately.
