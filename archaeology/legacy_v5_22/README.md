# JANUS Demiurge v5.22 archive revival

This directory preserves and runs a sanitized archaeology snapshot recovered from the user-supplied `backups janus_cores.rar` archive.

## Preserved snapshot

- Archive SHA-256: `48cea4d9840da4e68f3dfee3cc994d71cac5bdecd2fca046990170709367f53e`
- Snapshot root: `janus_core — NG+Last 2testMMO — копия (14) — копия — копия`
- Core identity: `JANUS DEMIURGE CORE v5.22 — ПОЛНАЯ ИНТЕГРАЦИЯ ВСЕХ МОДУЛЕЙ`
- Preserved bundle SHA-256: `8ac0235a7fe1f843fee10d6af66e7305787cf089fe8b01e666bec68659577d00`
- Included source/support files: 107, byte-for-byte hashed in the manifest contained in the bundle.

The preserved bundle is intentionally sanitized. `config.conf`, runtime logs, compiled caches, legacy launchers/shortcuts, model artifacts, and machine-specific storage telemetry are excluded. The historical source bytes that are included are never patched in place.

## Why copy (14)

The archive contains 27 generations/copies. A later-looking `24.03 0226` v5.22 folder is not self-contained: compared with copy (14), 13 Python files are absent, including the convergence/core/thermal controller and the integrated module/patcher/matrix/tachyon-monitor lineage. Copy (14) is the latest archive candidate found with complete local import closure for `core.py`.

## Relationship to current GitHub history

The repository history contains a v5.22 `core.py` at commit `2bedf99d90de7700bb29b52d42d4b637d08ed41d` and v7.2 at the later line. The archive copy (14) `core.py` has Git blob id `bb252983f72978977076823315e32d6a0b487865` / SHA-256 `9a04836ac7ee1b58d0078b03133f7b619ce4df09e6190aab3827e717568881c0`; those exact bytes were not present as a retrievable blob in the repository. This archive therefore preserves a real intermediate v5.22 variant rather than merely repackaging the existing historical commit.

Current `janus_genesis/demiurge.py` and the spiral/probation control plane are later additions and are not retroactively attributed to this archive snapshot.

## Bounded revival

`legacy_ci_runner.py` extracts the preserved source into an immutable staging tree, verifies every manifest hash, copies it to a disposable work tree, and applies CI-only compatibility transforms there. The source bundle itself remains unchanged.

CI-only transforms:

- Windows-specific `system_monitor.py` -> portable read-only metrics stub.
- `aiosqlite` import -> disabled stub because the subconscious lane is disabled in smoke mode.
- outbound runtime network -> denied except loopback.
- infinite core loop -> bounded to 1-3 cycles.
- MonkeyPatcher source mutation -> suppressed.
- expensive validation sample generation -> reduced for smoke mode while keeping a real train/validation step.
- MatrixEngine unconditional CUDA allocation -> suppressed on CPU.
- Visionary events -> observed without diffusion/model download.

The workflow has read-only repository permissions, does not persist checkout credentials, does not receive legacy secrets, and uploads only the run log and receipt.

A local preflight of this exact bundle completed one bounded v5.22 cycle successfully: agent/world initialization, real `run_training_cluster`, score/loss/diversity calculation, action selection, memory/world update, and bounded shutdown all executed.

## Epistemic boundary

This revival is software archaeology and runtime restoration. Historical NP-task, Tachyon, convergence, or simulation outputs are not evidence that P=NP or P!=NP. The global P-vs-NP status remains OPEN.
