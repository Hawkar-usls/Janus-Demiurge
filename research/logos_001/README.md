# JANUS Demiurge — LOGOS-001 R1 experimental symbolic discovery

**Research-only, not a production model or universal solver.** This module
mirrors the frozen stdlib [JANUS Meta Registry LOGOS R1]
(https://github.com/Hawkar-usls/janus-meta-registry/tree/d21d95cdb3fc506e05113b2d1ac778c52b147564/research/logos_001)
algorithm and wraps it in a typed Demiurge proposal-only API.

Run locally after producing the frozen synthetic TRAIN+VALIDATION dataset:

    python research/logos_001/demiurge_adapter.py \
      --input /tmp/logos-r1-input.json \
      --out /tmp/demiurge-logos-r1-candidate.json

The adapter returns *proposed* analytic expressions. It is forbidden to
self-certify these as laws. Independent witness code in Meta Registry evaluates
held-out test coordinates, outside-regime shift and random-label controls, and
tampered evidence on a separate CI worker.

Mirrored source is byte-identical to Meta Registry commit
d21d95cdb3fc506e05113b2d1ac778c52b147564, checked at every CI run.
The workflow has no schedule, read-only permissions, and no Rowan, paid model,
NAS, model selector, production scheduler, or deployment side effects.

Scientific scope: recovery of four deliberately simple synthetic laws. The
negative controls include noise-only data and a distribution shift that looks
valid on TRAIN+VALIDATION but breaks on fresh TEST observations. The synthetic
oracle code is public, so this is **not** an externally blinded benchmark.
No God Code metaphysical proof, P=NP result or novel physical law is claimed.

Before any live Demiurge promotion, run the same gates with licensed genuinely
unseen external data and a separate model performance baseline.
