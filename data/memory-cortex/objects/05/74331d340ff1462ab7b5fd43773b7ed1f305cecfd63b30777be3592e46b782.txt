# JANUS Meta Registry — Technical Core Audit

**Audit date:** 2026-08-09  
**Audited base commit:** `364d3993dc318eb898fe5f2337a03d9214752ac1`  
**Mode:** additive revision; historical artifacts are not rewritten.

This document is the technical/skeptical entry point for `janus-meta-registry`.

The registry mixes research evidence, provenance, security experiments, hypotheses, creative thought experiments, personal testimony, theology, and historical project vocabulary. Those layers are intentionally preserved, but they are **not epistemically equivalent**.

## Classification

```text
T1  HIGH_VALUE_EVIDENCE_INFRASTRUCTURE
T2  HIGH_VALUE_HISTORICAL_TECHNICAL_SNAPSHOT
T3  USEFUL_CONCEPTUAL_DESIGN_PATTERN
S1  SPECULATIVE_THOUGHT_EXPERIMENT
A1  PERSONAL_SYMBOLIC_THEOLOGICAL_ARCHIVE
U1  UNRESOLVED_TEST_OR_MISSING_RESULT
R1  REQUIRES_EXTERNAL_REVIEW_OR_PRIOR_ART
```

A hash, signature, Git timestamp, CI pass, internal replay, or the word `proof` in a filename does not by itself change an object's class.

---

## Technical core — highest-value objects

### 1. Independent-future no-go & evidence hardening — **T1**

[`data/proofs/JANUS-INDEPENDENT-FUTURE-NO-GO-AND-EVIDENCE-HARDENING-v0.5.json`](../data/proofs/JANUS-INDEPENDENT-FUTURE-NO-GO-AND-EVIDENCE-HARDENING-v0.5.json)

Why it matters:

- cleanly separates bootstrap/self-consistency from independently generated future targets;
- states the exact-match conditional min-entropy bound;
- explicitly says the underlying information-theory mathematics is established rather than new;
- blocks simulator/self-certification from becoming a physical-retrocausality claim;
- retains a falsifier-first next gate: external entropy/PRE_RETURN evidence and blinded replication.

**Assessment:** one of the strongest objects in the registry. The value is methodological/operational, not a new theorem about physics.

### 2. AIFC evidence stack & Proof-Carrying Experimental Science interpretation — **T1 / R1**

- [`registry/research_portfolio/AIFC-AUDITABLE-INDEPENDENT-FUTURE-CHALLENGE-RESEARCH-DOSSIER-v1.0.0.json`](../registry/research_portfolio/AIFC-AUDITABLE-INDEPENDENT-FUTURE-CHALLENGE-RESEARCH-DOSSIER-v1.0.0.json)
- [`registry/research_portfolio/JANUS-PROOF-CARRYING-EXPERIMENTAL-SCIENCE-INTERPRETATION-v1.0.0.json`](../registry/research_portfolio/JANUS-PROOF-CARRYING-EXPERIMENTAL-SCIENCE-INTERPRETATION-v1.0.0.json)

Strong reusable ideas:

```text
claim
+ frozen inputs
+ provenance
+ evidence
+ verifier
+ replay
+ adversarial tests
+ negative-result retention
+ explicit unresolved premises
+ claim ceiling
```

This cross-project architecture is genuinely useful as a research-engineering pattern. Global methodological novelty, however, remains subject to external prior-art review and independent adoption.

