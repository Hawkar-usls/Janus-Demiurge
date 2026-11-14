# ESSENCE v1.6.1 — real, native dynamic INT8 CPU experiment

The v1.6 experiment showed that PyTorch transformer logits after a packed
INT8 storage round-trip are close to baseline, but that reconstructing FP32
weights does **not** save process memory or accelerate true low-bit inference.

This independent research branch adds a test using actual PyTorch native
`torch.ao.quantization.quantize_dynamic(..., {torch.nn.Linear}, dtype=torch.qint8)`
on a disposable copy of the **same SHA-256-pinned committed JANUS GPT
`promoted.pt`**. It quantizes supported Linear layers only; embeddings,
norms and any unsupported modules remain original precision.

A fresh **separate-process FP32 reference** is recorded before the native test.
Next-token CE, top-1 agreement and CPU median time are measured using the exact
same frozen historical anchor/public probe corpus. Linux process RSS is read
from /proc and original versus dynamic quantized state_dict byte size is
measured using in-memory PyTorch serialization. GPU VRAM remains unavailable
on CPU CI. The conversion does temporarily hold the original and quantized
models simultaneously, so the memory result is labelled allocator-confounded
and cannot by itself prove a real deployment memory saving.

Tests guard checkpoint SHA before and after. No model training, replacement,
service write or checkpoint promotion. Any output quality regression is a
**HOLD**, not a reason to weaken checks.

This is an additional test, distinct from the signed external evaluator and
actual service canary rollback necessary for autonomous changes to production
JANUS models.
