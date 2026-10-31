# JANUS NAS Archeology · Code Steward v1.6.1 and archival guards

These are **owner-NAS historical sources**, not working production code. Recovered from `Janus/services/` on 2026-10-31. All original NAS files remain unchanged. Current DADDY_KEYMASTER, Demiurge and Meta Registry policy remains authoritative.

| Original NAS file | Original SHA-256 | Key value |
|---|---|---|
| `services/janus_code_steward.py` | `25b470b8f8b286f439b02df45edaf12ae8686e7a3b9d7f362fa8f21306f8e8d8` | Append-only release receipts, code signature, activation, compatibility and bounded probation logic |
| `services/janus_archive_stack.py` | `b0ffbf601eb2455679d8425003f423b4bca10efdc6bef47cbf189b621f06aa7c` | Content manifests, retention classes, bounded background archive ingestion and quarantine |
| `services/db_guard.py` | `468e06e8c62bab580120537a40d9f0f98ad3f92e80310644a7747a33321cbefa` | SQLite health, candidate discovery and rescue (potentially destructive!) |
| `services/janus_habitat_gate.py` | `5f4204229c9f95f3fa8f2be863f617db1b31793c238857e73de01752651ccffc` | Older Habitat gate |
| `services/janus_habitat_terminal.py` | `221db18d214bbe030b519546853b393689bdfd4e6722281e42d7be175241436e` | Older Habitat terminal |
| `services/modules_live/mod_janus_decision_governor.py` | `693b6a7846ce929ba5276fcbec42c4b47a75ef33e909ed365d1ccb9ae554b9c1` | Directives/entropy/training feedback aggregation |

GitHub text copies may differ at newline/encoding boundaries. Original hashes attest **source bytes on NAS**, not restored Git blob identity.

## Verified historical receipts

The `receipts/` directory contains four **actual** historic NAS JSON records: two releases and two activations. Their self-hashes are independently validated in CI using the original canonical JSON format. They show a first bootstrapped release and a second activation, but **do not prove production-grade self-programming**.

- `000001`: source `LIVE_NAS_BOOTSTRAP_SNAPSHOT`, observed gate & terminal bytes 54,038 / 113,430; `ci=false`, `demihead=false`.
- `000002`: source `MAMA_MAMA_SMOTRI_YA_KODYU_NOHAND_DELEGATING_SMOKE_TEST`, 204 / 292 bytes; a smoke test with reported `ci=true` etc, **NOT** proof of real defect-repair or safe release promotion.
- The two self-hashed activation receipts document an append-only sequence from `000001` to `000002`, not a verified live rollout test on an independently supervised node.

### Critical restrictions

- `db_guard.py` **defaults `JANUS_DB_GUARD_ALLOW_FULL_RESTORE` to `"1"`** and can overwrite a DB, so do not run/import it against NAS or production SQLite, and never silently reuse its policy.
- `janus_archive_stack.py` may move/quarantine items when activated. It is preserved only as untrusted historical reference code; no scheduler created for it.
- Historical Habitat and Decision Governor modules have not been proven equivalent to current R2, real cloud worker failover or Model Loader.
- Avoid importing any `*.py` under this archive; CI only performs AST parsing and receipt checks, no legacy execution, no NAS connections.

### Possible safe future improvements

Reimplement pure receipt checks as a new isolated side-effect-free validator; compare current Git CAS archive rotation with old retention categories; adopt candidate integrity checks **only** under an explicit read-only, owner-approved sandbox policy with WAL/sidecar awareness; evaluate rollback timing on synthetic regressions. Use source hashes and modern independent tests before proposing any production changes.

