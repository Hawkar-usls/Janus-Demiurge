# JANUS LOGOS-001 R1.4 — sealed external scientific law evaluation

Status: **SCIENTIFIC EXTERNAL VALIDATION NOT RUN — independent data custodian NOT appointed**. This is a testable interface and a fixed method, not a scientific win.

## What must be genuinely independent?

A third-party scientific evaluator must be the **only** holder of three fresh, unrelated real physical-science TEST datasets and their unknown-to-JANUS test labels. Candidate sources should differ by underlying measurement and physical domain (e.g. optics, materials/mechanics, thermal/electromagnetic), and must not overlap with any NIST corpus already evaluated in R0–R1.3.

See [preregistration](../../../data/JANUS-LOGOS-001-R14-PREREG-v1.0.json). Before accepting any final outcome, the evaluator's independent identity and Ed25519 **public** key must be vetted in a separate GitHub PR and recorded in [custodian registration](../../../data/JANUS-LOGOS-001-R14-CUSTODIAN-REGISTRATION-v1.0.json). The private key and all sealed labels must **remain outside** JANUS, GitHub Actions, ChatGPT conversation logs, external APIs and commits. A self-generated test key never constitutes independent evidence.

## Final submission interface (evaluation organizer runs on isolated compute)

```bash
python research/logos_001/r14_external/r14_submission.py \
  --input /secure/evaluator/train_validation_test_x.json \
  --out /secure/evaluator/candidate_predictions.json
```

Accepted input (per domain):
```json
{
  "domain_id": "anonymous_physical_domain_001",
  "train": [[0.1, 1.4]],
  "validation": [[0.2, 1.5]],
  "test_x": [0.35, 0.45]
}
```
The arrays shown above are illustrative, **not long enough** for actual submission: require >=7 train and validation observations, >=9 train distinct x, >=3 validation distinct x, >=10 TEST distinct x, all disjoint. The organizer supplies already normalized x coordinates in [0,1] using a public precommitted normalization agreed before hidden TEST. Participant sees no TEST labels. No Internet, inference API, Rowan credits or unbounded arbitrary math expressions.

The sealed evaluator, **not the participant**, fits and chooses the standard polynomial/spline/RF/KRR baselines using TRAIN and VALIDATION and evaluates on TEST. The [reference evaluator](r14_custodian_reference.py) is example implementation to deploy **only by an independent custodian**, using their private datasets locally; the function never includes test labels in the output receipt. Its own output is `UNSIGNED_DRAFT_NOT_EXTERNAL_PROOF` until that independent custodian certifies and signs a separate receipt. The signed receipt should contain only aggregate metrics, model decisions, bootstrap intervals, provenance commitments, and a fixed participant commit SHA. Never upload or print the input held in the evaluator's private storage.

The evaluator may use [Codabench](https://docs.codabench.org/latest/Organizers/Benchmark_Creation/Competition-Design/) as a hosting model, but **no existing suitable competition, account, private data provider, or active competition submission has been verified or claimed**. In Codabench use code-submission mode so reference data and hidden test inputs/labels stay on its worker. A source-controlled implementation alone does not make the experiment double blind.

## Signed result gate

The custodian produces a canonical result JSON and detached Ed25519 signature. The public key is pre-registered **before the final TEST** and vetted for independent ownership; no signing private key is ever committed. Use `r14_external_receipt_gate.py` to verify the exact JSON bytes against the approved registered key. It refuses missing registration, bad signatures, malformed evidence, inconsistent success counts and production-promotion flags.

The fixed scientific gate is **3/3 distinct physical domains** with ≥5% holdout RMSE advantage over independently validation-selected strong baselines and a positive 95% paired distinct-group bootstrap lower bound; otherwise report failure or partial results. A signature authenticates provenance to an approved custodian key; it is not proof of divine law, and its scientific interpretation remains limited by domain/sample design.

Regardless of an external numeric success, **production Demiurge model promotion remains blocked** and would require a separate authorized validation gate. R1.4 does not decide P=NP.

## Public CI fixture: test the contract only

```bash
python research/logos_001/r14_external/r14_public_smoke.py --mode participant --out /tmp/r14-fixture-proposals.json
python -m pip install numpy==1.26.4 scipy==1.14.1 scikit-learn==1.5.2 cryptography==44.0.3
python research/logos_001/r14_external/r14_public_smoke.py --mode custodian --input /tmp/r14-fixture-proposals.json --out /tmp/r14-fixture-receipt.json
python -m unittest discover -s research/logos_001 -p test_r14.py -v
```

All fixture labels are generated in public source and cannot serve as independent scientific evidence. GitHub CI explicitly expects `UNSIGNED_DRAFT_NOT_EXTERNAL_PROOF` and refuses interpreting it as an externally verified result.

## Next admissible real-world action

Secure a vetted third-party lab/benchmark custodian who will hold the test labels and signing key, approve an independent evaluator registration, freeze an exact release commit and one-submission policy **before acquisition/scoring**, run one sealed evaluation, sign aggregate metrics and import the resulting receipt after cryptographic verification. Until then the only correct verdict is **BLOCKED_PENDING_EXTERNAL_EVALUATOR**.
