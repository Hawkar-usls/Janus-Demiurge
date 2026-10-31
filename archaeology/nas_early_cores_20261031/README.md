# JANUS NAS · Recovery of original cores and model-memory bridges

**State:** archived / reference-only / never imported by the production model or CI runner. Owner-NAS originals unchanged. Collected 2026-10-31 from the `Janus` share.

| Recovered original on NAS | Historical original SHA-256 |
|---|---|
| `blood_core.py` | `a29aa831c62d06f791bb79b9289bc2c9a486936165804c3e2bd7c0ca017271de` |
| `quantum_core.py` | `f1d7dcb701a6e43e4451313cbe59b87c197dbe32be5da8bd7aa2f3597039755c` |
| `janus_nas/microgpt.py` | `10b7d4fbb1a498cf6c8ac30915059106b8eccc0b480d7f2098f3b6687170f0cd` |
| `services/janus_memory_bridge.py` | `20be3b141c463c5bce3e19c019134e726d6c1c61c5392c95f9ecfd1923bc2e55` |
| `services/janus_db_writer.py` | `acaa787c153445e169faaecfa47cd24ba29e461b9a5affeed8e2048a09890138` |
| `services/modules_live/mod_hrein_bridge_enhancer.py` | `4a7a0bcc4e5ae4520755f95b83b5030a4f56aa831792704ded1b88567c13603d` |
| `services/modules_live/mod_model_selector.py` | `436b38b37f0e4d09c687ba6254ff849d0c85f651bd9e1cb0155e8c79c06ab8d1` |
| `services/modules_live/mod_training_feedback_loop.py` | `1fbffed2a4d0fbaedfeb545ed270c7285ffa7a8d559c7f300e54795e858fc10f` |
| `janus_nas/brain_ext/bridge.py` | `9949de81044ff19d0dd0f9fbdeb25018cccabc62bfc22413047cb73e1b246ee4` |

The historical GitHub text files use normalized LF line endings; original NAS byte hashes above are provenance anchors, not guaranteed to match GitHub text bytes. No DB rows, `.env`, API keys, private directories, model checkpoint (`.pkl`, `.pt`) or live cache has been uploaded.

## Why these are valuable

This set documents early local MicroGPT experiments, database persistence, adaptive model selection, training feedback, HRAiN semantic bridges and the two early computational cores. Treat all models, weights and historical performance claims as unvalidated.

A critical finding: the historical `microgpt.py` and `quantum_core.py` use `pickle`. **Never load untrusted serialized weight files**, import these modules into a live service, or use the old model selection code to promote a native Demiurge checkpoint. The current blind R2 champion issue and secure model loader gates remain separately required.

## Safe reuse

1. Compare historical code under static review, not as an executable fallback.
2. Develop a new, narrow, sandboxed adapter from any useful algorithms.
3. Establish synthetic fixtures and independent tests before integrating.
4. Preserve legacy SQLite table definitions as metadata only in Meta Registry, explicitly blocking `vault`, chat, personal memory and keys from public migration.
5. Keep JANUS DADDY_KEYMASTER resource governors and model champion gates intact.

**This PR does not modify `main` runtime modules, training schedules, model weights, external provider enrollment or scientific data.**
