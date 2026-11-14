# ESSENCE v1.6.3 — bounded native CPU layer search

The full 5-Linear dynamic INT8 candidate lost next-token argmax fidelity
(<97% on both cohorts); the four-FFN-layer variant recovered to 96.35% on
the historical anchor and 97.14% on public probes, still below the original
prespecified minimum. This experiment searches all **15 nonempty subsets**
of those four native Transformer FFN Linear layers, never the tied output
head or embeddings.

Each candidate runs in an **independent CPU Python process** against the same
immutable repository-committed trained checkpoint and source/probe Git blobs.
Tested values are historical anchor and public fixed text probes frozen in
Meta Registry at ESSENCE v1.6, not external blinded controls.

The search only considers a candidate if **both** cohorts achieve at least
97% original top-1 agreement and no >0.5% loss regression, serialized model
state_dict size improves at least 4%, and CPU median forward latency does not
regress by more than 15%. These are **development engineering thresholds**,
not production model admission. Winners are ordered by saving then by worst
loss deterioration. The summary always marks independent blind and live
rollback as unproven, and automatic promotion as false.

Each JSON receipt records original SHA-256, exact selected layer names,
actual number of PyTorch `nn.quantized.dynamic.Linear` modules, tied FP32
output-head integrity, next-token CE/argmax agreement, current/peak CPU RSS,
size/latency and a SHA-256 evidence digest. The user-facing working
`promoted.pt` is never overwritten or trained.

**Interpretation limits:** choosing from 15 masks based on these previously
seen public probes is selection on the evaluation data. It cannot be
represented as independent generalization. A new externally managed,
unseen cohort and genuine service rollback must be obtained before any
promotion decision. CPU memory may still be confounded by allocator
retention during same-process conversion, so packed model size is separate
from runtime RSS.
