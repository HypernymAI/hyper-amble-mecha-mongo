"""Recorded construction demonstrations at the existing corner-store footprint."""
from __future__ import annotations

WORKSITES = (
    {"id": "arm-site", "name": "Construction site · SO-101 conveyor lab", "profession": "construction", "place_id": "store",
     "status": "replay_ready", "detail": "SO-101 recorded MuJoCo conveyor runs are ready in the construction site. Recorded lab dollars are separate from town credits.", "demo_url": "/hypernym/presents/#arm"},
)


def snapshot():
    return [dict(site) for site in WORKSITES]
