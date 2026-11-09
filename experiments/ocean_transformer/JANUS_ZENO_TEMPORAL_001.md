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
