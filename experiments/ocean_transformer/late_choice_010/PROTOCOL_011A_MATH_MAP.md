# JANUS-011A — Mathematical Search Map for Operational Retrocausality

Scientific status: MATHEMATICAL COUNTEREXAMPLES AND POWER CALCULATIONS; NOT a physical discovery or new laboratory data. Frozen script and test examples are exact deterministic operations with a standard-library Python runtime, no quantum computer and no random sampling until desired p-value.

## Question actually answered

Under what additional assumptions can a setting C chosen after an early result A have a detectable effect on the *unconditional, independently signed* record of A? And which tempting experimental signatures can be replicated WITHOUT any information travelling backward in time?

### A. Standard two-qubit Born rule
Bell state (|00> + |11>)/sqrt(2), Alice reads Z. Bob later chooses Z or X. Exact joint distribution:
- C=Z: P(A0,B0)=.5, P(A1,B1)=.5, others 0.
- C=X: all four joint P(A,B)=.25.
Thus P(A0|C=Z)=P(A0|C=X)=.5, NO operational signal.
Postselect B0: P(A0|B0,C=Z)=1 but P(A0|B0,C=X)=.5. This conditional difference CANNOT be read from Alice's early records without future B data.

Proof: trace preservation: Tr_B[(I tensor E_C)(rho_AB)] = Tr_B(rho_AB) for any local CPTP E_C on B, no classical communication. Indefinite quantum causal order / quantum switch is not itself backwards signalling (see citation).

### B. Nonlinear/postselected P-CTC LIKE toy
Early A and later C independent fair bits. Later success S has P(S|A=C)=1 and P(S|A!=C)=r. For accepted runs, P(A=C|S)=1/(1+r) and selected apparent conditional difference is (1-r)/(1+r), while acceptance fraction is (1+r)/2. For r=.05: selected difference .9047619 and acceptance .525; full early record still P(A|C)=.5. Retrospective postselection cannot transmit a bit to the early observer, unless a genuinely pre-existing success-flag mechanism exists beyond ordinary quantum theory. A theoretical P-CTC map is not physically established by selecting runs on an ordinary CPU.

### C. Ontological retrocausality that gives no channel
Formally assume future C controls hidden past lambda with 10% mismatch, so I(lambda;C)=1-H2(.1)~.5310044 bits. Make accessible early A=lambda XOR R for a truly independent fair hidden mask R. Then I(A;C)=0 exactly, even though latent lambda is mathematically future-dependent by assumption. A/B outcome-only data can never distinguish this particular hidden construction from standard operational no signalling. No claim the future truly influences hidden variables in nature.

### D. Classical forward-time false positive
Let a hidden earlier U be fair. Early A=U. Later C copies U with probability 0.55 and flips otherwise. An uninformed analyst gets P(A1|C1)-P(A1|C0)=.10, a huge apparent backward signalling effect. A randomized true do(C) intervention breaks U->C, and the effect vanishes: P(A1|do(C1))-P(A1|do(C0))=0. Thus the critical experiment is an *after-A genuinely independent C*, not a mere timestamp or PRNG block.

### E. Operational signal power map
Define delta=P(A1|do(C1))-P(A1|do(C0)). Hypothetical p=.5 +/- delta/2; two balanced independent Bernoulli samples; alpha 0.001 two-sided, 90% nominal power. Gaussian total N ~ (z_(1-alpha/2)+z_power)^2 / delta^2. This is a power approximation, NOT an exact Fisher calculation or physically measured result. For the PREVIOUSLY SEALED physical JANUS-010 N=16,384, a delta around .0357 (3.57 percentage points) is the approximate 90%-power threshold under ideal iid conditions. For delta=.01 N about 209,000; delta=.04 N around 13,100. Smaller physical biases, drift, lost events, extra looks or multiple variants would require revised and independently validated sample sizing. Do not change sealed experiment thresholds on the basis of these power estimates.

## Where to look, mathematically — admission hierarchy

1. **Only genuinely distinguishing operational target:** Precommitted early A, then genuinely newly generated independent physical C, independently certified clock, no photons/outcome-conditioned survival filter, and in addition a reproducible nonzero **unconditional** delta between future interventions do(C).
2. **Potential new physics, not physically shown:** A process that violates standard trace-preserving linear quantum dynamics / accesses nonlinearity or valid externally heralded early success without post hoc selection. Until real physical apparatus and selection independent evidence exist this is toy mathematics, not an accessible backwards channel.
3. **Retrocausal hidden variable interpretations:** Can fit same operational predictions as standard quantum mechanics. A mathematical hidden earlier lambda depending on future settings is not by itself a distinguishing experimental prediction; constraints that yield a different observable are necessary.
4. **Postselected quantum eraser/P-CTC simulations:** Produces apparent future-dependent conditional correlations but NOT readable earlier signals. Reject as evidence if early recorder has no success flag.
5. **Shared seeds, leaks and event filters:** Can create spurious early/future associations of any specified sign and size. Test by lab independence / randomized physical do(C) and preserve all trials.

## Relevant peer-reviewed / scholarly context

- Stanford Encyclopedia of Philosophy: https://plato.stanford.edu/archives/win2025/entries/qm-retrocausality/
- Blasiak et al., Comparing the cost of violating causal assumptions in Bell experiments (2024): https://pubmed.ncbi.nlm.nih.gov/38281717/
- Delayed choice experiments mathematical equivalence (2024): https://repository.tudelft.nl/record/uuid:cf475a74-24fe-4f30-b133-c8bec3155acb
- Lloyd et al., Closed Timelike Curves via Postselection: https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.106.040403
- Causal nonseparability and quantum switch physical limits: https://doi.org/10.1088/1367-2630/17/10/102001
- Experimental aspects indefinite causal order (2024): https://www.nature.com/articles/s42254-024-00739-8

No NAS access, no hardware, no external lab measurements and no alteration to sealed JANUS-PHYSICAL-LATE-CHOICE-010. Append-only provenance and falsifiability map to be recorded separately from physical evidence.
