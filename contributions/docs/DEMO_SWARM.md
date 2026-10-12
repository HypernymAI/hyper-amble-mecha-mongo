ARCHIVAL NOTE: This document describes the full hackathon package. This public repository is a source excerpt and does not run as a standalone application. Refer to the root README for the hosted demo and omitted dependencies.

# Presents swarm video — recording sequence

Use the running shared city at http://127.0.0.1:3190/hypernym/presents/#now.
Record at a readable desktop width, with keys and Setup closed. Use the Town,
Street, or Angled camera preset; Reset restores the selected framing.

1. **0–15 seconds — the city.** Show the original Presents street, homes,
   healthcare/finance/construction workers, and the construction zone at the
   former corner-store footprint.
   Say: “Ambles work, earn credits, furnish their homes, and retain memory.”
2. **15–35 seconds — a real worker.** Open Jobs, show an accepted job and its
   wage, then open the named resident. Show their home and Memory. These are
   live model-backed residents; the visible queue and Atlas sync status are real.
3. **35–60 seconds — one simulated life.** Open Simulation, select a resident
   and day. Follow the same resident ID through morning, work conversation,
   memory, packs, and night. Show the item blocks and exact quantities.
   Say: “These stories are synthetic, generated from the economy ledger.”
   A useful example is healthcare resident `amble-003370433`, **day 9**:
   two jobs earn 30 credits; three packs cost 24; two mugs drop; six credits
   remain. The inventory blocks above are explicitly the final day-50 state.
4. **60–80 seconds — persistence and scale.** Show Atlas collection counts or
   a resident document with its stable ID. Show measured corpus token progress.
   The completed corpus contains 1,009,925,108 measured narrative tokens across
   the original sample and a separate 68,000-resident scale scenario. These are
   procedural synthetic stories, not LLM-generated tokens. The 5-million
   population is a separate weighted economy scenario. Atlas holds the
   10,000 sample days and proof; the bulk scale archive stays local.
5. **80–90 seconds — learning.** Show a resident’s existing learned memory or
   an explicit Dream result. Chris’s native Atlas memory, judge and dream code
   is retained. Name the actual embedding model shown on Jobs; don’t claim
   two domain models unless they are configured and verified.

Open **Construction site** (the former corner-store location) to show the
SO-101 conveyor lab. It replays two recorded MuJoCo runs; use Pause, scrub,
speed, or the run selector. Each recorded episode ends at $35. These are lab
replay dollars, not town wallet credits. Back returns to Presents. Delivery
and drone work are out of scope. Local corpus files are
not all in Atlas: the cloud holds linked samples and the live town memory.

## Simple Intel Mac handoff

Unzip the source package, then double-click **Start Swarm.command**. It uses the
same portable Presents launch approach, creates a local Python venv and installs
only the web/database requirements. The synthetic sample needs no NumPy or model
account. Live worker turns need that Mac’s own authenticated model CLI; configure
Atlas in Swarm → Setup. No accounts or secrets travel in the ZIP.

Open **Simulation** to replay sample days and see each synthetic resident’s
inventory. **Start Presents.command** still launches Chris’s original visitor
chat and Mind-panel flow. Hardware testing on a physical Intel Mac remains
pending. The corpus generator and its optional tokenizer are separate from
normal launch; the billion-token archive is not bundled into the portable ZIP.
