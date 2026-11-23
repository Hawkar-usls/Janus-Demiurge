# JANUS Rowan/TOPA shadow-learning protocol (frozen before training)

**This is supervised training of a new, small sequence-to-processed-label calibration model, not fine-tuning Rowan Boltz-2 or Tranception.** It changes actual trainable regression weights on a pinned public third-party assay. The trained model remains SHADOW and has no Rowan credit-spending or automatic science-claim authority.

## Frozen reference and target
- Public dataset: `genbio-ai/ProteinGYM-DMS`, revision `cc6b0b56553e694dbf27dc84c6b37a8686e64b85`, `singles_substitutions/BBC1_YEAST_Tsuboyama_2023_1TG0.tsv`.
- SHA-256: `ca355a655381c95fe899d61a406251e0cd17d68bbabe287651d526fdeb821f87`.
- Exactly 1084 unique 64-residue single substitutions, finite processed labels. Labels are **third-party processed measurements**, original lab units, normalization and independent biological replicates are NOT verified.
- No trained model inputs include labels, fold identifiers, output scores or Rowan-derived data.

## Features and split
Feature vector = intercept + source amino acid one-hot (20) + destination amino acid one-hot (20) + difference of fixed Kyte-Doolittle hydropathy index + absolute hydropathy difference + normalized mutation position and quadratic position. Source 64-aa wildtype fixed from BBC1 manifest. No variable learned representation or external model downloads.

All variant rows sharing the same **mutation position** belong exclusively to one split. Sort 64 positions by SHA256(`JANUS-TOPA-20261025-SPLIT-V1|position`), first 16 held-out TEST positions, next 12 inner VALIDATION positions, remaining 36 TRAIN positions. Hyperparameter λ chosen from {0.1,1,10,100} using TRAIN/VALIDATION only, then model is refit on TRAIN+VALIDATION (48 positions), evaluated once on untouched 16 TEST positions. Normalize numerical features only by constants defined above; center outcomes by training mean. Ridge penalty applied to every coefficient except intercept (implemented as centered target and features with unpenalized centered mean).

TOPA independent replay must read source TSV separately by HTTPS and verify exact SHA256; rebuild holdout positions without trusting training metadata; independently recompute predictions and compare MAE/RMSE and exact printed coefficients; compare to training-mean baseline, produce negative-control shuffled/mislabelled evidence. **No autotuning on TEST** after outcome inspection.

## Promotion / stopping
- If fewer than 1084 valid rows, any duplicate, non-canonical substitution or nonfinite label: STOP.
- Every retrain is exactly reproducible on the same source SHA. New learned weights are archived append-only and must be independently replayed by TOPA.
- Only allow `SHADOW_CANDIDATE_EVALUATED` if all checks pass; never permit production promotion without a *different independently sourced assay*, robust replicated controls, and explicit future approval.
- Strong test accuracy in within-assay position heldout is *not* independent biological validation; model can exploit assay-specific effects. Weak/test-negative findings are retained, not hidden.
- AURA Oracle may propose falsifiers/negative controls as versioned suggestions. It must not set acceptance criteria after the data, train on test labels, write model weights or authorize credits.
- This workflow consumes **zero Rowan credits** and never transmits the Rowan project key. It runs on GitHub, not Yaksa or NAS.

## Autonomous learning meaning
New public data can trigger an independently preregistered subsequent model version; this version explicitly accepts only a frozen SHA. The mechanism learns model **weights** using genuine gradient-free ridge fitting, but it is not a self-training foundation model, nor can it autonomously expand study scope or spend paid credits.
