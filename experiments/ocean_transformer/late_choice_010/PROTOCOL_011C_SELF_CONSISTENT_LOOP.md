# JANUS-011C — Exact cyclic time-loop toy, and the causal provenance no-go

Date: 2026-11-10. **Theoretical research only**. Distinguish (a) mathematical consistency of a future-dependent distribution, (b) a physical mechanism for backwards flow, and (c) experimentally observable, independently witnessed retrocausal signalling. Only (a) is constructed here. It is **not** Deutsch's actual quantum CTC circuit or Ji–Lloyd–Wilde's postselected quantum CTC capacity theorem.

## Exact loop construction

Binary earlier record A, later independently chosen binary setting C, hypothesized feedback-loop state L. The loop transition conditional on C is a row-stochastic Markov kernel

[
 T_C = \begin{pmatrix}1-u_C&u_C\\v_C&1-v_C\end{pmatrix}
]

and self-consistency imposes `pi_C T_C=pi_C`. For strictly positive `u_C,v_C`, the unique stationary distribution is `pi_C=(v_C/(u_C+v_C),u_C/(u_C+v_C))`. Let the early reported A be L.

Fix `(u0,v0)=(1/5,3/10)` and `(u1,v1)=(3/10,1/5)`. Then `P(A=1|do C=0)=2/5`, `P(A=1|do C=1)=3/5`; `delta=1/5`. All transition rows and stationary probabilities are normalized and nonnegative, both outcomes have nonzero probability, and no sample is removed. With uniform independent C this is a symmetric binary channel with Shannon mutual information `1-H2(2/5)=0.02904940554533142` bits/use. **This is mathematical capacity for a noncausal graph admitted as an assumption, not a physical retrocausal channel.**

## Noise perturbation

Suppose the actuator's applied choice flips the intended C with independent probability epsilon, so the loop transition is a convex mixture of both original kernels:

[
T_{C,\epsilon}=(1-\epsilon)T_C+\epsilon T_{1-C}.
]

Because each `u_C+v_C=1/2`, the stationary probabilities are `P(A=1|C=0)=0.4+0.2epsilon`, `P(A=1|C=1)=0.6-0.2epsilon`, `delta=0.2(1-2epsilon)`, and the symmetric-channel capacity is `1-H2(0.4+0.2epsilon)`. At epsilon = 0, 0.1, 0.25, 0.5 the exact delta is 0.20, 0.16, 0.10, 0.00, respectively. Noise cannot convert mathematical assumptions into physical evidence.

## Why normalization and full outcome accounting are insufficient

Let `u0=q/2, v0=(1-q)/2`, `u1=(1-q)/2, v1=q/2`, for any `0<q<1`. All rows remain strictly positive and stationary states unique, while `P(A=1|C=0)=q`, `P(A=1|C=1)=1-q`. Thus the toy capacity `1-H2(q)` ranges continuously from **0** at q=1/2 to **arbitrarily close to 1 bit/use** as q approaches zero, all without postselection.

This freedom is the key falsification result: a model chosen solely to satisfy normalization, fixed-point self-consistency and a nonzero early/future statistical contrast does not select real world physics. A new, independently motivated physical field/dynamical equation would need to specify q or a specific transition kernel with additional testable consequences. Hand-selecting the kernel after observing a desired retro effect is not evidence.

## Genuine completely positive trace-preserving quantum extension (still only a toy)

The 2-state transition matrix can be embedded in an ordinary quantum *entanglement-breaking* CPTP map by using four Kraus operators:
\[
K_{j,i}=\sqrt{T_C[i,j]}\, |j\rangle\langle i|,
\qquad
\mathcal E_C(\rho)=\sum_{i,j} K_{j,i}\rho K_{j,i}^{\dagger}.
\]
Since each row of T_C sums to one, \(\sum_{i,j}K_{j,i}^{\dagger}K_{j,i}=I\). The map is completely positive because it has an explicit Kraus decomposition. It destroys off-diagonal coherence but preserves trace and **all** outcome contributions.

