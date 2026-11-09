# JANUS-ZENO-TEMPORAL-001 — CPU Quantum Zeno & Temporal Integrity

Status: **DEVELOPMENT_ONLY** · baseline: ordinary quantum mechanics · no
production model changes · no claim of tachyon electrons or a retrocausal signal.

## Scientific motivation

The SciOne video [«Вечности быть не должно. Тогда почему она есть?»](https://youtu.be/e4k4kHzbYyU?t=837)
discusses quantum Zeno physics at 13:57–16:49 and the block-universe
interpretation at 23:26–26:53. This is a **source of hypotheses**, not physical
measurement data. Atoms in an optical lattice measured repeatedly can display
slower transitions; repeated quantum measurement does not literally stop time.

## Lane A — exact CPU Zeno curves

Prepare a 2-level system in |0>, then evolve under
`H = hbar*Omega*sigma_x/2` for total time T. Use fixed
`Omega*T` values pi/2 and pi, and fixed measurement-count grid
`0,1,2,4,8,16,32,64,128,256`.

For N≥1, perform a **nonselective** projective Z measurement after each
free-evolution period T/N. Compute two *different* observables:

- `P(all results 0) = cos(Omega*T/(2N))^(2N)`.
- `P(final result 0, all previous records ignored) = (1+cos(Omega*T/N)^N)/2`.

The latter is checked numerically by iterating a diagonal density-matrix
population update, without conditioning on the earlier results.

N=0 is the no-intermediate-measurement Born reference:
`P(final 0) = cos(Omega*T/2)^2`.

Outputs: `zeno_probabilities.json` and self-contained `zeno_survival_curve.svg`.
This specific driven qubit shows a Zeno limit; it does not establish
anti-Zeno physics, time discretization, observer consciousness, or a
controllable choice of measurement outcome.

## Lane B — Wolfram Alpha maths (not yet live)

`zeno_wolfram_bridge.py` permits exactly four fixed, public expressions
that check the analytic Zeno N=0,2,4 reference values. The offline mode is
automatically tested and explicitly says `NO_LIVE_API_CALL`.

The live API can be requested only with a manual
`workflow_dispatch.live_wolfram=true` **and** the repository secret
`WOLFRAM_ALPHA_APPID`. It makes four read-only Full Results requests at most,
fails closed if the service is unavailable, and saves verification Boolean
flags rather than raw Wolfram result text/numbers. It uses the documented
Wolfram Full Results API (https://products.wolframalpha.com/api/documentation/).
No secret, future target or unrestricted AI query is sent. No GitHub CI or
paid-query autopolling is scheduled.

## Lane C — temporal integrity / retrospective selection trap

1. `zeno_retro_control.py receiver` generates 2,048 early random bits and
   saves their SHA-256 receipt before the sender phase starts.
2. `sender` generates a separate OS-random late-choice bitstream on the
   **same runner**, binding the early receipt hash without modifying it.
3. `assess` compares **all** 2,048 early and late bits with an exact
   two-sided binomial null. It additionally demonstrates why retaining
   matches *after seeing both bitstreams* yields an artificial 100%
   selected-match rate without communicating anything to the past.

Crucially, this is a **same-runner methodological negative control**, not an
independent blinded physical experiment. A SHA-256 receipt is not a trusted
external timestamp; GitHub job order is not independent transmission; a
fortuitously small p-value alone is not proof. A future experiment must
involve an independently administered late-choice generator and external
precommitted early data, with endpoint and statistical plan fixed in advance.

## Automation and audit

Open **Actions → JANUS Ocean / Zeno Temporal 001**. On the pull request,
unit tests plus a complete offline CPU research run execute on GitHub Actions;
no torch, GPU, QPU, NAS, or paid provider is needed. Artifacts are read-only
receipts and a short provenance manifest with the Git commit and SHA-256 hashes.
Historical experiment records are never overwritten by the workflow.

If you later obtain a Wolfram AppID, set `WOLFRAM_ALPHA_APPID` in the
repository's Actions Secrets and explicitly choose `live_wolfram=true` on
a manual workflow dispatch. The live verification is optional, not a
prerequisite for Lane A or C.

This experiment tests established Zeno mathematics and temporal data
integrity. It does **not** train native Ocean weights on genuine quantum lab
observations, prove retrocausality, or generate a physical tachyon channel.
Those steps require new independent evidence.

## Beetle keyless Wolfram evidence (read-only bridge)

JANUS Ocean now has a **separate source-bound reader**:
`beetle_wolfram_readonly_gate.py`. It looks only at
`Hawkar-usls/janus-lapis`'s public `beetle-state` branch, at
`data/beetle-state/wolfram_math/zeno_n2_verified_v1.json`.

Only the small attestation is accepted; the reader never calls Wolfram
Cloud, sends a credential, or downloads the provider's answer. It checks
the *exact* query ID, expression, expected (1/4), receipt digests,
safety flags and status from the Beetle. A missing attestation yields
`NO_RECEIPT_YET`. An invalid or negative one yields a non-passing
decision; there is **no synthetic fallback to success**.

A positive result is labelled `BEETLE_WOLFRAM_MATH_REPORTED_MATCH`,
meaning the **separate Beetle client reported an arithmetic match**.
It does not mean an independent laboratory verified a quantum phenomenon,
that physical retrocausality was observed, or that JANUS is allowed to
change production weights. All official provider content remains excluded
from GitHub artifacts, including the full numerical provider result.

The Ocean workflow writes `artifacts/beetle_wolfram_math_gate.json`
and binds its status into the existing run summary. No additional
cron or third-party calls are introduced by the Ocean reader.

## V3: multi-observable CPU reference and late-choice illusion

The earlier keyless Wolfram Cloud MCP check of `cos(pi/4)^4` is archived as a
single arithmetic match, not as independent verification of the full physics model.
The new `zeno_science_council_v3.py` freezes three different quantities:

| Case ID | Expression | Physical event |
|---|---|---|
| `zeno_n4_unconditional` | `(1+cos(pi/4)^4)/2` | Final Z=0, preceding measurements unread |
| `zeno_n4_all_zero` | `cos(pi/8)^8` | All four Z outcomes equal zero |
| `bell_early_marginal` | `1/2` | Early A=0 in a Bell pair, whatever later basis B uses |

These first two probabilities are different events. They MUST NOT be conflated.

For the Bell pair (|00>+|11>)/sqrt(2), the independently calculated
unconditional marginal is P(A=0)=1/2 for all later basis rotations theta,
while the heralded subset has P(A=0 | B=0, theta)=cos(theta)^2.
Thus a postselected correlation can depend on the later choice even though
no usable raw earlier message has changed. A 513-angle independent CPU test
checks this distinction. The source code computes all four joint outcomes.

Artifacts: `artifacts/zeno_science_council_v3.json` plus the existing immutable
per-run hash manifest. This is a standard quantum theory synthetic reference:
no physical experiment, no retraining of production weights, and zero new
Wolfram provider calls in automated CI.

Future Wolfram Cloud MCP queries must be explicitly approved fixed cases
and small-scale, per the provider's limited personal-use terms. A positive
provider result establishes one arithmetic equality, not retrocausal physics.

## New V3 source-bound Wolfram N4 arithmetic attestation

The Beetle recorded one *live* keyless Wolfram Cloud MCP match for the
predeclared unconditional N=4 Zeno formula `(1+cos(pi/4)^4)/2` = 0.625.
The earlier all-zero event at N=4 has a different probability
`cos(pi/8)^8` = approximately 0.53079.

The read-only verifier `zeno_n4_wolfram_v3_gate.py` pins the source
`beetle-state/wolfram_math/zeno_n4_unconditional_v3.json` to its original
response SHA-256 and Beetle receipt SHA-256, checks the expected case
and physical event, and rejects any attempt to promote arithmetic evidence
into a proof of physical retrocausality. No provider result text, credential,
or new Wolfram request is used by the Ocean CI.

Live originating Beetle run:
https://github.com/Hawkar-usls/janus-lapis/actions/runs/42623569598.
Previous N2 V1 unresolved and N2 V2 verified records remain untouched.
