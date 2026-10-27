# All Star HRAiN source intake · 2026-10-27

Imported source: owner's private local `All Star/experimental_sat_profile.py` (SHA-256 `0c1baa31fca64add6aa2d299b444951887767a3bd269acd68a4ef0e9ebbfacc9`).
This project file contains no private source graph data; private logs, trained weights, model-zoo data and token files remain off GitHub.

The source describes a bounded **SAT clause occupancy / graph-saturation heuristic**, *not* a proof of P=NP or a universal decision algorithm. Preserved as `restored/experimental_sat_profile.py` rather than wired into autonomous production.

Safety adaptations: strict n ≤ 8, ≤ 32 clauses and ≤ 12 power-sum orders, explicit invalid-literal rejection, and Python arbitrary-precision integer power sums to avoid silent NumPy int64 overflow. Histogram recovery still uses floating-point least squares; `recovered_histogram` is approximate and must not be treated as a certificate. CI uses synthetic examples only.

**HOLD:** Do not automatically import `hrain_autonomy.py`, `ecosystem_bridges.py`, `janus_log_ingest.py` or `project_paths.py`. They contain graph-mutating pruning, unverified memory/network imports, potential sensitive-log corpus ingestion and import-time directory creation, respectively. These require separate API contracts, privacy filtering and regression tests. Do not replace the owner's original HRAiN or iNaiHR interface.
