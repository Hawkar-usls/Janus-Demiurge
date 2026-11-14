# JANUS-010M — Independent Causal Falsification: preread methodology

## Original data and scope
Original historical ETH Zurich Storz et al. Bell dataset: 1,048,576 physical
trials, four columns (Alice basis a, result A, Bob basis b, result B).
Storz et al., Nature 617, 265–270 (2023), DOI 10.1038/s41586-023-05885-0.
Data DOI: 10.3929/ethz-b-000624026.
ZIP SHA256: 2d39d1b6898480d3de0134e2d55ac3faee87af32c8db5bc6fdf6fa6997296909.

This complete archive was *already viewed* by earlier JANUS-010C, so
the 010M chronological validation split is a computational model check,
NOT an independent blinded physical experiment. No per-shot timestamps
are included and no genuinely late choice after committed early outcome
is evidenced by the four columns.

## Three models and mathematical results

M0 (standard QM no-signalling): applying any local trace-preserving
quantum operation E_C at Bob leaves Alice's reduced density operator
unchanged:

rho_A(C) = Tr_B[(I tensor E_C)(rho_AB)] = Tr_B(rho_AB).

Thus the unconditional probability for an Alice result, at fixed Alice
setting, is independent of Bob's later or spacelike setting, assuming
standard quantum operations and no communication. This does NOT deny
the Bell violation observed in joint correlations.

Mpost (postselection artifact): with independent uniformly random A,C
and B=A XOR C, A is independent of C before conditioning; conditioning
on B=0 forces A=C and yields a perfect *false* signal. This is a classical
proof by counterexample; ETH remote readout selection is displayed ONLY
as a diagnostic, never as a valid primary inference.

Mjanus (exploratory statistical proxy): permit an extra remote-setting
dependence in local results. Predeclared effect size for relevance is
absolute probability difference 0.01. ETH remote setting is NOT a
certified physically later free choice after a signed earlier A.
Rejecting M0 here would not demonstrate future-to-past communication.

## Frozen protocol before this 010M real-data replay

- Include ALL 1,048,576 physical source trials; verify complete exact
  original source hashes and four-column formats; no omitted rows.
- Train model parameters on the FIRST 524,288 recorded trial rows.
  Validation is the LAST 524,288 source rows. Neither block was never
  seen in previous JANUS-010C analyses, so the split cannot be called
  an external holdout.
- M0 predicts local +1 by own setting only; Mjanus predicts local +1
  by own and remote setting; both fitted with fixed Beta(1/2,1/2)
  Jeffreys smoothing from first half. Report fixed validation
  log likelihood difference and predictive bits per trial for each wing.
- Exactly FOUR no-signalling marginal comparisons on validation
  (Alice own 0/1; Bob own 0/1), two-sided pooled z scores and four-test
  Holm familywise alpha=0.001. Note asymptotic iid assumptions.
- Retain 4096-consecutive-trial validation block diagnostics; block-z
  is only descriptive without independently established block independence.
- For POSTSELECTION ONLY, subset by positive readout at the OTHER wing
  and display the remote-setting association; NEVER use selected events
  to fit the main two models or calculate primary p-values.
- The 0.01 hypothesis magnitude and the split are design choices, not
  measured constants. Do not optimize any rule after seeing 010M outcomes.
- No source external clock, physically late choice or lab witness exists
  in this archive. No QPU charge, NAS edit or modification to sealed
  JANUS-PHYSICAL-010 is permitted.

## Scientific admission

Even a statistically stronger predictive model or a significant p-value
cannot prove retrocausality from these *spacelike* Bell measurements.
The independent prospective 010 physical late-choice protocol requires
an after-A generated free QRNG choice, timebase with uncertainties, an
external signed early readout, no postselection, and independent replication.
Until then, status stays ARCHIVAL_REAL_PHYSICS_FALSIFICATION_DIAGNOSTIC_ONLY.
