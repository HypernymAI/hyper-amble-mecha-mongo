ARCHIVAL NOTE: This document describes the full hackathon package. This public repository is a source excerpt and does not run as a standalone application. Refer to the root README for the hosted demo and omitted dependencies.

# Recorded SO-101 construction lab

The construction lab is a local browser replay of two recorded MuJoCo episodes.
It does not run physics, control a robot, call a model, or earn town credits.
Its dollar ledger belongs to each recording; there is no live wage bridge.

Source ZIP SHA-256, supplied with the handoff:
`1128b9287010deade080e58fd410a11014dfea7ab88af1ed056f587933a84b04`.
Only `hypernym/presents/sim/` was copied from the extracted handoff into
`web/static/presents/arm-lab/`. The old street, pack audio, sample deck and
preview launch scripts were not imported or executed.

Open `/static/presents/arm-lab/index.html`. Embedded Back emits the existing
same-origin `presents:leave-terminal` message. Standalone Back returns to
`/hypernym/presents/#now`. The parent shell may send `presents:visibility`;
the replay verifies the sender and origin before changing visibility.

The import map uses the existing `/static/elsewhere/vendor/three.module.js`.
Both existing Three.js r184 bundles matched the handoff exactly:

- `three.module.js`: `36a60b0120335f89a80a0dab70292292b0ec414b3d05e83cd09a3ea428c6712a`
- `three.core.min.js`: `6486aa0d719cfa87ec88dc47223b59b1fb8417a1a407fc0e52467c943e2f8cc9`

The lab retains the supplied robot, urdf-loader and Three.js add-on notices.
The robot notice describes upstream simulator files beyond this browser subset;
this import contains the URDF and its referenced STL meshes, not the upstream
MuJoCo XML scenes. The copied application notice now names the shared vendor path.

Static checks resolved the JavaScript imports and every URDF mesh reference to
local assets. The scene and episode-index files resolve locally. Both episodes
have increasing frame timestamps, six joint values per frame, ledger amounts
matching the recorded payout table, and final frame balances matching their
ledger sums and index summaries. Seed 0 runs 60.08 seconds; seed 3 runs 60.00
seconds. Each recording ends at $35, with seven red squares in the bin.

Changes to the imported app are limited to the Three.js import path, standalone
Back destination, and explicit recorded-dollar labeling. Primary browser verification passed: the robot and conveyor rendered in Presents,
both episodes loaded, pause/play and seeking worked, the final recorded ledger
showed $35, and Back returned to the original street. Construction-site re-entry
also passed, with no browser console errors. Physical hardware control is not included.
