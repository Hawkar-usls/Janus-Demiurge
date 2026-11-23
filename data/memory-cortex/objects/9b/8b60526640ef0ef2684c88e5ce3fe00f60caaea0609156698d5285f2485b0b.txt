# ESSENCE v1.6.5 — Conservative real-model quantization admission

This is an **additional post-hoc** risk assessment of the successful
v1.6.4 prospective two-public-source experiment. It does **not** change the
predeclared v1.6.4 empirical pass threshold retroactively.

## What has actually been demonstrated

GitHub Actions in a **separate Meta Registry repository** read the exact
version-pinned, trained JANUS-Demiurge `promoted.pt`, recreated three
native CPU INT8 FFN Linear operators, and evaluated on post-selection
CPython and PyTorch README blobs from November 14, 2026. Both corpora
met the preregistered empirical >=97% Top-1 agreement and 0.5% CE
non-regression thresholds, while reducing serialized model bytes by
32.73% and measured single-run forward time by 12.34%. The CPU process
RSS **rose**; no RAM saving was demonstrated and no GPU was available.

## Why this is still not a production-ready model

There were 8 batches of 2 sequences × 48 token predictions = **768
correlated token positions per corpus**. Top-1 matches were **745/768
(97.005%) and 746/768 (97.135%)**. Even if observations were independent,
an *illustrative Wilson 95%* interval gives lower bounds of about 95.55%
and 95.70%, both below the proposed operational reliability threshold.
Token observations from overlapping language-model sequences are *not
independent*, so this lower bound is optimistic as an uncertainty summary,
not a valid empirical coverage guarantee.

The data are public external files, not private independently blinded
laboratory cohorts. There is no proven training-data separation,
external custodian, service-level canary, live production rollback, or
signed model-change review. The present benchmark selected among
15 candidates in development, so its development metrics are biased
upward by selection. One CPU timing run is not sufficient to claim a
robust hardware speedup.

The fail-closed admission witness `tools/essence_v165_conservative_admission.py`
uses Git-blob-pinned append-only evidence, validates actual trial source
receipts and matches counts before recomputing Wilson lower bounds.
It explicitly rejects forged custodian, authority, token counts and
conservative-PASS claims. Output **always remains production HOLD**.

This infrastructure runs **only on PR updates or an explicit manual
GitHub Action**, so unchanged evidence does not waste scheduled CI time.
No active model is modified or promoted, and NAS is out of scope.
