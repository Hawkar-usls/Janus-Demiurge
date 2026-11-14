# ESSENCE v1.6.2 — selective native CPU INT8

Follow-up to verified v1.6.1 full dynamic INT8 HOLD: five quantized
Linear operators reduced serialized model bytes but changed next-token Top-1
argmax too much (94.66% historical, 96.48% public probes; threshold 97%).

This trial preserves the tied **token embeddings + lm_head output layer at FP32**
and applies native PyTorch INT8 only to the four internal Transformer
feed-forward Linear layers. It compares both `all_linear` (historic control)
and `ffn_only` in independent new CPU processes against the same
SHA-pinned baseline logits and preregistered frozen probes.

Measures genuine nn.quantized.dynamic.Linear count, loss, top-1 fidelity,
CPU latency, state_dict serialized bytes, current process RSS; retains
hardware/allocator caveats. Automatic promotion remains permanently false
in the research lane; only external evaluation and reviewed operational
rollback can authorize changing an actual JANUS model.

No new measurement data is introduced to the source text corpus during
this experiment. This is an **adaptive layer selection candidate after
observing prior results**; therefore its performance on the reused probes
is DEVELOPMENT-ONLY, not a clean independent blind validation.
