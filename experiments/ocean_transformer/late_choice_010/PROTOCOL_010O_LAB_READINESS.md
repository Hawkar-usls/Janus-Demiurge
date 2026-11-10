# JANUS-010O — hardware-ready physical late-choice gate (NO PHYSICAL RUN CLAIMED)

**Scope:** engineering readiness and independent-lab witness protocol supporting the EXISTING frozen JANUS-PHYSICAL-LATE-CHOICE-010 (N=16384, two-sided Fisher exact alpha=0.001, no postselection). JANUS-010O does NOT replace/redefine that scientific protocol and is NOT a simulation claimed as physical evidence.

## Required physical chain

1. Produce a pair of entangled photons / qubits in an experimentally audited source, with heralded shot ID. Alice's readout gate and Bob's delayed partner gate are defined before acquisition; use all attempted heralded shots, including detector no-click, readout failures and invalids as predeclared missing/failure records. No recoding missing data as 0 or removing it.
2. Alice performs an EARLY raw A measurement. A separate, independently operated recorder writes the A result, shot ID, physical timestamp, uncertainty and monotonic sequence number into a non-rewriteable custody medium, and attests that it was irreversibly committed before physical generation of C. A timestamp/JSON string produced later is NOT independent custody. The recorder must not send A or derived data to QRNG or Bob.
3. An independent QRNG physically GENERATES setting C only AFTER A has been recorded and committed. It may not reveal a preexisting random bit from an earlier seed, later-read stored entropy, a drand block or a precalculated schedule. Verify QRNG source/entropy timing, firmware, I/O isolation, latch/actuation and absence of classical A->C feedback.
4. C controls a PHYSICAL measurement switch in Bob's analyzer (e.g., EOM/Pockels cell) after entropy generation and before delayed Bob measurement B. The partner must remain a coherent quantum system until B. If optical delay line is used, audit loss, coherence, detector dead-time and setting-dependent survival; long fibers may make this impractical without quantum memory.
5. An independent calibration connects Alice timestamp counter, QRNG choice-generation counter, actual Bob basis-latch counter and Bob detector counter into a common physical timeline. Measure offset, drift, cable delay, propagation latency, detector latency, QRNG entropy-generation-to-latch delay and uncertainty distribution. Neither fitted Bell coincidences nor user-typed clock offsets are admissible as physical calibration.
6. Independent custodian validates hardware public keys, firmware manifest, raw TDC/oscilloscope calibration, all early WORM captures and corresponding later records. A self-signed value is not independent. A valid cryptographic signature alone does NOT prove that a device captured a truly physical choice when claimed.
7. For EVERY preregistered trial require robust time inequalities in the same already independently calibrated physical timebase:
   upper(A_commit) < lower(C_entropy_generation),
   upper(C_entropy_generation) < lower(C_basis_latch),
   upper(C_basis_latch) < lower(B_detection).
   Absence of any term, unclear common epoch or overlapping uncertainty => NO PHYSICAL CHRONOLOGY PASS. These four stages are stricter than merely displaying t_A<t_C<t_B.
8. Also audit shielding, classical paths, RNG setting independence, trial synchronization, source drift, hardware failures, excluded-shot handling, absence of setting-dependent survival and counterfactual null controls. The physical no-signalling null and the local Bell correlations must be kept separate.
9. Freeze the independent lab proposal, public key provenance, trial schedule, equipment and calibrations with a third party BEFORE taking the first physical candidate shot. No repeated tests until a desirable p, no after-the-fact model changes, no software-generated "evidence".

## Mathematical distinction

No-signalling in ordinary quantum mechanics:
Tr_B[(I tensor E_C)(rho_AB)] = Tr_B(rho_AB) for trace-preserving local operations E_C.

Postselecting on a B measurement can create an apparent A/C dependence even when A and C were independent. Only unconditional A by physically late C, with all shots included and fully audited timing/custody, could be a meaningful challenge to the no-signalling null. An unexplained statistical deviation would still need independent systematic-error elimination and new independent replication, not instant proof of backwards communication.

## Required apparatus — conceptual, NOT physically available to this run

Entangled partner source and herald; photon or stored-qubit delay preserving coherence until after C; Alice fast measurement and independent early WORM/FPGA witness; dedicated QRNG with evidence of entropy-generation time AFTER A; actual fast basis actuator; Bob detector, shielded data paths; time-to-digital hardware or synchronized clocks with independently calibrated absolute epoch, uncertainties and reference timing; instrument logs signed by a lab not controlled by the same operator.

The user's ordinary ESP32 or a GitHub Actions runner cannot, by itself, certify nanosecond-level inter-laboratory causal ordering or quantum entanglement. Simulated timestamp rows and software-internal random numbers are engineering tests only.

## Engineering acceptance

JANUS-010O readiness parser audits record fields and chronological uncertainty envelopes but MUST ALWAYS report PHYSICAL_ORIGIN_UNVERIFIED and NO_PHYSICAL_TRIALS_OBSERVED in default CI. User-provided declarations, synthetic source files or even internally generated signatures are not sufficient independent custody. An actual 010 physical experiment remains BLOCKED without externally controlled hardware, independently authenticated timing and separate physical witness.

**No changes** to frozen JANUS-PHYSICAL-LATE-CHOICE-010, no NAS/ESP32 hardware interaction, no QPU allocation or external lab operation were made here.
