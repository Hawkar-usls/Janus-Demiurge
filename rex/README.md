# JANUS Rex v1.1 — bounded organogenesis

Rex creates runnable module candidates. Rex does **not** admit or crown them.

Full lifecycle:

`Demiurge desire -> Rex Director -> bounded ModuleSpec -> Rex builder -> candidate -> Auditor -> quarantine -> Nexus exact-SHA policy gate -> bounded runner`

Canonical laws:

- `REX_CAN_CREATE_NE_REX_CAN_CROWN`
- `GENERATOR_MUST_NOT_SELF_AUTHORIZE`
- `DESIRE_TO_SPEC_NE_ADMISSION`
- `AUDIT_PASS_NE_ADMISSION`
- `ADMISSION_BINDS_EXACT_SOURCE_SHA256`
- `AUTORUN_IS_NEXUS_POLICY_NOT_REX_AUTHORITY`
- `NO_CANONICAL_OVERWRITE_BY_REX`
- `AUTHORITY_DELTA_ZERO`

v1.1 deliberately generates Python from bounded deterministic templates. A desire or model may propose intent/parameters, but it is never executable source and never grants admission. Only templates allowed by `rex/policy.json` can be generated. Automatic execution is a separate Nexus decision under `rex/nexus_policy.json`, requires an Auditor PASS, binds the exact source SHA-256, runs with a scrubbed environment and bounded input/timeout, and preserves `authority_delta=0`.

`rex/JANUS_REX_DESIRES.json` is the bounded organogenesis request queue. `JANUS Rex Director v1.1` materializes deterministic specs from that queue and dispatches Organogenesis. New safe modules therefore can be born and run without giving Rex final authority over their own admission.
