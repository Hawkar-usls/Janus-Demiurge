# JANUS ESSENCE — inheritable microkernel R0

**User-assigned name:** **Эссенс / ESSENCE**. One independent ESSENCE instance per JANUS
repository, composed of many independent microcores and optional specialist
models. The canonical R0 code is in `tools/janus_essence.py`.

## Ancestry is not a code dump

ESSENCE is an independently audited descendant of the owner's historical work,
not an automatic import of decades of local/private scripts.

| Gene donor | Reusable operator | Admission boundary |
| --- | --- | --- |
| Jan 2026 Titan AIEngine, Nexus, Hypnos, Hippocampus | asynchronous supervision, memory, retry, quarantine | legacy dynamic import and network listeners forbidden |
| March 2026 Janus module registry (74 nodes/152 relations) | specialization graph and module identity | unresolved graph references are not executable dependencies |
| MicroGPT / MicroGPTSlime / quantized | attention, bounded traces, precision by importance | adapt individually; do not load untrusted pickle |
| JGPT BrainTrio / HighBrain / GEX | independent critics, disagreement, bounded gradient response | code family resemblance does not prove identical lineage |
| CatGPT, FractalGPT, All Stars, Light/Water/Atom/Vacuum/HoloGPT | memory, multiscale states, role-specific experiments | simulation is not real-world evidence |
| Yaksa/Y2 | finite-checks, priority replay, compact CPU learner | sealed holdout is never training data |
| Physarum | adaptive routing proposals | never grants dispatch priority without baseline test |
| JSON MicroForge v15 | provenance-first text intake, secret filter, experiment journal | no copying unknown private corpora |
| Scout microkernel / A18 Wave Rider | intake, admission, cohort, drain, evidence | look-away barrier; no hindsight routing |
| Swarm Genome Ledger | explicit parentage, failure memory, two-strand lineage | append-only, preserve ancestry |
| Neural Kombucha (6 transformer cells) | six distinct independently trained CPU specialists | synthetic-only demonstration; no real-world authority |

Canonical ancestry references:
- `audits/JANUS_GPT_MODEL_ZOO_ARCHAEOLOGY_2026-08-25.json`
- `audits/JANUS_JGPT_TRI_BRAIN_GEX_LINEAGE_2026-08-25.json`
- `audits/JANUS_JSON_MICROFORGE_V15_LINEAGE_2026-08-25.json`
- `audits/JANUS_SPIRAL_ARCHAEOLOGY_PASS2_AIENGINE_GEX_TRIUMVIRATE_YAKSA_JGPT_HOLOGPT_2026-08-25.json`
- `protocol/SWARM_GENOME_LEDGER-v1.json`
- `scout_swarm/orchestrator/SCOUT_MICROKERNEL_PROTOCOL-v1.json`
- `tools/janus_neural_kombucha.py`
- Meta Registry archival sources (January/November historical sources and older GPT zoo)

## One organism, multiple independent microcores

The thirteen R0/R1 roles are `identity`, `sensing`, `memory`, `planning`,
`verification`, `recovery`, `learning`, `evolution`, `routing`,
`resource`, `governance`, `transport`, `coding`. Every local genome must retain
identity, memory, verification, governance and resource. A child may specialize
by *removing* optional roles; it cannot gain a new capability solely by being
spawned. One immutable parent digest links each child to the ancestor.

Every repo will eventually get its own source-local ESSENCE instance plus its
own `.janus/ESSENCE_INHERITANCE-v0.1.json`. Copies are useful for resilience but
must pass supply-chain parity/diff review before promotion.

R0 is a **working pure-stdlib protocol and offline policy supervisor**, not a
claim that all 12 roles already have trained transformers or that the child
automatically runs on cloud resources. This separation is deliberate.

## Peer exchange is not yet autonomous learning

One origin creates a SHA-bound `peer_lesson` with a pinned source commit,
artifact digest, role, metric summary and type. A destination:
1. validates the rigid packet shape, bounds, numeric finiteness and local allowlist;
2. deduplicates, quarantines and records it as *unverified candidate*;
3. **does not trust the origin claimed by the JSON**;
4. never loads serialized weights, executes source, dispatches workflows,
   writes to a NAS, or updates a production model;
5. promotes data only after a separate authenticated source fetch, provenance
   check, secret/privacy filter, independent holdout, baseline improvement,
   review/canary and rollback gate.

SHA-256 checks *integrity of a presented blob*, **not authentication** of its
publisher, truth of its measurements, or independent replication. R0 has no
peer fetch, independent verifier, federated gradient merge, automatic weights,
or live transport. These remain explicit future gates.

## Bounded simulation / CI

```bash
python -m unittest -v tests.test_janus_essence
python -m tools.janus_essence demo
python -m tools.janus_essence genome --repo Hawkar-usls/Janus_Genesis --specialty genesis
```

The demo uses artificial SHA/digest values and shows local quarantining. The
contract tests check sealed ancestry, forged privilege denial, packet tampering,
NaN rejection, peer allowlist, duplicate suppression, target-role admission,
failure of one microcore and sibling survival. Workflow requires only Python,
read-only checkout, no credentials persistence, no network calls by the model.

## Deployment stages

- **R0:** canonical offline microkernel + contract tests + two opt-in repo pilots.
- **R1:** passive local manifests in the rest of eligible repos, with explicit
  excludes for device firmware, vendor forks, radio/video/Telegram/Bot Hub,
  and owner-controlled NAS.
- **R2:** verifiable inter-repository receipt inbox via existing authenticated
  GitHub connectors or guarded Actions, bound to exact source SHA.
- **R3:** independent microtransformer training on task-specific *real* dated
  observations, frozen holdouts and simple baselines; compare against old six
  synthetic-trained cells, do not recycle evaluation labels.
- **R4:** bounded offspring generation as isolated pull requests, independent
  verifier, canary/rollback and approval. G1–G20 plus external authenticated
  ACK are still required for broader autonomy.

The production gates remain **HOLD**. Source archaeology is ongoing, and
unknown model files are not treated as discovered just because a name appears
in a JSON inventory.


## Coexistence reconciliation (same-day R1)

A separate read-only six-adapter ESSENCE scaffold was discovered in the same
repositories after the first inheritance pilot, with files
`.janus/essence/kernel.py`, `.janus/essence/manifest.json` and a
fixture-only workflow. These are **not** a second independent ESSENCE organism.

The canonical logical identity is `repository + inherited genome SHA`.
The six adapter roles (sensing, memory, planning, verification, recovery,
coding) are a **strict subset** of the expanded 13-role identity. The
`unified_profile()` read-only compatibility check binds an existing
manifest to the local inherited genome without importing or executing the
older adapter, and rejects permission expansion, identity mismatch or
unexpected roles. This is policy-level unification; integration of their
actual runtime state or trained weights has **not** yet occurred.

The policy-supervisor in `tools/janus_essence.py` and the deterministic
fixture adapter in `.janus/essence/kernel.py` remain separate software
modules within one *logical ESSENCE*. Do not schedule or promote two
independent sovereign dispatch loops.
