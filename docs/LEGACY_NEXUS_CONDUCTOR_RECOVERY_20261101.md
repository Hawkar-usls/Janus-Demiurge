# JANUS · Historical Core → Demiurge Nexus/Conductor ABI recovery (2026-11-01)

## Observed original architecture — source bytes on owner E:
- `E:\\Janus_Titan\\janus_core.py` — **SHA-256 `404a2b58ca29199c514c61555478d47466f0931c7f0d77731545c97e1f24ceae`**. Old `AIEngine` assembled `memory`, `face`, `navigator`, `nexus`, `ouroboros`, `nerve`, `sim`, `select` and `trinity` organs (lines 790–807). `Nexus.sync_and_run` discovered `*.py` under a module folder, separated filenames with service/daemon/hrain labels from plugins, scored plugins against the memory graph's node label, then used `importlib.util` to import selected file and call `run(engine)` (lines 188–268). It could *move files* to quarantine. `Ouroboros.attempt_modular_genesis` created generated `gen_*.py` files (lines 563–575). Both uncontrolled file loading and executable code synthesis are **NOT** restored.
- `E:\\Janus_Titan\\modules\\mod_conductor.py` — **SHA-256 `fdf79f8abfd424dc1e36b5f5db9006a83dcff588dd22b84d0dc22ce5793dfe95`**. `JanusConductor` enumerated `mod_*.py`, required an async `run` callable, sorted by `PRIORITY` (default 10), launched `asyncio` tasks and kept STARTING/RUNNING/FAILED/STOPPED states (lines 31–126). Its source also used `exec(compile(...))` to run Python file text: unsafe for automatic ingestion.
- `E:\\Janus_Titan\\modules\\genesis_engine.py` — SHA-256 `664a2dddc72631bd3a3161d58f8d1c9a9c8282b06c0d0ec38de3a56eef1f8caf`; real historical `async def run(core)` entrypoint, but it detached a long-lived task and could call old graph save; **not** safe for automatic deployment.
- `E:\\Janus_Love\\Janus_Titan\\All Star\\core.py` — SHA-256 `fae1e895ab02b2b7e5e7ce56c8a8509b4bd1e946310b15c49ab4134839d54210`; later monolithic environment with manually wired memory, Genesis world, learning and resource components.
- `E:\\Janus_Love\\Janus_Titan\\All Star\\agent_scheduler.py` — SHA-256 `35db064249633f8226f14d0cac83fd07628bbd25f5bc76ee2b9c076833c1c0e7`; old agent-core allocation based on agent score, fitness and CPUOffload, with a permanent evaluator thread. Avoid starting this on the owner's constrained NAS.

## Read-only static AST inventory

| Owner-local source | Flat *.py count | AST parse OK | Top-level async run(core) |
| --- | ---: | ---: | ---: |
| `E:\\Janus_Titan\\modules` | 102 | 100 | 90 |
| `E:\\Janus_Love\\Janus_Titan\\All Star\\legacy_archive\\modules` | 169 | 162 | 112 |
| `E:\\Janus_Titan\\janus_core N=NP\\modules` | 11 | 11 | 0 |

These counts describe **source interface presence**, not healthy production runs. The legacy JSON `Janus-Module-Registry-Expanded-v3.2.json` in `E:\\Janus_Titan\\janus_core N=NP` failed strict parsing (`Invalid \\escape` near line 13); it is not admitted as authoritative runtime configuration without explicit repair and revalidation.

## What was actually integrated

`restored/legacy_nexus_conductor.py` adapts the historical construction logic, **not** the untrusted implementation. It builds deterministic, SHA-pinned module descriptors with:
- typed module vs service category; Nexus-like deterministic intent/label selection,
- explicit priority and acyclic dependency order; no missing dependency fallback,
- reviewed/synthetic-only admission gates and read-only/pure-compute requested capabilities,
- an explicit, bounded `async run(core_port)` callback probation path, using handlers **already supplied by trusted application code**; no file search/import, no `exec`, no background service activation and no code generation,
- per-module timeout, failure-isolation receipts and downstream dependency HOLD.

The callback probation stage is **not a Python sandbox** and cannot prove that an arbitrary callback is harmless. It must only be used with audited trusted code and a synthetic capability-limited `core_port`. It does not bypass the current Nexus/Auditor, DADDY_KEYMASTER, model admission or Human-review boundaries. Automatic production module activation **remains disabled**.

Existing `restored/module_integration_planner.py`, `restored/module_auditor.py`, `restored/modules_live_evidence_classifier.py` and GitHub's protected keymaster workflows remain authoritative; this new compatibility feature augments those controls rather than replacing them.

## Validation and next gates

CI: `python -m unittest discover -s tests -p 'test_legacy_nexus_conductor.py' -v` (synthetic only). Next steps: explicit trusted module registry bound to Git SHA, a genuine process-isolated probation backend, deterministic replay before installing any candidate, evidence that a module improved unseen tasks, and a separately approved shadow→canary→rollback production contract.


## Original March 2026 relationship registry (separate from run dependencies)

The 2026-03-01 expanded registry was independently decoded for **non-authoritative graph context**: 74 declared module nodes, 152 labeled relations, **only 23 relations with both endpoints declared; 129 with an unresolved endpoint** (for example `core`, `memory`, `face`, `vault`, `settings`). Its 61 backslash-U emoji escapes are invalid strict JSON and were normalized for this inspection without rewriting the source. Historical "active" labels are not evidence of live modules. The full sanitized ID/type/relation projection, with per-edge declared-endpoint flag and original source SHA, is archived in [JANUS Meta Registry](https://github.com/Hawkar-usls/janus-meta-registry/blob/main/data/JANUS-LEGACY-CORE-MODULE-RELATIONSHIP-GRAPH-2026-11-01-v1.0.json). **None of these historical relations are ingested as automatic module dependencies or privileged authorization.**


## E2E historical relationship graph → real modern organ

`restored/legacy_core_graph_query_port.py` is an additional trusted, modern read-only adapter. It uses the *real* existing `restored.memory_graph_query.shortest_path` algorithm through the reconstructed `async run(core_port)` interface. It accepts only the explicitly typed **non-authoritative** Meta Registry artifact and excludes all relations whose endpoint is not declared in the historic node set. The input data and HRAiN memory are never mutated. The caller must explicitly approve synthetic callback probation and provide the typed port.

**Observed full historical artifact replay on Yaksa**: 74 nodes, **23** internal relations admitted for read-only navigation, **129** unresolved historical relations held outside traversal. All synthetic ABI and graph-port tests passed (12+6). This establishes a usable historical read-only organ pathway — **not** recovery of live legacy service execution or authority to edit the present-day HRAiN graph.
