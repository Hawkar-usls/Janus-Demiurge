# JANUS-ZENO-TEMPORAL-003 — published ion laboratory measurements + prospective blind beacon

Status: **DEVELOPMENT_ONLY**; external lab measurements from a published paper, not new quantum experiments run by JANUS.

## Lane 1 — Real published laboratory values (1990)

Source: W. M. Itano, D. J. Heinzen, J. J. Bollinger and D. J. Wineland,
*Quantum Zeno effect*, Physical Review A **41**, 2295–2300 (1990),
DOI: https://doi.org/10.1103/PhysRevA.41.2295.
Original U.S. Government study, accessible at
https://materias.df.uba.ar/ft2a2020c2/files/2012/07/Quantum-Zeno-effect.pdf.

Table I publishes seven pulse counts (1, 2, 4, 8, 16, 32, 64) and
two directions of laboratory transition-probability estimates (1→2 and
2→1), **14 genuine published measurement estimates** in all.
They are published summary numbers, **not 14 individual raw measurements**.
The table also provides a simplified ideal projection reference and
the authors' fuller apparatus predictions including finite pulse
duration and optical pumping.

Input: `data/itano1990_pra_table1.json` (a small, directly transcribed
numeric table with DOI, provenance and no copied PDF/figures).
`itano_lab_benchmark.py` evaluates frozen ideal
`P_transition(n) = [1 − cos(pi/n)^n]/2` using
`zeno_temporal_001.py`, then compares with the actual observations and
with the separately reported original paper predictions.

No fit to these values, no filtering, no sample selection or clamping.
For n=64 and 1→2, the published estimate is **−0.006**: that is
a calibration-noise-affected estimator and **not a physically negative
transition probability**. The authors estimate uncertainties of
about 0.02 from calibration scatter. They do not provide a validated
full covariance matrix here; so our RMSE/MAE are descriptive only,
not formal model-selection p-values.

The ideal model should capture the direction of the Zeno trend, but
the full apparatus model may better match the real ion measurement
because our ideal model assumes instantaneous, perfectly nonselective
measurements and ignores optical pumping.

## Lane 2 — Independent future drand choice, blinded software null control

Protocol: `blind_drand_pilot.py` (pure deterministic evaluator, except
for its initial OS CSPRNG draw) and
`drand_pilot/signed_quicknet.mjs` (official pinned signature-verifying
`drand-client@1.4.2`).

1. **EARLY:** generate 256 OS-random bits, choose a drand Quicknet round
   45 rounds after the latest already verified beacon, record the target
   release UTC time, frozen early bits and SHA-256. Publish them into
   an immutable GitHub Actions artifact BEFORE that future round.
2. **LATER:** read exactly the committed future round from Quicknet
   using cryptographic signature verification (BLS) and the pinned
   public key + chain hash, derive all 256 bits without postselection.
3. **TIMESTAMP GATE:** separately query the GitHub artifact creation time
   and require it precede the target round's release by at least 15s.
   Fail closed if this cannot be shown.
4. **RAW TEST:** compare **all** 256 bits, exact two-sided binomial
   under the ideal independent-bit null hypothesis; one nominal
   p<0.05 outlier would never prove information travelled backwards.
   Freeze one test; do not retry/select a favourable seed.

drand documentation: https://docs.drand.love/developer/http-api/
Signature-validating client: https://github.com/drand/drand-client
Quicknet chain hash:
`52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971`.

**Important boundary:** drand is an independent *future random number*
source, but this is a software control, not a physical retrocausal channel
or an independent laboratory receiver. GitHub timestamps are an external
artifact-service witness, not an independent independent experimental custodian.
A later physical experiment would need a separately administered receiver
and externally preregistered blind outcomes.

GitHub workflows: one small offline CI for published lab values and
negative protocol tests, plus an isolated **single trigger on this PR
branch** for the live signed beacon pilot (no permanent schedule).
Untrusted conditions, missing timing proofs or signature errors halt
the blind report; they do not count as science successes.
Artifacts include SHA-256 provenance, full raw comparisons and explicit
`physical_retrocausal_signal_proven=false`; none are promoted to
production JANUS model weights or used as future labels for training.

## Acceptance gates

- DOI/source and 14 table estimates verified against the paper
- Frozen ideal model compared to 1→2 and 2→1 separately
- Published −0.006 preserved exactly, never clamped
- Full-pulse original-paper comparator clearly separated from JANUS model
- No-fit RMSE/MAE and approximate-uncertainty caution
- 256 bits fixed before a future signed beacon; future round immutable
- GitHub artifact uploaded early; independent creation time verified
- No postselection, no retraining, no optional extra trials
- All tests and CI PASS; no physical retrocausality claim
