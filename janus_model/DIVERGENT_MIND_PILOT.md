# JANUS Divergent Mind v0 — A / B / V exploratory pilot

**Status:** research-only, read-only, opt-in prototype. No production cognitive
loop has been rewired. No autonomous repo operations, model weight training,
scientific-gate edits, or deployment are included.

This pilot takes inspiration from the user's request to emulate three useful
properties of an altered perspective **without** claiming intoxication, human
subjective experience, or improved intelligence:

- **A — atypical attention.** Notice stale versus current source states, and
  rarely co-occurring analytical operators. An old failure followed by a new
  acknowledgement is a *temporal transition*, not proof of an active outage.
- **B — bridge generation.** Generate bounded, low-confidence analogies
  between distinct domains (e.g. durable context admission and Beetle ACKs)
  using a small allowlist of explicit operators.
- **V — adversarial verification questions.** For each leading bridge, ask
  what domain-native observation would falsify it. **No verifier is actually
  executed** in v0; every scientific/causal conclusion remains open.

The letter V stands for *verification design*, not a successful verification.
The generator uses a deterministic heuristic on observations, **not an LLM**,
and is not yet wired to live HRAiN, iNaiHR, EYE R3, or native-model runtime.
Those systems informed the A/B/V interface and are possible read-only future
consumers or candidate sources. The pilot never asserts that distinct repos,
models, or lineage labels establish independent scientific evidence.

## Exact source-bound pilot corpus

The input pack is
`janus_model/eval/DIVERGENT_MIND_SOURCE_PACK-v0.json`. Its 13 observations
cover Janus-Demiurge, Genesis, EYE R3, Beetle/Lapis, Cosmos, TOPA,
Fundamentum, AIFC and IO. Every item carries:

`{id, domain, subject, lineage, repository, commit, path, value, observed_at, operators}`

The full 40-character commit SHAs and paths are immutable snapshot references,
not links to moving `main`. For example:

- Beetle/Lapis health at 20:45:31 UTC recorded Cosmos as STALE / NO_ACK.
  Cosmos `beetle-memory` ACK recorded receipt at 20:49:00 UTC; the older
  health snapshot is **not** a live diagnosis.
- Genesis's current-head Nexus integration view (an **open PR**) requires
  fresh replay on its own exact pinned heads. Old PASS cannot be inherited.
- Cosmos and TOPA have **open** JWST research PRs derived from the *same*
  underlying observational study; two repositories do not create two
  independent measurements.
- EYE R3's candidate count and its strict-order failure are separate
  observations, not equivalent acceptance criteria.
- Fundamentum's P vs NP status remains **OPEN**. Native training receipts,
  machine-psychology proposals, and Beetle staged context are not claims of
  general intelligence, scientific proof, or runtime memory consumption.

The source paths were checked against the pinned GitHub revisions during pilot
construction. This is a human-curated snapshot, not automated runtime
source-contents verification. In particular, open-PR data are **candidates**,
not merged, authoritative defaults.

## Safety and interface

`python -m janus_model.divergent_mind --pack janus_model/eval/DIVERGENT_MIND_SOURCE_PACK-v0.json`

The CLI writes JSON to stdout, or optionally to a **caller-controlled local**
`--out` path. The inference core has no network, git, shell, credential,
repository-write, or model-promotion calls.

- Maximum 80 input observations; 16 attention events; 24 cross-domain
  candidates; 12 falsification questions.
- Unexpected fields, hidden labels, nonexact commit refs, unknown operators,
  path traversal, duplicate IDs and non-UTC timestamps are rejected.
- Every candidate retains exact repo/commit/path/lineage provenance, marks
  `independence_verified=false`, `claim_promotion=false` and
  `effect_authority=false`.
- The top-level receipt returns `authority_delta=0`; cross-repo writes,
  autonomous merge, external effects and scientific promotion are false.
- A source operator match is a suggestion to ask a question; **it cannot
  satisfy VERIFY, observational independence, causal identification or
  mathematical proof gates**.

## Reproducible algorithm-blind *smoke* benchmark

```bash
python -m unittest discover -s tests -p 'test_janus_divergent_mind.py' -v
python -m janus_model.divergent_mind_benchmark
```

`DIVERGENT_MIND_PRIVATE_EVAL-v0.json` is *separate from generator inputs*.
“Private” means algorithm-blind, **not secret or independently authored**.
The rubric contains four designer-defined heuristic question-relevance targets
and controls for false independence, stale-state errors, claim escalation,
closed scientific gates and zero execution authority.

| Pilot metric | Structural baseline | A/B/V pilot |
| --- | ---: | ---: |
| Attention signals | 2 | 2 |
| Cross-domain candidates | 0 | 24 |
| Falsification questions | 0 | 12 |
| Designer relevance targets captured | 0 / 4 | **3 / 4** |
| False-promotion/lineage/temporal safety checks | pass | pass |

Result as of the pinned fixture: **smoke pass** (14 unit tests); *not* an
accuracy result or a matched-AI intelligence comparison. The baseline was
deliberately defined to have **no** bridges, so any apparent gain on bridges
is mechanical. The pilot misses one predeclared comparison:
Fundamentum's proof gate versus the unresolved JWST interpretation
(`CLAIM_BOUNDARY`), because the 24-candidate budget truncates hypotheses.
That miss is retained openly rather than optimized away after scoring.

Current limitations include heuristic analogy volume (24 may be noisy),
researcher-authored targets, small/selected JANUS cases, possible stale
human-curated observation values, lack of independent holdout review,
and absence of live cognitive-loop integration.

## Proposed gated path to R1

1. Have HRAiN submit structural attention pointers and iNaiHR submit
   associative candidates in *read-only, source-pinned packets*.
2. Let EYE R3 propose structural analogies with explicit negative controls;
   never treat its index counts as proof of working mechanisms.
3. Route top hypotheses to a **separate** domain-native verifier. A skeptical
   judge should evaluate blinded candidates and matched-baseline outputs;
   add preregistered unseen cases and false-discovery accounting.
4. Only after independent review consider an opt-in consumer of the resulting
   question-only packets. Preserve science gates, provenance, and
   `authority_delta=0`. Any new effect authority needs a different proposal
   and explicit review.

**Checkpoint:** this PR stages a reproducible experiment. It changes no
production JANUS decisions and no external repository.
