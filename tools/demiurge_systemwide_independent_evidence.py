#!/usr/bin/env python3
"""Run deterministic evidence expansion against the system-wide JANUS mission."""
from pathlib import Path
import demiurge_mail_research_swarm as base

base.MISSION_PATH = (
    Path(__file__).resolve().parents[1]
    / "scout_swarm"
    / "missions"
    / "JANUS_FULL_SYSTEM_SCOUT_DIRECTIONS-2026-08-22-v1.json"
)

import demiurge_independent_evidence as independent  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(independent.main())
