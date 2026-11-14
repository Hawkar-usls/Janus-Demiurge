# ESSENCE v4.2 — independent Physarum falsification / external custodian kit

**Current state: AWAITING_EXTERNAL_CUSTODIAN.** No independent scientist, private blinded source corpus, externally anchored Ed25519 key, or externally signed result has been obtained. GitHub Actions PASS is **not** external replication.

## What is frozen before the outside test

The code and scientific acceptance thresholds are in [external_replication_contract.json](external_replication_contract.json). G3 and the two G4 siblings are the **existing, unchanged** FP32 weights:

| Model | Frozen SHA-256 weights |
| --- | --- |
| G3 ancestor | \`7ae346fff869dc14eec9e32ffa0e00419d98faa2150f79a763e927e0fc2cd299\` |
| G4 control | \`a5c5924acccdf47bfb9c3b6bc5ca9a8ba455e0cad4ef6d928ff684624634e57b\` |
| G4 Physarum | \`dfbe1214f6e6f954b3f999d7d8802c89e2aa5fe45e75ffe9a68a73d76953683f\` |
| G4 fixed 14-step cost-matched control | \`a0a8a878fd784235e390f441ec192d973e079714321b5d8a6b2cbb343d3bd174\` |

The G4 pair already has a positive **self-verified** result on HTTPX/attrs. **That cohort has already been seen** and MUST NOT be presented as the new blinded test. G3's Requests/Click cohort is also permanently excluded.

The original G4 trial performed 3 short development probes × 2 gradient steps, a Tero network + Jones swarm search, and then one 8-step training run for each of the two siblings. The original total computational training workload was **6 + 8 + 8 = 22 gradient steps**, not 8. Target CPU, wall clock, RAM, and inference must also be measured.

## Custodian qualifications

An *independent person or organization* who is not controlled by JANUS must:
1. Decide and privately retain **at least 10 original, unseen Python source tasks from at least five independently maintained source families**, with 2+ files per family, *after* the model weights above were frozen. The tasks must not appear in training files or any earlier public external-source tests. File size 4 KiB–100 KiB, no personal data/secrets; source must be lawfully usable.
2. Seal a private manifest of relative task paths, family labels, byte lengths and SHA-256 hashes, include the protocol JSON SHA-256, and **publicly commit the manifest hash** under the custodian's independently controlled repository or another externally verifiable timestamped registry, before the exam begins.
3. Use an independently controlled Ed25519 signing key with a public key fingerprint recorded outside any JANUS-controlled code. Sign the full manifest bytes and a separately audited full-cost ledger. A signature proves cryptographic consistency only; independence still requires verification of institutional control and the independent public timestamp.
4. Install Python and CPU PyTorch on the chosen target machine; run the standalone, independently readable \`tools/essence_v42_cleanroom_verifier.py\` (NO imports of JANUS trainers, optimizer, or legacy Physarum). It loads strict raw f32 arrays, checks all frozen SHA-256s, evaluates only local private samples, and returns task **hashes and scores, not raw contents or task paths**.
5. Report all outcomes, including negative, non-significant, excessive-cost, or invalid results. Never change the task set, seeds, costs, hyperparameters or criteria after seeing G4 results.

**GitHub Actions may test the verifier with synthetic tasks but must not run the true secret challenge on JANUS-controlled infrastructure.**

## Signed challenge schema (external; examples are fake)

\`\`\`json
{
  "schema":"janus.essence.custodian_hidden_challenge/4.2",
  "protocol_sha256":"<sha256 of frozen external_replication_contract.json canonical data>",
  "challenge_id":"<unique externally controlled identifier>",
  "made_after_model_freeze":true,
  "task_data_stays_with_external_custodian":true,
  "files":[
    {"path":"tasks/opaque01.py","family":"independent_repo_A",
     "sha256":"<sha256 of task bytes>","bytes":8192}
  ]
}
\`\`\`

The real manifest must contain at least 10 such files, with two or more per family and five or more families. Sign the UTF-8 \`json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",",":"), allow_nan=False)\` using Ed25519. The signature and the 32-byte raw public key are Base64 text files.

The separate precommit record:

\`\`\`json
{
  "schema":"janus.essence.custodian_precommit/4.2",
  "challenge_sha256":"<canonical manifest sha256>",
  "protocol_sha256":"<frozen protocol sha256>",
  "public_external_commit_url":"<independently owned timestamped public reference>",
  "external_custodian_identity":"<who controls the key>",
  "independent_organization":"<organization with independent management>",
  "published_before_exam":true
}
\`\`\`

The external reviewer must independently confirm the referenced public commit and earlier timestamp. A string in a JSON file is NOT sufficient evidence of publication or independent custody.

## External cost-replay ledger

The custodian measures original search cost and two candidate-training costs under the **same CPU, same torch version and thread count**, preferably with several repeated independent runs. The \`tools/essence_v42_cost_replay.py\` utility replays the exact 22 training steps, captures process CPU and wall-clock timing, asserts that both resulting checkpoint hashes match the locked G4 models, and records peak RSS. It may be audited or independently reimplemented; the self-run GitHub Actions measurement is not external evidence.

The custodian then signs a cost ledger of schema \`janus.essence.external_cost_replay/4.2\`, including:
- \`protocol_sha256\`, \`challenge_sha256\`, \`g4_weights_sha256\` (mapping control and physarum to the exact hashes above)
- \`measured_on_same_cpu: true\`, \`full_probe_steps: 6\`, \`per_sibling_steps: 8\`, \`no_cost_imputation: true\`, \`measurement_method: "CPU_PROCESS_TIME_SECONDS_REPLAY"\`
- nonempty \`hardware_description\`
- measured positive \`control_training_cpu_seconds\`, \`physarum_probes_cpu_seconds\`, \`physarum_network_search_cpu_seconds\`, and \`physarum_training_cpu_seconds\`

Those four CPU quantities must be measured directly. Exam inference CPU time is then measured by the standalone verifier and added to each arm. These costs are machine-dependent; compare on one CPU and report memory/RAM/wall times as well. The cost ledger also requires independent inspection of the time measurement method. No cost shall be silently counted as zero.

## Independent verifier invocation

After building a safe offline folder for the three sealed models, the challenge and task files:

\`\`\`sh
python -m pip install 'torch==2.5.1' 'cryptography==44.0.3'
python tools/essence_v42_cleanroom_verifier.py \
  --policy research/essence/physarum_v42/external_replication_contract.json \
  --g3-zip sealed-G3.zip \
  --g4-zip sealed-G4-siblings.zip \
  --baseline14-zip sealed-14step-costmatched-control.zip \
  --challenge challenge.json \
  --precommit externally-published-precommit.json \
  --public-key external-custodian-ed25519.pub.b64 \
  --expected-fingerprint EXTERNALLY_VERIFIED_ED25519_PUBLIC_KEY_SHA256 \
  --challenge-signature challenge.sig.b64 \
  --cost independent-full-cost-ledger.json \
  --cost-signature full-cost-ledger.sig.b64 \
  --tasks-dir /secure-offline-unseen-tasks \
  --out /secure-offline-results/physarum-g4-independent-receipt.json
\`\`\`

The full receipt includes an equal-file-weight next-byte CE over 32 evenly spaced 24-byte windows per source, per-family results, an exact one-sided sign test across *independent source families*, inference CPU and process RSS, and the **cost-adjusted gain per CPU vs G3** for the control and Physarum siblings.

### Preregistered success is deliberately difficult

All of these must be true: at least 1% mean loss reduction versus both the old 8-step control AND the sealed 14-step equal-budget fixed control, no source family loss regression over 0.001 CE, one-sided family sign-test p ≤ 0.05, both children better than G3, and Physarum's gain per **full CPU second** at least 1.05 times the sealed 14-step equal-budget control. Any contrary result is \`NO_COST_ADJUSTED_PAIRED_GAIN\`.

**Safety boundary:** the standalone verifier never grants production privileges. Even a signed \`PASS_COST_ADJUSTED_PAIRED_GAIN\` remains \`HOLD_PENDING_INDEPENDENT_IDENTITY_AND_PRECOMMIT_AUDIT\` until an uninvolved reviewer verifies the custodian's institutional independence and the actual earlier commitment publication. Production models may only be changed by a separate authorized, independently reviewed deployment protocol with holdouts, target-machine measurement and real rollback.

This package does not create a hidden benchmark, connect an external lab, receive a signing key or run an outside computer by itself.

### Prior cost-matched evidence (not external validation)

A separate 14-step fixed control checkpoint was already sealed in [GitHub Actions run 43652825898](https://github.com/Hawkar-usls/Janus-Demiurge/actions/runs/43652825898) before the earlier internal source exam. On development data, this fixed 14-step model had loss **4.963532**, better than Physarum's **4.998392**; this is evidence AGAINST claiming a universal Physarum advantage. That internal external-source exam stopped on a Git blob hash mismatch, so it does not establish any held-out gain. Its attempted Werkzeug/Rich/Trio/Pydantic cohort is excluded from the genuinely new hidden custodian task set. All previous negative results are retained.
