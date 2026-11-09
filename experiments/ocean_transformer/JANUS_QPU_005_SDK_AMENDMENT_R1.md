# JANUS-RETRO-PHYSICAL-005 — SDK / hardware admission amendment R1
Date: 2026-11-09. Status: **DRAFT / OFFLINE ADMISSION ONLY / NO QPU RUN**.

## Non-retroactive science and provenance

The originally preregistered experimental protocol **is not modified**:
- Original experiment: JANUS-RETRO-PHYSICAL-005
- Original PR #485: https://github.com/Hawkar-usls/Janus-Demiurge/pull/485
- Original merge commit: \`8fa54f25c5bf3f5593db6b7ddc2a3a8da5f78f19\`
- Original Meta Registry PR #475: https://github.com/Hawkar-usls/janus-meta-registry/pull/475
- Original registration: \`data/experiments/JANUS-RETRO-PHYSICAL-005-PREREG-2026-11-09-v1.json\`
- No change to \`physical_qpu_005_protocol.py\`, \`physical_qpu_005_ibm.py\`, the original analysis, shot count, alpha, or past preregistration record.
- Experimental results, simulation data, and an operational quantum communication channel are **not** claimed.

This amendment modifies only **launch administration and an isolated offline admission test**.
Any future change to the circuit, sampler selection, result decoder or analysis
must be separately preregistered **before** execution; its evidence must not
be relabeled as an original 005 result.

## SDK compatibility (no IBM API calls)

\`qiskit==2.6.2\` and \`qiskit-ibm-runtime==0.50.0\` are installed in the
isolated CI job. Run the original 11 tests with the **real IBM client package
installed**, then check the frozen circuit structure, the runtime imports,
and absence-of-credentials submit rejection. The audit **must not initialize
QiskitRuntimeService**, call a provider backend, or execute Sampler.run().

In Runtime 0.50.0 the original adapter's \`SamplerV2\` import remains available
but has been deprecated. IBM recommends the client-side
\`qiskit_ibm_runtime.executor_sampler.Sampler\`. We **do not silently switch**
this experiment's sampler, as that could change compilation or interpretation.
The offline pass does not establish live-device compatibility. It does not
validate which backend is accessible, actual \`if_else\` ISA transpilation on
that backend, mid-circuit measurement timing, or the decoded live bit arrays.

Official IBM references:
- https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/release-notes
- https://quantum.cloud.ibm.com/docs/en/guides/execute-dynamic-circuits
- https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/0.50/qiskit-runtime-service

## Manual hardware dispatch amendments and limitations

The existing manual workflow has been **proposed** to require, in addition to
the original two approval inputs:
1. A \`workflow_dispatch\` only, on \`main\`, by actor \`Hawkar-usls\`;
   rerunning a failed/successful workflow attempt is rejected;
2. The exact original preregistered plan SHA-256 pasted at submission;
3. A default-deny repository/environment variable
   \`JANUS_QPU005_RELEASE_GATE=APPROVE_QPU005_R1\`;
4. An environment named \`janus-qpu005-approval\`. **Before merging** this
   amendment, create and configure this environment with required human
   reviewers, and store IBM Quantum credentials as environment secrets.
   GitHub creating an environment name alone **does not enable reviews**;
5. Existing serial concurrency, private credentials and one 4096-shot
   submission *per successfully admitted dispatch* remain in place.

**Remaining limits:** repeated **new** manual \`workflow_dispatch\` calls are
not globally idempotent; actor, environment, and SHA checks are not a
cryptographically enforced one-job ledger. An accepted remote submission can
occur even if the GitHub runner crashes before persisting the provider job ID.
The operator must disable the release gate immediately after submission and
verify its unique provider job ID before any new attempt. Do not treat a retry
as free or safe. The configured environment may require a specific GitHub plan
or repository settings. An Open Plan assertion in the form is **not** proof
of the provider's account/billing tier. If the gate/review configuration is
unknown, the correct disposition is **NO QPU SUBMISSION**.

## Evidence and acceptance criteria

The separate offline CI produces \`qpu005_sdk_offline_admission_r1.json\`
with baseline source hashes, versions, preregistered plan SHA, fail-closed
credentials test, static workflow gate audit and explicit \`qpu_time_used=false\`.
It reports physical transpilation and provider tier as UNVERIFIED. GitHub
artifacts expire, so preserve the JSON and SHA as a distinct append-only
Meta Registry record, **not** as a rewrite of the original registration.

The amendment is eligible for consideration only after its own offline CI
passes, code review confirms original 005 frozen source files unchanged,
and the separate human-protected GitHub environment is configured. No
approval, automatic merge, activation or hardware call is implied.
