# JANUS admitted autonomous code writer

Owner instruction and ordered roadmap: https://github.com/Hawkar-usls/Janus_Genesis/issues/302
Implementation/acceptance: https://github.com/Hawkar-usls/janus-meta-registry/issues/370

The system authors one small pure function per cycle from a reviewed ten-task catalog. It runs on GitHub-hosted CPU every six hours and after reviewed implementation changes. No new inference API key or provider inference charge is required. Ordinary Actions/cache usage still follows the owner's GitHub plan. PC, NAS and an open chat are unnecessary for this cloud lane.

The author uses Qwen/Qwen2.5-Coder-0.5B-Instruct, Apache-2.0, revision ea3f2471cf1b1f0db85067f1ef93848e38e88c25. Model weights and every tokenizer/config file are verified before loading; only safetensors are loaded, remote model code is disabled. These are external open weights, never attributed to JANUS's native 446208-parameter model. Source: https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B-Instruct

The author has no source-write credential and never executes its generated code. Two actual model responses and their exact extracted source are preserved. No hand-written successful function is substituted if generation fails. The first response is greedy; the second uses a run-specific sampling seed. Duplicate responses remain visible in their hashes and do not establish diverse variants.

A separate clean job validates syntax/admission, then executes each candidate in a pinned Python container without network, credentials, privileged capabilities or writable host mounts. CPU, time, memory and process counts are limited. At least 200 fresh independently selected functional cases check output types, edge behavior and input mutation. Model prose, a syntactically valid function and a green author job are insufficient for promotion.

A separate publisher, which never executes model code, binds exact bundle, source, evaluator, model, image and prior-state hashes. It writes only STATE.json, ROADMAP.md, attempts/, receipts/ and generated/ on janus/autonomous-code-state. Both accepted and rejected variants are retained. Normal Git push rejects a competing head; replay is idempotent and conflicting/stale input is held. There is no main merge, permission edit, secret management, arbitrary task path or automatic authority expansion.

Another clean worker reconstructs only the exact persisted state commit, binds the latest receipt to the initiating workflow run ID, verifies the exact accepted task/source, and independently retests that task in the restricted container. Rejected runs return WAIT rather than retesting an older accepted function. Later use by a reviewed runtime adapter remains separately observable; a library test does not establish all-organ consumption.

The queue advances only after a verified promotion; failed work remains queued and preserves the previous working extension. After all admitted tasks are complete the writer reports IDLE. Adding new task families, changing the oracle or extending effectful permissions requires reviewed implementation. This bounded library is infrastructure for self-maintenance, not proof of universal autonomous programming, G1–G20, long-term reliability or independent scientific value. The main roadmap's current phase and prerequisites remain unchanged.

## Verified self-modules (isolated branch)

The publisher now builds `self_modules/<reviewed-task>/module.py` containing **exact** independently accepted model bytes, plus an immutable `MODULE.json` with original source hash, run-bound receipt hash, independently tested case count, pinned external model and evaluator image, API signature, and zero-dependency/zero-permission contract. The deterministic `MODULE_INDEX.json` records all modules and immutable manifest hashes. All artifacts are committed atomically in the existing `janus/autonomous-code-state` branch and never directly installed in trusted `main`.

Before packaging, the builder independently replays the full chain `candidate response → SHA-bound bundle → independent evaluation → immutable receipt → accepted source`. It rejects altered source, forged evaluation, substituted model weights, replay conflicts, changed earlier packages, or permission metadata. A clean separate worker reopens the state commit and repeats this exact audit before calling any extension in its networkless pinned container. Failed/rejected code does not create a module and cannot impersonate an earlier accepted one. Normal package publishing uses existing permissions and remains scoped to `self_modules/`, `MODULE_INDEX.json`, `STATE.json`, `ROADMAP.md`, and existing evidence directories.

**Admission boundary:** new module *categories* or new dependencies still require reviewed policy, independent behavioral oracle, tests, an explicit PR and permission checks. A published self-module is an independently validated **pure extension**, not an automatically trusted production library, a plugin installer, a universal self-writer or proof of P2/G1–G20. This is the first composable catalog layer toward controlled self-maintenance, not permission to run generated shell code or modify sensitive infrastructure.


## Review-only autonomous module PR lane

Once a pure module passes independent evaluation and is stored in the isolated
`janus/autonomous-code-state` branch, a separate GitHub-hosted proposer can
prepare **one review-only pull request** per invocation. This is not
autonomous integration into trusted `main`.

* The proposer reads and replays the complete module catalog, candidate bundle,
  pinned external-model identity, independent evaluator, immutable receipt,
  source bytes, and state commit. Its only allowed PR payload is
  `candidate_modules/<reviewed-task>/module.py` (exact authored bytes) and
  `candidate_modules/<reviewed-task>/PROPOSAL.json` (deterministic provenance
  with zero permissions and `install_into_runtime=false`).
* The branch name binds the reviewed task and the full SHA-256 of the generated
  source. Historical pull requests and existing remote review branches are
  checked so repeated scheduled runs cannot silently overwrite attempts or
  flood duplicate proposals. No branch force-push or deletion is authorized.
* Only the proposer job has narrowly scoped GitHub Actions write permissions
  for creating a proposal branch and a **non-merged** PR. It cannot mutate
  production state, call Rowan or install model-generated dependencies.
* A clean read-only verification job separately checks GitHub's actual PR
  head/base and exact two-file diff, finds the originating state SHA as an
  ancestor of the durable state branch, reconstructs the **historical** commit,
  and replays exact source/manifest/receipt/evaluator integrity against it.
  PRs cannot establish their own new criteria, and an unexpected file, fork,
  changed source, substituted state SHA or altered authority flag fails closed.
  Since GitHub-token-generated PRs may not trigger other workflows, the
  proposer explicitly dispatches the independent read-only verification.
* Approval and merge are separate human-reviewed actions. No generated code is
  automatically imported by trusted runtime, used as a privileged model tool,
  assigned a network credential, or deployed to other JANUS organs. An
  operational rollback plan is required before any later approved integration.
  This mechanism provides verifiable **proposals**, not general-purpose
  self-modification or proof of P2/GENESIS #162 autonomy.


### Repository Actions PR-permission fallback

The first real main-branch proposer run `41120045517` **pushed** an exact-source review branch for `retry_delay`, but GitHub explicitly rejected `gh pr create`: `GitHub Actions is not permitted to create or approve pull requests`. This is a repository policy, not proof that module verification failed. PR #379 was instead opened once using the separately authorized GitHub connection; its source is still review-only.

The workflow now preserves this restriction: when Actions PR creation is denied, it does **not** borrow a more privileged token or alter repository settings. It creates a persistent GitHub issue pointing to the immutable review branch, and dispatches a fresh **read-only** workflow to verify the branch's precise one-commit/two-file diff, exact source SHA, historic state commit ancestor, and replay of model and independent evaluator evidence. A human-authorized actor can turn the reviewed branch into a PR later. This fallback is not itself a PR and does not merge or install code. If issue creation or independent verification is denied, the workflow must remain visibly failed/HOLD rather than claim integration.
