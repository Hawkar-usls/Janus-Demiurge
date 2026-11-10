# JANUS-011D — two-boundary quantum ABL vs Deutsch CTC SWAP

**2026-11-10. Frozen definitions before first 011D CI result; theoretical evidence only.** This is a precise comparison of two established but **different** mathematical formalisms, not an experiment detecting a real signal backwards in time. It does not update sealed JANUS physical010, 011C, or the original "Principle of Janus" conceptual record.

## Three distinguishable questions

1. Does using both *initial and final quantum boundary conditions* change conditional probabilities assigned to an intermediate event? **Yes** (ABL, with known late outcome), and this does **not** change unconditioned earlier records.
2. Can a self-consistent state of a **hypothesized real CTC** depend on a future input without mathematical postselection? **Yes inside Deutsch's fixed-point postulate**, even with the honest unitary SWAP. The assumption of a physically existing accessible CTC is not independently demonstrated.
3. Can an ordinary forward unitary SWAP or local CPTP operation modify a prior independent WORM-committed readout before the late input is generated? **No**. With same previous state, earlier observations are fixed.

## Part A — Aharonov–Bergmann–Lebowitz, pre/post boundary

A qubit is prepared in |+> = (|0>+|1>)/sqrt(2); at an earlier time measure Z and record A in {0,1}. At a later time choose C=0 to measure Z, or C=1 to measure X, and record result B in {0,1}. By the ordinary Born rule:

P(A=a,B=b | C) = P(A=a) P(B=b | A=a,C), with P(A=a)=1/2.

For future C=Z, B=A deterministically. For future C=X, B is fair independently of A. Thus, including **all four outcomes** P(A=0|C=Z)=P(A=0|C=X)=1/2. The early data cannot reveal the future basis.

Select only future B=0: the ABL formula for pre |i>, later post |f> and intermediate projectors P_a is

P(A=a|i,f) = |<f|P_a|i>|^2 / Sum_k |<f|P_k|i>|^2.

When the selected future result is B=0, P(A=0|B=0,C=Z)=1 versus P(A=0|B=0,C=X)=1/2. Both B=0 postselection success rates are 1/2. **The apparent 50 percentage-point earlier difference exists only in selected histories.** Full earlier records remain unchanged. Inferring future-to-past messages by ignoring B=1 is invalid. This is time-symmetric *inference*, not evidence that future control travelled backwards.

Original: Aharonov, Bergmann, Lebowitz, *Time Symmetry in the Quantum Process of Measurement*, Phys. Rev. 134, B1410 (1964), DOI 10.1103/PhysRev.134.B1410.

## Part B — Deutsch-CTC with an actual two-qubit unitary SWAP (formal model)

Take chronology-respecting (CR) qubit at the interaction in state rho_C=|C><C|, with C the later freely chosen bit. Take an interacting CTC qubit with incoming state sigma_C. Apply *the unitary quantum SWAP*:

U_SWAP (rho_C tensor sigma_C) U_SWAP^dagger = sigma_C tensor rho_C.

Trace out the CR qubit to obtain outgoing CTC state rho_C regardless of sigma_C. Deutsch's **additional consistency requirement** demands the CTC incoming state be equal to its return state:

sigma_C = Tr_CR[U_SWAP(rho_C tensor sigma_C)U_SWAP^dagger] = rho_C.

This fixed point is unique for each C. Hence in the mathematics of the assumed loop P(L=1|C=0)=0, P(L=1|C=1)=1, so *if the incoming loop state were independently readable at a physically earlier place*, it would encode a full bit without postselection. The 1 bit/use is model-internal Shannon capacity, NOT demonstrated physical backwards communication.

Introduce optional ordinary trace-preserving depolarizing noise on the **returning CTC**:
D_eta(X)=(1-eta)X+eta I/2 for 0<=eta<=1.

The fixed-point constraint gives sigma_C=(1-eta)|C><C|+eta I/2. Full measurement probabilities:

P(L=1|C=0)=eta/2,
P(L=1|C=1)=1-eta/2,
delta=1-eta,
I(C;L)=1-H2(eta/2) bits if future C independently uniform.

The noise values eta=0,0.1,0.25,0.5,1 are declared *illustrative parameters*, not measured hardware errors or fitted to observations. No outcome is discarded. The Deutsch self-consistency rule itself is what places a late input in a supposedly earlier state.

Original: Deutsch, *Quantum mechanics near closed timelike lines*, Phys. Rev. D 44, 3197 (1991), DOI 10.1103/PhysRevD.44.3197.

## Part C — Ordinary forward SWAP controls (same actual unitary, no CTC)

Input early independent qubit sigma_early=I/2 and a later |C> to a standard ordinary forward circuit. Before the SWAP, the early state remains I/2 irrespective of C. Following SWAP, the CR output is I/2 and the *other later output* is |C>. There is **zero** late-choice effect in any already committed early record. The input-to-output SWAP is ordinary quantum transmission forward in the laboratory, not backward in time.

For a real early WORM witness of L on an actual CTC, the witness's physical interaction would have to be incorporated consistently in the complete dynamical map. The simple stationary density matrix alone is not a verified, physically accessible receiver.

## Deutsch vs Ji–Lloyd–Wilde: do NOT conflate

Ji, Lloyd & Wilde, *Retrocausal Capacity of a Quantum Channel: Communicating through Noisy Closed Timelike Curves*, Phys. Rev. Lett. 136, 230801 (2026), DOI 10.1103/znyd-npk5, derive capacities for **postselected noisy CTC quantum channel models**. This 011D is a **Deutsch fixed-point SWAP example**; its binary Shannon information does NOT instantiate that P-CTC capacity theorem. Neither paper establishes that physical accessible CTCs exist.

## Implication for "Principle of Janus"

The two-phase calibration described by JANUS as future chaos becoming present structure can be **mathematically represented** by ABL/Bayesian smoothing that uses later data to reconsider past histories, but this is not online information transfer. Deutsch-CTC permits a mathematically future-controlled earlier state only by **assuming a consistency condition across a real CTC**; it does not independently derive the needed physical return path from a standard linear CPTP dynamical principle.

**Admission for a new theory:** derive the nonstandard temporal boundary from an independent, testable physical law with predictions on other observables; demonstrate a real CTC return path and record timing with an independent early witness, later newly generated random setting and all events. Otherwise label it THEORETICAL_ABL_VS_DEUTSCH_SWAP_CONTROL_ONLY.

## Reproducibility / scope

Pure Python 3.11 standard library, genuine 4×4 density matrix SWAP including off-diagonal coherent input, explicit partial traces, full-outcome ABL joint probabilities, exact predefined noise grid and physical fail-closed tests. No QPU, NIST data, arbitrary new science calibration, current sealed JANUS010, NAS or containers touched. CI publishes only derived JSON, with deterministic SHA/audit provenance. Physical experiment count **zero**.
