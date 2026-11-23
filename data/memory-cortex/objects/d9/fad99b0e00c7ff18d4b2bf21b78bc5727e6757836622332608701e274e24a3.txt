# JANUS — GitHub-native public evidence intake and Meta Registry growth

## Purpose and actual execution model

The existing Meta Registry already has recurrent GitHub Actions for autonomous reports and an EYE corpus indexer. This additional workflow introduces a **review-gated, append-only public-source intake** without a server, NAS modifications, live model deployment, or unbounded training.

Daily schedule (after reviewed merge into `main`): `06:27 UTC` via `.github/workflows/janus-public-source-intake.yml`; also supports manual `workflow_dispatch`. Jobs are concurrency-serialized, run on a standard GitHub-hosted CPU runner, have timeouts of 5/8/6 minutes, use no external API keys, and never open a network listener. **A draft PR does not activate a scheduled workflow on `main`.**

## Data acquisition (public and bounded)

| Source | Exact intake | What the receipt does NOT prove |
|---|---|---|
| GDELT | `lastupdate.txt` and *at most one* latest `.gkg.csv.zip` (max 9 MB compressed); verify manifest size and MD5, compute a fresh SHA-256, inspect 1–3 TSV rows for 27 fields; store only structural metadata and row hashes | No source article fact-checking, no raw article text, no time-travel signal |
| Wikipedia | fixed public Russian search `замедление времени`, at most three article titles/URLs | No claim-by-claim encyclopedia validation |
| OpenAlex | fixed search `quantum causality`, at most three DOI/title/publication-date entries | No publisher full text, abstracts or peer-review verdict |
| TACHYON R2H | latest **public GitHub Actions run metadata** from `Hawkar-usls/Demi_Head`: run ID, commit, workflow status | No evaluation of model weights, scientific generalization or secret assessor |

All external URLs are exact allowlisted HTTPS API routes. GDELT manifest HTTP links are upgraded only if they match the exact official GKG archive hostname and filename pattern; redirects are rejected. Requests use bounded sizes, no retry loops and no private user questions. GDELT DOC API is not called (the earlier HTTP429 is respected). GKG public batch availability was independently observed on a connected PC before this workflow.

## Immutable evidence receipts

An intake run produces one small `JANUS-PUBLIC-SOURCES-<source-digest-prefix>.json` file, with SHA-256 over canonical JSON. Its ID is derived from **source content**, not the time the GitHub Action ran. Repeating an identical source observation does not rewrite an existing file.

Every entry explicitly has `source_class=PUBLIC_UNTRUSTED_METADATA_QUARANTINE`, `training_permitted=false`, `factual_claims_verified=false`, `scientific_admission=HOLD`, `auto_merged=false`. Provider failures are recorded as unavailable rather than incorrectly treated as false facts. The observation is first kept as a downloadable Actions artifact; the separate publish job creates **one new branch and one review-only PR** containing only `data/observations/public_source_quarantine/<name>.json`. No workflow step auto-merges any PR.

If GitHub repository settings do not permit Actions to create PRs, the workflow preserves the pushed review-only branch and reports the limitation. Approving GitHub Actions permissions and merging candidate PRs require authorized repository maintainers. The source PR's read-only smoke test does NOT publish or receive write credentials.

## EYE and scientific safety firewall

Important: Meta Registry's existing `EYE Meta Registry Training` workflow indexes most of the source tree. Adding external web data directly under trusted experiments could accidentally train its derived semantic association engine on unverified or adversarial text.

This candidate explicitly adds `data/observations/public_source_quarantine/` to `EYE/training/train_eye_registry.py`'s `EXCLUDED_PREFIXES`, and adds the corresponding exclusion to the EYE workflow's trigger and hard indexing audits. The isolation is tested. No new GDELT, Wikipedia or OpenAlex observation is **automatically** used to train TACHYON, EYE, SLIME, or an autonomous production AI.

For knowledge-base promotion, a separate reviewed scientific source must be checked for attribution, content rights, accuracy, independent evaluation, duplicates and train/eval contamination; then a different PR may copy a **curated** derivative to an approved corpus. Only then can the existing EYE model regenerate its non-authoritative index. Physics and retrocausal experiments still require an independent sealed external assessor. A network archive is not a scientific discovery.

## Operational and financial boundaries

- Only one regular GitHub run per day, no loops, no recursion or automated concurrent runners, no hidden API keys, no cloud billing commitments. A GitHub Actions schedule can be delayed or skipped and needs the workflow on `main`.
- All runner permissions are `contents: read` except the narrow `propose-review-pr` job (`contents: write`, `pull-requests: write`). Neither training nor download jobs receive write authority.
- The workflow never touches NAS Docker containers, GitHub secrets, the production MCP endpoint or JANUS Ocean.
- Zip sampling is bounded; it does **not** decompress a GKG archive into persistent storage. Only checksum receipts, sampled-row SHA values and public bibliographic metadata are archived.
- Deployed MCP source search remains a separately approved project in `Hawkar-usls/Janus` draft PR #51. This GitHub-native intake does not expose a live public HTTP/MCP server, but it can grow Meta Registry source inventory without server uptime.
- Training results from R2H are represented by run provenance metadata; original model checkpoint archives and detailed metrics remain in the already recorded separate research receipts/Google Drive archives. Do not claim they are retrained by this collector.

## Acceptance procedure

1. Review this source PR. Check the offline fail-closed tests plus a one-time read-only live-source PR smoke artifact.
2. Review security implications of GitHub Actions repository permissions and auto-PR setting. Merge only after approval.
3. Trigger `JANUS Public Evidence Intake — Quarantine and Review PR` from the default branch or allow the next daily schedule.
4. Inspect the emitted artifact and newly proposed quarantine PR. Confirm the hashes, source URLs, statuses and exact one-file write scope.
5. Review/merge an appropriate metadata PR. Independently curate and promote any trustworthy information. Do **not** auto-import these records into TACHYON's training weights.

Status while draft: `CODE_PROPOSED / SCHEDULE_NOT_ACTIVE / EYE_QUARANTINE / NO_AUTOMERGE`.
