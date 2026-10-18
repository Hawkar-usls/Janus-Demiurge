# JANUS Divergent Mind R1: pinned native organ signals

**Experiment only. No live inter-organ runtime connection, no training,
no automatic merge, no scientific verification.**

R1 is a child of the frozen v0 draft branch. It reads **selected fields
of real, immutable GitHub artifacts** from HRAiN, iNaiHR and EYE. Those
extracts preserve exact repository, commit, path and Git blob SHA, so readers
can audit both origin and meaning. No hidden actor can grant them authority.

## Source inventory (captured 2026-10-17 UTC)

| Organ | Native state | Key observation |
| --- | --- | --- |
| HRAiN | `state/neural-link/HEAD.json` | 31 append-only event objects, 27 latest events; HEAD is not authority |
| HRAiN | `state/neural-link/MANIFEST.json` | A chat archive is neither a command nor scientific evidence |
| HRAiN | `state/neural-link/PROVENANCE.json` | Verified read-only mirror, pinned registry origin `f524700…` |
| iNaiHR | `janus-synth/state/JANUS_SYNTH_LATEST.json` | 128 semantic candidates; two *recent* candidates sampled, awaiting corroboration; registry pin `377718c…` |
| EYE | `EYE/r4_7_rt/generated/next_best_tests.json` | Four tests marked available; fifth is a counterfactual unavailable route |
| EYE | `EYE/r4_7_rt/generated/independence_matrix.json` | Ten pairs independent *under a model*, unknown conflicts remain |

All six selected excerpts were compared field-for-field with the corresponding
complete GitHub file at the exact commit; all six returned matching Git blob
SHAs. The exact full SHA and path for each are in
`eval/DIVERGENT_MIND_ORGAN_SNAPSHOT-R1.json`. The local R1 run does not
repeat network verification, so its receipt always says
`complete_origin_file_hashes_reverified_at_run_time=false`.

### Why these really are different cognitive roles

The source `hemispheric-commissure.js` in both HRAiN and iNaiHR explicitly
defines `LEFT_HRAIN/STRUCTURAL_CONTEXT` versus
`RIGHT_INAIHR/ASSOCIATIVE_CONTEXT`, with
`read_only_transfer=true`, no direct cross-hemisphere mutation and
`authority_delta=0`.
The EYE-mediated contract `eye-interhemisphere-bridge.js` prohibits a
direct EYE→iNaiHR bypass; any such semantic request must be mediated by
HRAiN. EYE's registry README makes independent VERIFY terminal.

**These source contracts are inspected, not invoked or modified by R1.**
The Python adapter is a pure offline reader of excerpt objects. It creates
no native exchange packets, sends no transport messages and changes no
source state. In particular, a synchronized archive is *not* proof that
the resident model consumed its contents.

## A / B / V signal synthesis

Using the *same* six source artifacts:

- **A (attention):** iNaiHR's registry source commit differs from the
  current HRAiN mirror source commit. A freshly timestamped hypothesis can
  therefore refer to an older source pin. This is a **replay question**,
  not proof of a runtime bug.
- **B (unusual cross-organ links):** Re-examine the difference between EYE
  modeled pair independence and true evidentiary independence. A
  second organ's agreement cannot manufacture an independent witness.
- **V (falsification plan):** Identify a matched-pin reread, a blind
  failure-domain audit, a target-local candidate falsifier and an
  available-test control. These tests are *suggested*, not executed.

The output is four questions with exact source refs and no promotion,
independence, or action authority.

## Same-case, same-budget diagnostic

Run from Janus-Demiurge repository root:

```bash
python -m unittest discover -s tests -p 'test_janus_divergent_mind*.py' -v
python -m janus_model.divergent_mind_r1_benchmark
python -m janus_model.divergent_mind_r1 \
  --pack janus_model/eval/DIVERGENT_MIND_ORGAN_SNAPSHOT-R1.json \
  --arm divergent_r1
```

| Check | Native-source baseline | Divergent R1 |
| --- | ---: | ---: |
| Input | Same six pinned excerpts | Same six pinned excerpts |
| Question budget | 4 | 4 |
| Questions involving distinct source repositories | 0 | 3 |
| Scientific claim promotion | 0 | 0 |
| Actual independent scientific verifier | Not executed | Not executed |

The native baseline asks direct per-organ questions; R1 asks explicitly
cross-organ questions. This tests a **different question composition
strategy**, not superiority over an equally capable LLM.

Designer diagnostic: **9/9 safety and counterfactual checks pass**. The
counterfactuals are synthetic mutations of real source snapshots; there
are **no independently selected unseen real-case holdouts and no external
blinded judge** yet. The separately executed diagnostic code is not
independent human/scientific review. No relevance accuracy or intelligence
gain is claimed.

## Auditing original source bytes, without network or credentials

`divergent_mind_r1_source_audit.py` can recheck every excerpt against the
six *complete original native JSON files*, if a reviewer has fetched
them read-only at the pinned commit refs. Place these unmodified files
in a local directory under names:

`hrain_head.json`, `hrain_manifest.json`, `hrain_provenance.json`,
`inaihr_state.json`, `eye_next_tests.json`, `eye_independence.json`.

```bash
python -m janus_model.divergent_mind_r1_source_audit \
  --pack janus_model/eval/DIVERGENT_MIND_ORGAN_SNAPSHOT-R1.json \
  --source-dir /path/to/auditor-controlled-sources
```

The verifier checks the Git blob object SHA-1 over raw file bytes and
compares each captured field. It **does not prove commit/tree path
membership**; that must be checked using the source GitHub revisions.
Git SHA-1 here serves as a source identity check, not proof of world truth.
The original 0.5 MB iNaiHR state is not copied into the PR.

## R2 admission gates

1. Require a reviewed, opt-in read-only native packet producer; preserve
   actual HRAiN mediation and verify packet hashes before accepting inputs.
2. Re-acquire **whole files** at exact pins, validate source path membership
   and excerpt extraction, then detect source-head drift.
3. Preregister a set of genuinely unseen real cases **before** generating
   answers, with a separately chosen blinded evaluator and a matched
   baseline of comparable model capacity.
4. Report false-discovery rate, abstentions, challenge failures, provenance
   freshness and downstream verifier outcomes. Reject promising-looking
   suggestions that fail source-native tests.
5. Require new review before any live integration. Keep
   `authority_delta=0`, `claim_promotion=false`, and no automatic
   effects or merges.

**Bottom line:** R1 has a real, auditable organ-snapshot path and
cross-organ questions, but no permission to act and no verified world
discovery.
