# Keymaster · NAS cold-copy integrity witness

This is an opt-in, owner-local, read-only check, not a background task. It detects mismatch in an existing passive NAS cold mirror without increasing the continuous CPU load on the NAS and without contacting GitHub or external providers.

Manual invocation on a consistent offline copy:

    python daddy_keymaster/nas_cold_copy_witness.py --root "/path/to/owner/offline/keymaster_meta_json"

The verifier checks exactly four references: LATEST.json, MIRROR.json, MIRROR.sha256 and snapshots/<source-commit-sha>.json. It enforces schema, maximum byte sizes, safe 40/64-character hash formats, pointer-to-mirror SHA-256 equality, sidecar hash equality, and snapshot byte identity. No file is edited, no contents of MIRROR.json are returned, no model is activated, no recovery is triggered and no schedule is created.

Owner-NAS read-only observation on 2026-11-01: source commit e0f8e8690e2e943e8c42fcbee6ae097edbc576f7 (Demiurge daddy-cas: epoch 8); pointer reported active_epoch 8, archive_count 3, mode PASSIVE_COLD_COPY_NO_MODEL_EXECUTION. Mirror, sidecar and NAS-local snapshot agree on file SHA-256 4b9ced78c31fd8f7d2370e504f58132e817bb2002df955154373dc110e6fcd2a.

The report does NOT prove that archive_count equals the true number of independent copies; the internally declared semantic snapshot hash is not validated. NAS-local duplication does not establish offsite redundancy or a successful disaster recovery. These remain separate gates.

CI tests use only synthetic temporary files with no NAS access, runtime tokens or model checkpoints.
