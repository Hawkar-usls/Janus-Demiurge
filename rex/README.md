# JANUS Rex v1 — bounded organogenesis

Rex creates runnable module candidates. Rex does **not** admit or crown them.

Pipeline:

`ModuleSpec -> Rex builder -> candidate -> Auditor -> quarantine -> Nexus exact-SHA admission -> bounded runner`

Canonical laws:

- `REX_CAN_CREATE_NE_REX_CAN_CROWN`
- `GENERATOR_MUST_NOT_SELF_AUTHORIZE`
- `AUDIT_PASS_NE_ADMISSION`
- `ADMISSION_BINDS_EXACT_SOURCE_SHA256`
- `NO_CANONICAL_OVERWRITE_BY_REX`
- `AUTHORITY_DELTA_ZERO`

v1 deliberately generates Python from bounded deterministic templates. A model may later propose a `ModuleSpec`, but model output is not executable source and cannot grant admission.
