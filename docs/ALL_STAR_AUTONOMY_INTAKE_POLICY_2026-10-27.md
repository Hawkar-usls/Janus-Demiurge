# JANUS All Star intake · review-first, not bulk copy (2026-10-27)

Source: owner-authorized `E:\\Janus_Love\\Janus_Titan\\All Star`. The connected Windows system is needed to read private local files; GitHub Actions cannot access this path. No remote desktop credentials or unattended access scripts have been added to GitHub.

## Safe workflow

1. From the owner computer, run `python tools/janus_all_star_intake_catalog.py --root "E:\\Janus_Love\\Janus_Titan\\All Star"`. This inventories only an explicit allowlist of code in the directory root.
2. Review aggregate `STATIC_REVIEW_ONLY` statuses and signal flags. Every candidate has `autonomousImportAllowed: false`, regardless of whether flags are empty. No source file, model, private JSON, logs or archive is copied or pushed by the tool.
3. Select a component, audit side effects, provenance, dependencies and secret exposure. Transfer only reviewed code to `restored/` or its canonical owning repository on a branch.
4. Run synthetic Windows/Linux CI and independent rollback tests, then merge only with passing gates. Live HRAiN memory is never a CI fixture.

The upstream All Star `project_paths.py` creates directories **at import time**. The new `restored/project_paths.py` is a pure portable resolver with an explicit `safe_inside()` containment check; it never creates directories automatically.

P0 reference: Demiurge #342 (lossless live compaction) and #346 (retention, journal and restart gate). PRs #343/#344/#347 already quarantine destructive compression and retention, and #348 imports original growth logic only into a disarmed sandbox. Do not mistake these for unattended production activation.

**Important:** An already running owner-local Python process may continue using earlier imported code. A controlled checkpoint/restart is required to guarantee activation; no such restart has been performed by this intake workflow.
