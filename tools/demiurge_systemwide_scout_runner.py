#!/usr/bin/env python3
"""Run the existing JANUS public-research engine against the system-wide mission.

This wrapper preserves the default HA10 mail mission and selects the next-turn
whole-system council mission only for this workflow.
"""
from pathlib import Path
import demiurge_mail_research_swarm as base

base.MISSION_PATH = (
    Path(__file__).resolve().parents[1]
    / "scout_swarm"
    / "missions"
    / "JANUS_FULL_SYSTEM_SCOUT_DIRECTIONS-2026-08-22-v1.json"
)

if __name__ == "__main__":
    raise SystemExit(base.main())
