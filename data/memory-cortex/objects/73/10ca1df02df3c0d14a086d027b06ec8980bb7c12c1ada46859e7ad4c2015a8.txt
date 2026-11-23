# ESSENCE v1.6.4 — prospective external-source replay

This GitHub-only research test evaluates the **single** previously selected
three-layer native CPU INT8 candidate, mask 7, after the source and selection
rule were frozen in the data/essence/v164 JSON. It does **not** search further
quantization masks and is not permitted to adapt the model during evaluation.

* Fixed original model: exact SHA-256 and Git blob in Janus-Demiurge at
  commit `edc4f104c4da43411d3987616c8de2d1cbd3a99d`. This is the
  same `promoted.pt` whose checksum was independently verified in v1.6.
* Two fresh **externally sourced**, SHA-pinned public GitHub datasets:
  CPython's `README.rst` and PyTorch's `README.md`, each at a November
  14, 2026 commit. Raw bytes are downloaded only in the GitHub Actions
  runner; exact Git *blob* SHA verification fails closed. Text is not
  redistributed in this repository.
* Immutable test settings: 8 batches of 2 × 48 tokens per corpus, seed
  2026111491, warmup 5 and 30 forward timings, one CPU thread.
* The Meta Registry runner independently reconstructs the PyTorch dynamic
  INT8 modules for the three FFN Linear layers and verifies the tied
  floating-point token embedding and output head. It uses native FP32
  trained weights as its baseline. The source code is not imported from the
  v1.6.3 candidate quantizer — selection and evaluator implementations
  are separate, although both rely on PyTorch.
* Test outcomes recorded: next-token loss, top-1 agreement with FP32,
  actual serialized state size, in-process CPU runtime/RSS, original
  checkpoint SHA and all input Git blob identities. FP32 and INT8 each
  run in a fresh Python process. CPU RSS still contains PyTorch runtime
  overhead and any allocation retention.
* Frozen hard limits: top-1 at least 97% and relative loss regression at
  most 0.5% **on each** new corpus, serialized state saving at least 25%
  and CPU median time regression at most 15%.

An experimental pass is **only prospective development evidence**. Public
README data may still overlap model pretraining; this is neither an
independent external custodian nor a cryptographically blinded unseen
laboratory cohort. No weight update, generation of an active service,
model training, production authority, automatic PR merge, NAS access,
or deployment is allowed. Full native model changes still require
independent blind validation and a reviewed rollbackable canary.