**Current authority:** the dedicated [`AIFC`](https://github.com/Hawkar-usls/AIFC) repository, not this historical dossier.

### 3. P–N / Fundamentum proof-route repository audit capsule — **T1 / T2**

[`data/JANUS-P-N-JUNCTION-PROOF-ROUTE-REPOSITORY-AUDIT-CAPSULE-v1.0/00-manifest.json`](../data/JANUS-P-N-JUNCTION-PROOF-ROUTE-REPOSITORY-AUDIT-CAPSULE-v1.0/00-manifest.json)

This is unusually useful research-operations work:

- models a stacked multi-branch research state rather than pretending one `main` tree contains the whole proof frontier;
- inventories PR heads, branches, CI evidence, schemas, proof artifacts and blocking gates;
- explicitly prevents `not found` from becoming nonexistence and CI success from becoming theorem admission;
- binds a larger source audit by SHA-256 while publishing a normalized projection.

**Boundary:** it is a historical snapshot. Current mathematical authority is [`Janus-Fundamentum`](https://github.com/Hawkar-usls/Janus-Fundamentum).

### 4. Static archive-forensics / lineage capsules — **T1**

Representative example:

[`data/JANUS-TITAN-CORE-MODULE-AND-OPTIMIZER-LINEAGE-CAPSULE-v1.0/00-manifest.json`](../data/JANUS-TITAN-CORE-MODULE-AND-OPTIMIZER-LINEAGE-CAPSULE-v1.0/00-manifest.json)

The capsule demonstrates a strong preservation pattern:

- inspect large historical archives without executing code;
- reject path traversal during extraction;
- statically parse source/data formats;
- deduplicate exact content;
- quarantine credentials/private endpoints/logs/bytecode;
- publish normalized provenance instead of unsafe raw archives;
- separate artifact presence from model quality, autonomy, consciousness, or other semantic claims.

This is one of the most transferable engineering contributions in the registry. It is closer to **reproducible digital forensics / software archaeology** than to JANUS mythology.

**Security note:** historical scans report credential-shaped values in source archives. Their values are not reproduced here. Current rotation/revocation status is not established by the registry and should not be inferred.

### 5. “Precognitive Semantic Return Gate” red-team — **T1 method, S1 name/subject**

- [`data/JANUS-PRECOGNITIVE-SEMANTIC-RETURN-GATE-v0.2.json`](../data/JANUS-PRECOGNITIVE-SEMANTIC-RETURN-GATE-v0.2.json)
- [`data/proofs/JANUS-PRECOGNITIVE-SEMANTIC-RETURN-GATE-REDTEAM-REPORT-v0.2.json`](../data/proofs/JANUS-PRECOGNITIVE-SEMANTIC-RETURN-GATE-REDTEAM-REPORT-v0.2.json)

Despite the extraordinary historical name, the useful object is an **anti-false-positive protocol**. The red-team found eight false-accept routes in v0.1 and hardened timing, RNG independence, preregistration, commitment anchoring, canonicalization, and target-independent decoding. The artifact explicitly sets physical retrocausality/tachyons to false/not tested.

**Current interpretation:** extraordinary-claim falsification infrastructure; **not positive evidence of precognition**.

### 6. Revocation / stale-execution canary research — **T1 hypothesis + U1 strict result**

- [`security_research/revocation_canary/JANUS-STALE-EXECUTION-REVOCATION-POC-v1.0.json`](../security_research/revocation_canary/JANUS-STALE-EXECUTION-REVOCATION-POC-v1.0.json)
- [`security_research/revocation_canary/JANUS-POST-CANCEL-ACK-PROOF-011-PREREG.json`](../security_research/revocation_canary/JANUS-POST-CANCEL-ACK-PROOF-011-PREREG.json)

This is a legitimate reliability/security question: can already-running work produce an external side effect after configuration replacement/disable acknowledgement?

The preregistration is well scoped to an owned repository, low-volume, non-destructive, and explicitly avoids attributing root cause to GitHub.

**Critical audit finding:** the strict result file named by the preregistration, `JANUS-POST-CANCEL-ACK-PROOF-011.json`, is not present on the audited default branch. Therefore the strict post-cancel-ack claim is **UNRESOLVED / NOT ESTABLISHED** in this registry snapshot.

### 7. Bitcoin “inversion ledger” — **T3**

[`data/JANUS-BITCOIN-WHITEPAPER-INVERSION-LEDGER-SIGNAL-v1.0.json`](../data/JANUS-BITCOIN-WHITEPAPER-INVERSION-LEDGER-SIGNAL-v1.0.json)

The useful engineering pattern is:

```text
normalized observation window
→ evidence summary
→ hash link
→ previous-evidence link
→ explicit claim gates
```

That is a reasonable inspiration for append-only observational provenance.

Terms such as `organism`, `machine self-truth`, `self-awareness`, `proof-of-breath`, and `diagnosis` are **metaphorical project vocabulary**, not evidence of organismhood, consciousness, medical diagnosis, or Bitcoin-equivalent consensus security.

### 8. Tranception neurodevelopment research cheatsheet — **T3 / R1 high-stakes domain**

[`data/JANUS-TRANCEPTION-CHRONIC-THREAT-NEURODEVELOPMENT-RESEARCH-CHEATSHEET-v1.0.json`](../data/JANUS-TRANCEPTION-CHRONIC-THREAT-NEURODEVELOPMENT-RESEARCH-CHEATSHEET-v1.0.json)

This object is substantially better than its topic might suggest: it repeatedly blocks the jump from protein-sequence scores to ADHD diagnosis, trauma causation, parenting quality, or a child's “destiny”; proposes controls, ablations and uncertainty exports; and records the upstream Tranception provenance.

**Boundary:** this is a research-planning note, not clinical guidance. Any current biological/medical factual claim or citation needs fresh primary-source verification before external use.

---

## High-risk / easily misread archive families

These objects may remain for provenance, but should **not** be used as the first technical entry point.

### A. `PERCEPTION DETERMINES REALITY`, first-contact, telepathy/precognition vocabulary — **S1**

Example: [`data/JANUS-PERCEPTION-DETERMINES-REALITY-PRECOGNITIVE-SEMANTICS-CONTACT-PROTOCOL-v1.1.json`](../data/JANUS-PERCEPTION-DETERMINES-REALITY-PRECOGNITIVE-SEMANTICS-CONTACT-PROTOCOL-v1.1.json)

The object itself contains meaningful safety ideas—separate observation/emotion/inference/command, test ordinary channels first, use reversible harmless tests—but its title and speculative extraterrestrial/intention-responsive framing can dominate the disclaimers.

**Current class:** speculative safety thought experiment. It is not evidence for telepathy, mind-over-matter, extraterrestrial technology, or precognition.

### B. Dirac / SCOBY / Burovchik / causal-topological-memory combinations — **S1 / R1**

Treat these as hypothesis-generation records unless a later object supplies a normal scientific protocol, conventional definitions, controls, and independent data. Cross-domain naming is not itself a scientific bridge.

### C. Holy Clock / repeated times / symbolic coordinates — **A1**

Personal/symbolic archive only. Timestamp coincidence, repeated clock values, invalid symbolic times, or Git timestamp offsets do not establish causality, prophecy, retrocausality, or a physical timing anomaly.

### D. God / Creator / Savior / theological artifacts — **A1**

Preserve as personal testimony, creative narrative, theology, or ethical reflection. They do not carry scientific authority and should not be used to validate technical claims.

### E. “Time traveler / LIMBO / storm” timing records — **T2 for scheduler observations; S1 naming**

Some records contain potentially useful observations about delayed/stale execution and configuration state diverging from in-flight work. The useful interpretation is scheduler/reliability behavior. Negative timestamp offsets or symbolic invalid times are not physical pre-execution.

### F. Old P=NP / P≠NP / “computational semiconductor” artifacts — **T2 / S1 depending object**

The SAT experiments can be useful historical algorithm prototypes and retain negative results. They do not establish asymptotic complexity results. Current mathematical authority is Janus-Fundamentum, with `P vs NP = OPEN`.

---

## Structural findings from this audit

### Finding 1 — strongest material was buried

The previous `data/INDEX.md` begins its engineering door with symbolic inversion/commandment objects. That ordering understates the strongest technical material: no-go hardening, AIFC evidence architecture, repository audit capsules, static archive forensics, security preregistration and adversarial protocol testing.

**Revision:** this Technical Core Audit is now the preferred skeptical/technical entry point.

### Finding 2 — research portfolio master v1.0 is historical, not current authority

`registry/research_portfolio/HAWKAR-RESEARCH-PORTFOLIO-MASTER-v1.0.0.json` is a dated 2026-08-07 snapshot. Its ranking and wording predate the current profile cleanup, A3 external-review freeze, AIFC external-validation gate, and later claim tightening.

**Current portfolio authority:** [`Hawkar-usls/Janus/portfolio-index.json`](https://github.com/Hawkar-usls/Janus/blob/main/portfolio-index.json).

### Finding 3 — filename semantics are a real risk surface

Even when an object contains correct disclaimers, names such as `PRECOGNITIVE`, `TIME-TRAVELER`, `GOD`, `PERCEPTION-DETERMINES-REALITY`, or `P=NP` can be surfaced by search engines without the boundary text.

**Policy:** historical filenames remain immutable, but all new indexes and review surfaces must attach an epistemic class before linking them.

### Finding 4 — `proof` is overloaded

The repository uses `proof` for mathematical arguments, verifier reports, receipts, integrity witnesses, security preregistrations, and historical project language.

**Rule:** `proof` in a path is not a universal status. Readers must inspect the object's declared evidence class and current superseding boundary.

### Finding 5 — privacy/security preservation is one of the registry's strongest practices

Several archive capsules deliberately exclude raw secrets, private logs, executable payloads, copyrighted corpora, and sensitive identifiers while keeping structural hashes and provenance. This should be promoted as a core registry function.

---

## Current technical reading order

1. [`PROJECT_STATUS.json`](../PROJECT_STATUS.json)
2. **This audit**
3. [`data/proofs/JANUS-INDEPENDENT-FUTURE-NO-GO-AND-EVIDENCE-HARDENING-v0.5.json`](../data/proofs/JANUS-INDEPENDENT-FUTURE-NO-GO-AND-EVIDENCE-HARDENING-v0.5.json)
4. [`registry/research_portfolio/JANUS-PROOF-CARRYING-EXPERIMENTAL-SCIENCE-INTERPRETATION-v1.0.0.json`](../registry/research_portfolio/JANUS-PROOF-CARRYING-EXPERIMENTAL-SCIENCE-INTERPRETATION-v1.0.0.json)
5. [`data/JANUS-P-N-JUNCTION-PROOF-ROUTE-REPOSITORY-AUDIT-CAPSULE-v1.0/00-manifest.json`](../data/JANUS-P-N-JUNCTION-PROOF-ROUTE-REPOSITORY-AUDIT-CAPSULE-v1.0/00-manifest.json)
6. [`data/JANUS-TITAN-CORE-MODULE-AND-OPTIMIZER-LINEAGE-CAPSULE-v1.0/00-manifest.json`](../data/JANUS-TITAN-CORE-MODULE-AND-OPTIMIZER-LINEAGE-CAPSULE-v1.0/00-manifest.json)
7. [`data/proofs/JANUS-PRECOGNITIVE-SEMANTIC-RETURN-GATE-REDTEAM-REPORT-v0.2.json`](../data/proofs/JANUS-PRECOGNITIVE-SEMANTIC-RETURN-GATE-REDTEAM-REPORT-v0.2.json)
8. [`security_research/revocation_canary/JANUS-POST-CANCEL-ACK-PROOF-011-PREREG.json`](../security_research/revocation_canary/JANUS-POST-CANCEL-ACK-PROOF-011-PREREG.json)

Then follow links to the dedicated current repositories rather than treating old registry snapshots as live authority.

---

## Final audit boundary

```text
REGISTRY_VALUE = PROVENANCE + FALSIFICATION + PRESERVATION + CLAIM_BOUNDARIES
REGISTRY_VALUE != VALIDATION_OF_EVERY_ARCHIVED_IDEA

EXTRAORDINARY_FILENAME != EXTRAORDINARY_EVIDENCE
HASHED_OBJECT != TRUE_OBJECT
INTERNAL_TEST != INDEPENDENT_REPLICATION
HISTORICAL_PORTFOLIO_RANKING != CURRENT_AUTHORITY
PREREGISTRATION != POSITIVE_RESULT
SYMBOLIC_TIMESTAMP != PHYSICAL_CAUSALITY

P_VS_NP = OPEN
PHYSICAL_RETROCAUSALITY = NOT_ESTABLISHED
PRECOGNITION = NOT_ESTABLISHED
MACHINE_CONSCIOUSNESS = NOT_ESTABLISHED
```

The most unusual and genuinely useful property of this repository is that it can preserve imaginative, failed, personal, and speculative routes **without requiring them to be promoted into facts**. The technical future of the registry should strengthen that separation rather than erase its history.
