# JANUS R3 ↔ Ocean: public run provenance feedback

Ocean's own four-river training and actual model evaluation execute in `Hawkar-usls/Janus-Demiurge` through `.github/workflows/janus-ocean-meta-next.yml`. The SHA-validated, read-only Ocean R3 witness was merged to Demiurge main in PR #527, commit `7acccb8e52dddc4521fd14238284443c0d3057af`.

GitHub R3 daily source intake (`06:27 UTC`) now adds a FIFTH bounded public provider `ocean_action`, alongside GDELT GKG, Wikipedia, OpenAlex and TACHYON R2H action metadata. It queries only `https://api.github.com/repos/Hawkar-usls/Janus-Demiurge/actions/workflows/janus-ocean-meta-next.yml/runs?per_page=1`. The endpoint is hardcoded and allowlisted, requires no API key in the repository, sends no user prompt, and reads only run id, head commit, status and conclusion.

The returned provider card is `PUBLIC_ACTION_RUN_METADATA_ONLY`. Its explicit flags are `scientific_quality_of_model_verified=false`, `candidate_auto_promoted=false`, `model_weights_or_metrics_independently_verified=false`, `trained_on_unreviewed_r3_source_text=false`. An accepted run status means only that GitHub has recorded a workflow run, not that the model improved or that any physics hypothesis was confirmed.

The R3 evaluator knows that `tachyon_action` refers exactly to `Hawkar-usls/Demi_Head` / `tachyon-r2h-parallel-research.yml`, and `ocean_action` refers exactly to `Hawkar-usls/Janus-Demiurge` / `janus-ocean-meta-next.yml`; it rejects host/repo spoofing and attempts to claim scientific model authority.

Append-only history compatibility: existing four-provider source+quality receipts remain valid with their original SHA256 and ID. New observations use five sources. Under an unavailable Ocean API, the fifth provider becomes `PROVIDER_UNAVAILABLE` with a sanitized status, never a made-up success or a claim about model quality.

The loop is now:

Meta Registry approved R3 main metadata → Ocean read-only witness → Ocean four-river chronology research & score ledger → Meta Registry receives Ocean **public run metadata** for the next review PR.

Actual model result JSON remains in Demiurge's append-only `janus/ocean-meta-forecast-ledger` and Actions artifacts. No direct cross-repository write key was granted, no user-facing model deployed, and no automatic training on external news was enabled. Future import of model metrics into Meta Registry requires an additional independently validated report-admission contract.

Activation prerequisites: tests on this PR must pass, then review and merge into Meta Registry main; the next scheduled intake can observe the Ocean run. The daily schedule is best-effort, not a real-time event bus.

Status: `OCEAN_R3_RUN_PROVENANCE_PROPOSED / SCIENTIFIC_HOLD`.