For the SAME past state \(\rho_{early}=I/2\), an ordinary later application of \(\mathcal E_0\) produces a final \(P(1)=0.45\), while \(\mathcal E_1\) produces final \(P(1)=0.55\). This 10-percentage-point difference is a permissible **later output response to a later input**, not backwards signalling: the shared previously committed early probability remains 0.5 under both settings.

Only by imposing the *additional global retro boundary* \(\rho_{early,C}=\mathcal E_C(\rho_{early,C})\), before C is physically generated, does the early probability become 0.4 versus 0.6. Therefore a completely legitimate local quantum channel does not by itself cause backwards information transfer. The entire retrocausal assumption is in the nonstandard boundary condition linking the late map to the earlier input state.

This is a **Kraus-lift of a classical Markov loop**, not an experimentally realized Deutsch quantum CTC circuit; the physical global boundary was not independently derived or observed.

## Forward-time control / no-go within ordinary dynamics

If there is no future-to-past causal edge, A is committed at t1 as `A=f(U)` from pre-existing variables U; C is genuinely freely generated at t2>t1 with independent source V and does not feed into A. For any intervention `do(C=c)`,

[
P(A=a\mid do(C=c))=\sum_u P(U=u)1[f(u)=a],
]

independent of c. For the balanced example A=U~Bernoulli(1/2), both interventions yield 1/2 and delta=0. Quantum local CPTP operations likewise preserve the earlier unconditioned marginal by trace preservation.

A normal CPU evaluating `pi_C` **after** C exists cannot alter the independently witnessed file A that was sealed earlier: if the algorithm requires c to emit A at t1, then either c was already available, the output was not actually committed at t1, or a new physical backwards channel was *assumed*. There is no independent demonstration of such a channel in JANUS-011C.

## Power planning, not experimental detection

For a genuinely physical delta of 0.2 across equally randomized C groups, an approximate independent balanced Bernoulli normal test with two-sided alpha .001 and power .9 would require around 523 trials in total. This is a planning calculation only; 0.2 was **built into the toy model**. Existing sealed JANUS physical-010 still fixes 16,384 shots and its preregistered analysis; do not alter any previously frozen evidence.

## Literature relation, precise limits

- David Deutsch, *Quantum mechanics near closed timelike lines*, Phys. Rev. D 44, 3197 (1991), DOI https://doi.org/10.1103/PhysRevD.44.3197. Uses quantum self-consistency for hypothesized CTCs. JANUS-011C uses a classical 2-state Markov fixed-point **analogy**, not Deutsch's quantum CTC map.
- Kaiyuan Ji, Seth Lloyd, Mark M. Wilde, *Retrocausal Capacity of a Quantum Channel: Communicating through Noisy Closed Timelike Curves*, Phys. Rev. Lett. 136, 230801 (2026), DOI https://doi.org/10.1103/znyd-npk5. Quantifies capacities for mathematical **postselected noisy CTC quantum channels**. The binary Shannon capacity computed by JANUS-011C is **not** their theorem, and the map is not a physical P-CTC device.

## Formal acceptance gates

- Exact probability normalization, uniqueness of stationary points, positivity and nonselection PASS.
- Mathematical intervention dependence within the posited loop PASS.
- Independence of causal assumption from stipulated backwards edge FAIL: loop carries the dependence by construction.
- Forward-timeline execution with early immutable A and later independent C producing measurable change FAIL.
- Physical mechanism to return a newly generated C to the past UNKNOWN / NOT PRESENT.
- Physical independent replication: zero experimental trials; **no retrospective signalling demonstrated**.
- No changes to original sealed JANUS-010, NIST calibrations, NAS, connected hardware, or prior scientific JSON results.

Store source code, CI, SHA and append-only registry with `THEORETICAL_TOY_ONLY` status. Do not merge as proven physical finding.
