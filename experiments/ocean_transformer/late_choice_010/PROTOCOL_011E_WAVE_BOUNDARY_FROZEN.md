# JANUS-011E · Physics-law-first boundary falsification · FREEZE BEFORE FIRST CI
Date: 2026-11-10. Scope: exact analytical 3+1D massless scalar wave Green functions, an electromagnetic *potential* analogue away from the source. NOT a verified quantum/EM experiment or a physical backwards channel.

## Research question
Do established locally time-reversal-invariant field equations, without an independently assumed future boundary, **derive** a measurable change in an already recorded earlier observable when a future choice C is physically created later?

## Fixed independent physical law
For a scalar field in flat 3+1 dimensions, \(\Box\phi=j\), \(\Box=c^{-2}\partial_t^2-\nabla^2\). With a point source at r=0 and r>0:

\[
G_{\rm ret}(t,r)=\frac{\delta(t-r/c)}{4\pi r},\quad
G_{\rm adv}(t,r)=\frac{\delta(t+r/c)}{4\pi r}.
\]

Both are distributional fundamental solutions of the SAME differential operator. So \(G_\lambda=(1-\lambda)G_{\rm ret}+\lambda G_{\rm adv}\) is also a fundamental solution for ANY \(0\le\lambda\le1\), while \(G_{\rm adv}-G_{\rm ret}\) solves the homogeneous field equation in the distributional sense. The PDE alone **does not select \(\lambda\)**; extra radiation/initial/final/absorber boundary data are necessary. This is an established property of wave equations, not a JANUS discovery. Do not conflate *representation* in terms of an advanced Green function with actual backwards operational signalling.

## Frozen numerical model
Normalize the geometric factor away: \(Y_C(t)=4\pi r\phi_C(t,r)\). Fix:
- Time is in arbitrary integer simulation steps, c=1 distance/time unit.
- Physical source/choice location x=0, receiver radius r=5 => travel time τ=5 simulation steps.
- A single later externally selected *model* binary C in {0,1}; choice/source time t0=16. **No actually late physical QRNG exists in this simulation**.
- Source input \(s_C(t)=C f(t-16)\), with \(f(0)=1,f(1)=1/2,f(2)=1/4\), zero at all other times; source never emits prior to late choice time 16.
- Exact normalized response \(Y_{\lambda,C}(t)=(1-\lambda)s_C(t-5)+\lambda s_C(t+5)\).
- Read early model receiver field at t_early=11, five steps BEFORE future choice at t=16, over complete t=0..30 traces, no coincidence/postselection/event removal.
- Compare three **predeclared** not fitted boundary cases λ=0 retarded, λ=1/2 time-symmetric, λ=1 advanced; "absorber-cancelled" control equals G_ret by an explicitly ADDED homogeneous compensator, NOT a derived Wheeler–Feynman absorber law.
- Predictions on model early contrast \(\Delta_{\rm early}=Y_{\lambda,1}(11)-Y_{\lambda,0}(11)\): λ=0 =>0, λ=1/2=>1/2, λ=1=>1. Late retarded-only receiver field response at t=21 =>1; advanced-only 0. These are units of normalized amplitude, NOT probabilities or measured bits.
- The absence of a physical derivation for λ is an explicit **FAIL** of goal to derive retro-signalling solely from a source-local differential equation. The advanced solution needs an *extra* future/global boundary.
- A forward-only chronological recorder stores an independent early noise baseline A=f(U) before C exists; it cannot use \(s_C(t+5)\) without future input. Label any offline "early" trace calculated after C as a **future-informed reconstruction**, never a physically witnessed past observation.

## False-positive control
Apply a five-sample centered moving average to the raw future source sample. It produces apparent source evidence as early as t=14 even though the source is zero before t=16, since the *algorithm reads future samples*. Compare to the purely causal five-sample trailing moving average, which MUST have zero output before t=16. A zero-phase/symmetric digital filter is computational look-ahead, not a future-to-past physical process.

## Scientific decisions frozen before first 011E results
1. All raw simulation timestamps included (0..30) and both C interventions; no selecting winning C or a source subset.
2. Verify analytically that G_ret, G_adv and any convex mix solve same wave differential operator (distributional identity, not a numeric PDE solver claim).
3. Report early/future response for λ=0,.5,1 and absorber-compensated scenario, the centered-versus-causal filtering artifact and the independent early recorder control.
4. Report **source law alone fails to identify an advanced fraction**. λ=.5 is NOT predicted by the PDE or verified as the universe's boundary.
5. No new physical dataset or NIST timing metrology in 011E; zero experimental physical trials. No inference of retrocausality on arbitrary simulated amplitudes.
6. Independent physically testable implication only IF a physically justified advanced boundary is separately given: before late independent source at t0, a receiver at r would exhibit an early precursor near t0-r/c. Ordinary retarded solution gives zero before source. This is a *conditional hypothesis*, not a derived physical prediction from the PDE alone. Energy conservation, absorber response, radiation condition, apparatus timebase and causality must be checked in an actual lab before elevating it.
7. Original sealed 010 protocol, NIST study, JANUS-011A/B/C/D, NAS, containers and QPU MUST remain unchanged.

## Sources and limitations
- Wheeler & Feynman, *Interaction with the Absorber as the Mechanism of Radiation*, Rev. Mod. Phys. 17, 157 (1945), DOI 10.1103/RevModPhys.17.157.
- Wheeler & Feynman, *Classical Electrodynamics in Terms of Direct Interparticle Action*, Rev. Mod. Phys. 21, 425 (1949), DOI 10.1103/RevModPhys.21.425.
- Stanford Encyclopedia of Philosophy, *Causation in Physics*, https://seop.illc.uva.nl/entries/causation-physics/ — retarded and advanced Green representations do not alone prove a causal direction.
- Leifer & Pusey, *Is a time symmetric interpretation of quantum theory possible without retrocausality?*, Proc. R. Soc. A 473 (2017), DOI 10.1098/rspa.2016.0607. Ontological retrocausality is not the same as a backwards communicable bit.

This Green-function toy is a **classical linear wave-equation test**. It is not a derivation of a nonlinear quantum CTC, Deutsch postulate, Ji–Lloyd–Wilde channel, or an operational retrocausal mechanism.
