# JANUS-011B — PRE-DATA FREEZE — 2026-11-10

Research question: Can the published 2026 Qu et al. photonic quantum switch data be independently normalized and its causal inequality reconstructed from all 16 setting/outcome tables, and does that imply any effect on a *precommitted earlier record* without postselection?

Original article DOI: 10.1126/sciadv.aee9271 (Science Advances, 2026-08-07).
Original Dryad dataset DOI: 10.5061/dryad.8kprr4z24 (first publication 2026-06-17). Dataset includes 16 Fig4_input_settingxxxx_vs_probability.csv, plus README.md; first column = 4-bit outcome tuple (a1,a2,b,c), second column experimental conditional probability, third reported SD. Settings are x1,x2,y,z.

Before reading source CSV bytes, protocol is frozen:
1) Require exactly 16 unique files from public Dryad dataset and exactly 16 distinct outcomes (a1,a2,b,c, in that order) per setting (x1,x2,y,z). Binary tuple labeling must be unambiguous; if it is not, FAIL CLOSED rather than adopt a labeling that best reproduces the paper.
2) Verify data normalized by setting, probabilities finite and in [0,1], finite nonnegative SD. Require |sum(P)-1| <= .01 per setting (the .01 is a conservative reporting-rounding tolerance, not a fitted physical parameter). Do NOT silently renormalize. Preserve and disclose per-file sum, missing values, ZIP hash and individual source hashes.
3) Reconstruct, from the entire reported conditional outcome distribution, *exactly* the article's equation (4):

T1 = (1/8) sum_{x1,x2,z in {0,1}} P(b=0, a2=x1 | x1,x2,y=0,z)
T2 = (1/8) sum_{x1,x2,z} P(b=1, a1=x2 | x1,x2,y=0,z)
T3 = (1/4) sum_{y,z} P(b XOR c = y*z | x1=0,x2=0,y,z).
S = T1+T2+T3, fixed causal-order bound S<=7/4.
Frozen report: T1,T2,T3,S, S-1.75, all-normalized diagnostic and source SHA; compare to authors' published rounded T1=.4846 T2=.4895 T3=.8348 S=1.8090±.0024. Differences <=.0005 (aggregate) are compatible with typical display precision but not necessarily proof of exact replication.
4) For each term use **reported per-outcome SD only** for a diagonal-only CONDITIONAL estimate, and report it explicitly UNVERIFIED as a physical uncertainty due to unknown shared-count and normalization correlations. No significance estimated from diagonal-only SD unless full covariance is grounded. Authors quote 24 SD with their uncertainty; that is NOT independently verified merely by reproducing S. Never invent raw counts.
5) Separate fixed analytic models:
   - Quantum switch with coherent control, XZ vs ZX: P(control-minus)=1 for ideal anti-commuting Pauli operations; incoherent classical order mixture gives P(control-minus)=.5. All outcomes retained (no postselection).
   - Explicit pure-ensemble deterministic *nonlinear toy* F(psi)=Kpsi/||Kpsi|| with K=diag(1,1/2); same maximally mixed rho=I/2 is decomposed by Z or X steering, giving P(0)=.5 vs .8. This assumes unphysical ensemble-decomposition dependence and is NOT an established quantum operation. Physical trace-preserving Kraus instrument includes K_success and K_failure, restores unconditional P0=.5, distinguishing postselected artifact from genuine hypothetical deterministic nonlinearity.
   - Standard local CPTP operations, process matrices obey operational no-signalling constraints for earlier recorded marginal under actual independently later distant choices. Neither a causal inequality violation nor a quantum switch implies that older recorded A changed.
6) Early-record test: Dryad CSVs are postselected experimental photon-detection conditional probabilities; they contain no individually externally witnessed, physically early signed A records and no authenticated trial-wise independent later C generation times. Automatically return EARLY_RECORD_CAUSAL_TEST_INELIGIBLE (NOT zero effect proven).
7) This is an already-published historic dataset: independent reproduction is not prospective blinded experiment. Authors note fair-sampling/detection loophole and limitations of spacetime separation. Claim cannot exceed fixed-order inequality only under its assumptions and detected-sample representation.
8) Ji/Lloyd/Wilde PRL 136 230801, DOI 10.1103/znyd-npk5 (published 2026-06-11), concerns *hypothetical* noisy postselected CTC channels. Its capacity bounds are in-model, not an empirically measured backward-in-time channel. Do not label 0.3 fake-signal toy as Ji exact capacity or infer unprovided channel numbers.
9) No retuning after reading Dryad; no changing sealed JANUS 010 or previous 011A; no NAS/containers/QPU use. Raw 16 CSVs are NOT redistributed into repository, only SHA hashes and derived aggregate JSON in artifacts.
