# JANUS Ocean / R3 verified metadata bridge (read-only)

## What this activates

JANUS Ocean already has a genuine `JanusTinyTransformer` training/federated-average research cycle: `.github/workflows/janus-ocean-meta-next.yml`, four independent CPU rivers with a held-out chronology score. This change integrates the **real Ocean research cycle** with Meta Registry R3 source-quality observations, without treating untrusted public news as scientific truth or updating JANUS Ocean production checkpoints.

## Runtime integration

1. Daily GitHub R3 collector in `Hawkar-usls/janus-meta-registry` is scheduled at 06:27 UTC; it proposes a review PR containing a source JSON and its quality/novelty receipt. It does **not** auto-merge these PRs.
2. Ocean's existing scheduled Meta Next runs at 07:17 UTC (best-effort GitHub schedule). It fetches the **merged** public registry `main` into a read-only sparse checkout and SHA-pins the observed head.
3. `ocean_r3_registry_bridge.py` validates every available paired source/quality SHA and references, checks fail-closed trust flags, and produces `data/ocean_r3_witness.json`. If no reviewed R3 pair was ever merged, the explicit result is `WAITING_FOR_FIRST_MERGED_R3_PAIR`; the original pre-R3 source record is recognized only as a legacy exception.
4. The existing Ocean model trains solely on chronological **JSON path category metadata**. R3 quarantine and quality paths are filtered out of training FEATURES and target events, not just marked suspicious. Its model output predicts next JSON category, not the truth of articles, time travel or source usefulness.
5. After the four Ocean rivers finish, the existing aggregate creates candidate checkpoint and held-out evaluation against majority/Markov baselines. A new `ocean_r3_evaluation.json` binds its real model accuracy, checkpoint SHA, Meta HEAD, and the R3 witness SHA, while preserving `scientific_admission=HOLD` and `model_auto_promoted=false`.
6. Artifacts are uploaded (30–60-day retention). A separate research-only branch in the Ocean repository appends a per-run R3 evaluation JSON alongside the existing Ocean forecast and report. There are no automated writes to `Janus-Demiurge/main`, Meta Registry/main or JANUS Ocean production service.

## Scientific and privacy boundaries

- A maintainer-reviewed metadata PR is not a scientifically curated data pack. The R3 source/quality JSON remain research context only, no training labels, gradients, independent fact check, physical retrocausality proof or ability to answer arbitrary user questions.
- No external private URLs, chat content, phone data, health information, tokens or NAS logs are fetched. There are no external AI-provider keys.
- The PR-only validation job uses `contents: read` and Python standard library, no model training or PyTorch installation. A separate production-scope Ocean workflow is deliberately NOT triggered on every PR because its four-run PyTorch training is expensive.
- Any later real knowledge-driven self-learning requires a separate curator-approved pack, proof of data rights, held-out scientific evaluation, rollback and independent scientific acceptance. A novel DOI alone is not permission to retrain.
- Ocean is not switched to user-facing production, no NAS containers touched, existing 20- and 40-River experiments remain untouched.

## Acceptance

- PR tests: poisoned/altered SHA, orphan receipt, quality trust escalation, prior legacy-only, chronology quarantine leakage and winner/loser baselines all fail or pass correctly as expected.
- Current Meta Registry read-only smoke: valid SHA-pinned main HEAD and correct wait status when no reviewed pair exists.
- After approval and merge of this PR, the next scheduled Ocean cycle should actually execute four research rivers and publish its independent R3 witness and combined model/R3 report to GitHub artifacts and Ocean research ledger.
- If the scheduled job misses a day, this is an operational scheduling gap, not evidence of an absent or retrocausal signal.

Status: `JANUS_OCEAN_R3_RESEARCH_LINK / SHA_GATED / GRADIENT_QUARANTINED / PRODUCTION_HOLD`.
