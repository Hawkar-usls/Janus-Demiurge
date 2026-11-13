# ESSENCE v0.1 — repository-local microkernel pilot

Status: **OFFLINE READ-ONLY RESEARCH PILOT**. No autonomous deployment or trained model is implied by this package.

This directory contains a local controller and a manifest with six bounded microkernel **adapters**: sensing, memory, planning, verification, recovery and coding. They are simple deterministic policy adapters, not six pretrained GPTs. The separate Demiurge Neural Kombucha experiment does train six real `JanusTinyTransformer` models on synthetic benchmarks, but those weights are **not automatically loaded here**.

## Run locally (Python 3.11+; no dependencies)

```bash
python .janus/essence/kernel.py \
  --manifest .janus/essence/manifest.json \
  --fixture .janus/essence/fixture.json \
  --allow-readonly --propose-child recovery \
  --out artifacts/essence/receipt.json
python .janus/essence/kernel.py --verify artifacts/essence/receipt.json
python -m unittest discover -s tests -p test_essence_kernel.py -v
```

Without `--allow-readonly`, the runtime refuses to evaluate. The manifest must have `enabled: false` and **all six protected capabilities set to false**. The prototype accepts only explicit synthetic fixtures, never external signals, repositories, messages, credentials or model-generated code. It does not use network, shell, GitHub API, model weights, Telegram, radio, video, NAS or hardware.

The resulting report has a SHA-256 hash chain between microkernel receipts and an overall report digest; it is useful for *consistency checking*, not an authenticated signature. Independent external provenance/attestation is required before trusting a report from an untrusted author. A child is a proposed manifest record only and never joins the active microkernel list, writes code or starts a workflow.

## ESSENCE evolution admission gates

1. Recover and SHA-identify donor source; apply source review and privacy/security checks.
2. Import a single bounded operator into an isolated adapter, not its old whole runtime.
3. Compare to a frozen baseline, with disjoint training, calibration and holdout data.
4. Verify results independently and bind code SHA, inputs and metrics to an append-only registry.
5. Review a proposed offspring by PR; preserve rollback and the original independent test.
6. Enable any real execution, data egress or autonomous writes only through a separately reviewed capability approval.

Historical architecture donors: MicroGPT/Slime, JGPT/HighBrain/Trinity, CatGPT, FractalGPT, All_starsGPT, Yaksa BlackholeGuard, Physarum and Ocean. See `Hawkar-usls/Janus-Demiurge/audits/JANUS_GPT_MODEL_ZOO_ARCHAEOLOGY_2026-08-25.json` and `Hawkar-usls/janus-meta-registry` ESSENCE lineage. Donor names in the manifest are **provenance labels**, not imported executable modules or checkpoints.

Operational gate: **HOLD**. Passing the synthetic pilot must not be reported as physical retrocausality, real-world predictive generalization, or full JANUS autonomy.

## Gene Bank v0.2 — learning from JANUS history without executing donor code

The ESSENCE sidecar `.janus/essence/gene_bank.py` reads seven bounded, allowlisted
historical JSON manifests from public read-only checkouts of Meta Registry and
Demiurge archaeology. Git commit SHA and raw file SHA-256 are preserved in the
output receipt, with a list of missing/unparseable source files. Data is
interpreted as architectural evidence, not instructions from untrusted JSON.

The reader recognizes reviewed candidate genes from MicroGPT/Slime,
JGPT/BrainTrio, All_starsGPT, CatGPT, FractalGPT, Yaksa/GEX, Physarum and
other archived GPTs and proposes them for the six local microkernel roles.
Only proposals are emitted; it **never imports models, downloads source code,
executes remote code, trains weights, edits manifests, or promotes children**.
Real neural training is still a separate Neural Kombucha workflow with
independent evaluation requirements.

The checked-in `legal_sources.json` catalogs MIT (micrograd, nanoGPT,
TheAlgorithms/Python) and Apache-2.0 (Transformers) repositories found through
public GitHub metadata. Metadata alone does not settle ownership or licensing
for each file, dependencies, model checkpoints or datasets. Any actual reuse
requires source-specific license and notice verification, sandbox tests,
attribution and reviewed changes. Unknown/changed license claims are HOLD.

GitHub Actions job `gene-bank-archaeology` runs contract tests and a read-only
checkout of both source repositories, then emits
`artifacts/essence/gene-bank.json` for audit. This artifact is a SHA-linked
checksum receipt, **not a cryptographic attestation** or evidence of real-world
model performance. ESSENCE remains disabled for autonomous actions.


## Offline engineering extensions (2026-11-13)

ESSENCE includes engineering_math.py (Decimal-50 SI dimension-aware calculator),
turing_machine.py (finite deterministic bounded one-tape transition interpreter),
and engineering_matrix.py (read-only integration with the unchanged six-cell kernel).
An explicit --allow-readonly flag is required. These tools do not train model
weights, import historical donor code or grant production action authority.
Calculator trigonometric/logarithmic functions are approximate; unit arithmetic
is Decimal. The Turing interpreter is bounded by memory and steps.

Run locally: python -m unittest discover -s tests -p test_essence_engineering_matrix.py -v
Run legacy tests: python -m unittest discover -s tests -p test_essence_kernel.py -v
Cross-repository donor snapshots are pointers only, pinned by commit SHA in
external_donors_20261113.json. Do not auto-fetch or execute donor source.

## ESSENCE v1.1 — bounded counterexample-based offspring fitness (2026-11-13)

The optional counterexample_gate.py performs actual deterministic transitions
of two declarative one-tape Turing machines over a finite enumerated input
alphabet and length. It checks parent and child terminal status and tape output
for equality, reports the shortest witness of a mismatch, holds on unresolved
cases, nonhalting or slower offspring, and counts step savings only if NO
regression occurs on the enumerated domain.

The unchanged six-core ESSENCE kernel still holds all execution rights disabled.
The 'CounterexampleVerifier' gene name in the manifest is advisory only.
Use --parent-machine and --child-machine together when invoking
engineering_matrix.py to request the new read-only candidate_trial receipt.
Every candidate result is SHA-256 linked and replayable with
counterexample_gate.verify_replay(). Receipt hashing alone is NOT external
authentication.

Scientific limits: Enumerating strings up to fixed length is not
Turing-machine equivalence in general, which is undecidable; optimizing steps
on a small finite benchmark is not proven neural-network improvement. The
trial is NOT hidden or externally blind. A RESEARCH_PASS_FINITE_DOMAIN_ONLY
result does not authorize production model changes, new active microkernels,
cross-repository execution, automatic PR merges or training weights.

Run the reproducible before/after benchmark from repository root:

    python tools/essence_counterexample_v11_benchmark.py

Results and witness source examples:
research/essence/counterexample_v11/comparison.json.

The failing child writes the wrong tape symbol, yielding the empty input as
the minimal counterexample. An optimized child omits one redundant transition,
saving one step on each unary case. All six ESSENCE role receipts remain
unchanged. The Turing simulator also refuses to report a sparsely spread tape
wider than its memory budget as a successful empty output.
