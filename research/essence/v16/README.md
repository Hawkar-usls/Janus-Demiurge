# ESSENCE v1.6 — independently replayable, real checkpoint research benchmark

Source: the actual GitHub-tracked Janus-Demiurge native GPT checkpoint
`janus_model/checkpoints/promoted.pt`, with hard SHA-256
`fc767adb812ac3bea54c44cbccfa9680941f95e2c8a77120559b41da044d9463`,
Git blob `88cad884b437dd0ab655d913b1c83d6a6d669735`, trained-model
source Git blob `11e359e89d3946895b2e0d6817c54253f09dfed1`.
The repository's own training-state journal describes this as promoted learned
weights. That provenance is not independently externally certified.

The frozen public probe source is preregistered before implementation in
Meta Registry (see PR #559). The known historical anchor is reused,
plus 12 additional publicly pinned probe texts that are *not a blinded external holdout*.

## Experiment

Runs in separate new Python processes in a **read-only GitHub Actions job**.
Uses the native `load_checkpoint` validation, which checks the original SHA
and ZIP structure before `torch.load(weights_only=True)`.

- FP32 baseline: saved logits for 8 deterministic batches of historical anchor,
  and 8 batches of public fixed probes.
- INT8 and INT4: pack actual tensor storage through the ESSENCE v1.5
  `ESQ1` blockwise numeric adapter, keeping original tensor structure;
  reconstruct float32 tensors in a disposable in-memory model.
- FP16: same storage-based experiment, re-expanded to float32 before forward.
- Adaptive: choose INT4, INT8, FP16 or FP32 per tensor/chunk based on the
  ESSENCE error policies, and compare actual output loss/argmax vs baseline.
- Restored: reload the untouched original checkpoint in a fresh process and
  replay baseline logits exactly; check the SHA before/after.

Uses PyTorch CPU with 1 forward thread, 4 warmups and 20 measured forward
repetitions, sequence 48, batch 2. Records real process resident RSS and
Linux peak RSS **separately by mode**. CPU-only GitHub Actions has no usable
CUDA VRAM; that field is explicitly `NOT_AVAILABLE_CPU_ONLY`.

Records actual training-ledger numerical loss observations as seven channels
(the original four training/anchor losses and three derived differences/means),
with source SHA and a q.v1.5 receipt. These are **real recorded model training
observations**, NOT active internal ESSENCE microkernel weights. The microkernel
roles remain logical and inert.

The candidate runtime still uses **FP32 operations** after decompression.
Therefore packing bytes are evidence of potential on-disk storage savings,
NOT hardware-native low-bit acceleration or RAM reduction. Runtime latency
may regress and must be reported; native low-bit inference remains an OPEN
engineering gate. The checked-in original checkpoint and state are NEVER
modified or promoted.

## Protected limits

Data is publicly preregistered, not externally blinded. Lower quality is
reported, not concealed. Automatic production model updates are **disabled**.
Passing local fidelity does not override existing signed model-admission,
independent holdout, hardware-matched inference tests or service rollback.

All per-mode receipts, baseline logits, CPU memory and latency measurements,
and final results are published as GitHub Actions artifacts for reproduction.
