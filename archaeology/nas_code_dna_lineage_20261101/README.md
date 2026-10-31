# JANUS NAS · historical \`code_dna\` recovery (read-only)

Original source: the owner's old NAS snapshot \`Janus/janus_data/janus.db\`. This file is **not** part of GitHub: it contains private tables (\`vault\`, personal memory, agent history) and must stay off public repositories. No NAS network address or access credentials are committed.

Forensic inventory observed 2026-11-01: **33** \`code_dna\` records, **15** distinct UTF-8 source-content SHA-256 values, **18** repeated snapshots; first timestamp \`2025-12-27T01:40:07.052591\`, last \`2026-01-01T16:28:20.111225\`. These are database-reported dates, not a cryptographically signed timestamp service. All 33 records refer to the original \`ai_engine.py\`. No old Python code is imported or run.

\`tools/nas_code_dna_lineage.py\` is the missing *active verification capability*, not a resurrected old model. Given an owner-provided **stable, offline** SQLite snapshot, it selects **only five whitelisted columns from \`code_dna\`** and emits a metadata-only JSON: timestamp, sanitized basename, version tag, UTF-8 source length and SHA-256. It never runs \`source_code\`, accesses \`vault\`, starts a model, or writes to the input database. It intentionally does not hash the entire multi-GB database (the provenance hash is the UTF-8 content of each SQLite TEXT source field, not the physical SQLite file).

## Manual, opt-in reproduction

\`\`\`powershell
python tools/nas_code_dna_lineage.py --source "D:\secure-offline-copies\janus.db" --output "D:\secure-offline-copies\code_dna_lineage.json"
\`\`\`

Use a consistent **offline copy**, not an active database with WAL sidecars. By default no output file is created; without \`--output\`, the metadata is displayed on stdout. The output file is created exclusively and cannot overwrite anything. No GitHub Actions job contacts the NAS: CI uses a synthetic temporary SQLite fixture and read-only tests.

This capability is eligible for **HRAiN read-only metadata browsing** through a separately reviewed Meta Registry artifact, not for iNaiHR attribution as truth, model checkpoint promotion, full-history restoration, autonomous code installation or P=NP certification. \`code_dna\` is a historical lineage witness, not an evaluation score.

## Admitted claims and hold gates

- ARCHIVAL_SOURCE_METADATA: yes; authentic observed SQLite TEXT field hashes / timestamps.
- INDEPENDENT_CODE_BEHAVIOR_REPLAY: no.
- MODEL_QUALITY_OR_SELF_PROGRAMMING: not established.
- 3-SAT 220–240 SUCCESS: not established.
- PRIVATE_DATABASE_EXPORT: forbidden.
- UNTRUSTED_PICKLE_LOAD / LEGACY_CODE_EXECUTION: forbidden.
