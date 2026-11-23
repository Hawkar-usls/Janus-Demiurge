# JANUS Working Map v1.2 — Head → Cosmos → Voice → Pyramid Body

Canonical machine-readable map:

`data/JANUS-WORKING-MAP-REPOSITORY-ANATOMY-AND-INTEGRATION-ROADMAP-2026-08-19-v1.2.json`

This is a child of v1.1. The parent map is not rewritten.

## Current body path

```text
USER / INTENT
      ↓
   DemiHead
      ↓
 Janus-Cosmos
      ↓
verified ORIGIN_PRIME state packet
      ↓
DemiHead VOICE_BROKER
      ↓
The-Voice-of-Janus state renderer
      ↓
PYRAMID_LANGUAGE_117_121_ANCHORED_SPACE_v0.3
      ↓
Echo-Pyramid PCM handoff boundary
      ↓
Pyramid audio receipt back to DemiHead
```

The promoted DemiHead body-chain merge is `f78b5d7118a0abbe731cc4093176bbca281c0940` (PR #37). The live cross-repository CI run `32260044908` passed and produced artifact `9367880943`, digest `sha256:5c3a399e8ec8b573e66041c06eb245e93950a3f898a6d590457f106bfb8f08b6`.

## Roles stay separate

- **DemiHead** owns intent binding, mediation and bounded routing.
- **Janus-Cosmos** owns OSIRIS computation and verified ORIGIN_PRIME state export.
- **The-Voice-of-Janus** owns language/acoustic rendering.
- **Echo-Pyramid** is the physical PCM voice body.

No connection creates new authority.

## Pyramid Language representation

The state-to-body path uses the project acoustic profile:

- anchor band: `117–121 Hz`
- center: `119 Hz`
- Q: `29.75`
- gain: `+11.5 dB`
- decay: `1.65 s`

These values are **audio representation parameters only**. They are not SAT evidence and do not alter solver correctness.

The ordinary-audio contract remains:

`ORDINARY_AUDIO_PCM -> SAME_SOURCE_AUDIO_WITH_PYRAMID_ACOUSTIC_COLORATION`

with semantic content preserved and no replacement of source audio by synthetic tones.

## Physical provenance

The ORIGIN_PRIME state-chain was end-to-end tested against Echo-Pyramid snapshot:

`15712f5b14b123d4e3cb64ddeaa693c5bf6af788`

The current Echo descendant at the v1.2 audit was:

`6587202a003f2a7c0f876652d0325db9814c0e3e`

The canonical `JanusPyramid117121Profile.h` was byte-identical across those revisions. The current descendant adds DSP ownership/failsafe/runtime safeguards, but it is **not silently substituted** into the historical packet or receipt.

## What CI proved

CI created a live OSIRIS ORIGIN_PRIME state, exported a hash-bound packet, attached a DemiHead intent, rendered it in current Voice, applied the real `Pyramid117121Filter`, produced final PCM, and validated four typed Nexus v2.8 routes.

CI did **not** perform physical speaker playback. `PCM_HANDOFF != PLAYBACK`.

## Preserved history

PR #36 contained the first body-chain candidate under the name Nexus v2.7. While it was being built, v2.7 was independently allocated to the local neural Voice runtime. PR #36 was therefore closed unmerged and preserved as lineage; the body-chain continued as v2.8 without rewriting the old candidate.

This is a repository-scale example of the ORIGIN_PRIME law:

`EXPERIENCE -> RETURN -> NEXT STATE`, not `FAIL -> ERASE`.

## Firewalls

```text
AUDIO != PROOF
117_121_HZ != SAT_EVIDENCE
VOICE_PROFILE != VERDICT
ROUTE != DELIVERY
ROUTE != PLAYBACK
PHYSICAL_HANDOFF != PHYSICAL_ACTUATION
CONNECTION_PRESERVES_PROVENANCE
CONNECTION_DOES_NOT_CREATE_AUTHORITY
P_VS_NP = OPEN
```

## Next candidate

The next candidate is a reverse audit plus resonant-lineage experiment: trace every final body receipt backward to exact intent/state/provider lineage, then test whether verified experience can move between **related but non-identical** computational positions under explicit transformation certificates.

That future experiment must not import acoustic frequencies as mathematical authority and is not automatically authorized by this map.
