# Janus Demiurge

> **Legacy experimental sandbox — not a flagship research claim.**

Janus Demiurge is an experimental Python project for exploring adaptive training loops, hyperparameter search, resource monitoring, evolutionary memory, and game-like agent simulations.

The repository is preserved because it contains useful implementation experiments and historical ideas that later informed more focused JANUS projects. It should be read as an **engineering sandbox**, not as evidence of autonomous general intelligence, physical prediction, or a validated scientific result.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## Current positioning

```text
PROJECT_CLASS = LEGACY_EXPERIMENTAL_SANDBOX
FLAGSHIP_RESEARCH = FALSE
HYPERPARAMETER_EXPERIMENTS = IMPLEMENTED
RESOURCE_MONITORING = IMPLEMENTED
AGENT_WORLD_SIMULATION = EXPERIMENTAL
FUTURE_EVENT_PREDICTION = NOT_CLAIMED
SCIENTIFIC_VALIDATION = NOT_ESTABLISHED
```

Historical module names and metaphors are retained for compatibility. They are not scientific claims.

## Main capabilities

- adaptive hyperparameter experiments;
- resource-aware training controls;
- evolutionary memory for previous configurations;
- swarm and Bayesian optimization experiments;
- background analysis modules;
- game-like Genesis agent simulation;
- Stable Diffusion integration experiments;
- CPU/GPU/system monitoring;
- SQLite-based event and metric storage;
- web visualization through the HRain interface.

A historical module named `tachyon_engine.py` is best understood as an **experimental performance/result forecasting component**. The repository does not claim precognition, retrocausality, or access to future physical information.

## Version 7.2.0 — 2026-03-29

Historical additions included:

- adaptive operating modes: `EXPLORE`, `EXPLOIT`, `SURVIVE`, `CHAOS`, `HUNT`;
- mode inertia;
- stagnation-driven exploration pressure;
- rollback to previously strong states;
- self-model-assisted mode selection;
- anti-collapse controls;
- adaptive parameter stabilization.

## Requirements

- Python 3.10–3.12
- Windows, Linux, or macOS
- NVIDIA CUDA GPU optional
- 8 GB RAM minimum; 16 GB recommended for larger experiments

## Installation

```bash
git clone https://github.com/Hawkar-usls/Janus-Demiurge.git
cd Janus-Demiurge
python -m venv venv
```

Activate the environment and install dependencies:

```bash
pip install -r requirements.txt
```

Run the main loop:

```bash
python core.py
```

## Configuration

Configuration lives in `config.py` and environment variables.

Selected variables:

| Variable | Purpose | Default |
| --- | --- | ---: |
| `JANUS_VOCAB_SIZE` | Vocabulary size | 257 |
| `JANUS_TRAIN_SIZE` | Training sequences | 5003 |
| `JANUS_VAL_SIZE` | Validation sequences | 1009 |
| `JANUS_STEPS_PER_CYCLE` | Steps per cycle | 1999 |
| `JANUS_SEEDS_PER_CYCLE` | Random seeds per cycle | 2 |
| `JANUS_BASE_BATCH_SIZE` | Base batch size | 128 |
| `JANUS_BLOCK_SIZE` | Sequence block length | 32 |
| `JANUS_BASE_DIR` | Data directory | `./janus_data` |
| `JANUS_DEBUG` | Debug mode | `0` |
| `JANUS_RESUME` | Resume saved state | `0` |

Optional subsystems can be disabled with environment variables such as:

```text
JANUS_SWARM_ENABLED=0
JANUS_BAYES_ENABLED=0
JANUS_META_ENABLED=0
JANUS_ADAPTIVE_TEST_ENABLED=0
JANUS_SUBCONSCIOUS_ENABLED=0
```

## Architecture

Key modules include:

- `core.py` — main orchestration loop;
- `config.py` — configuration;
- `environment.py` — training-data generation;
- `trainer.py` — model training;
- `memory.py` — experiment memory;
- `system_monitor.py` — system metrics;
- `janus_genesis/` — game-like agent world;
- `janus_character.py` — RPG state;
- `tachyon_engine.py` — historical-name forecasting experiment;
- `visionary.py` — image-generation integration;
- `subconscious.py` — background analysis experiments;
- `swarm_optimizer.py`, `bayes_optimizer.py`, `meta_model.py` — optimization experiments;
- `igpu_offload.py`, `cpu_offload.py` — resource offload;
- `janus_db.py` — SQLite persistence;
- `server.py` — HRain visualization server.

## Research boundary

This repository is intentionally **not** used as the evidence authority for the current flagship JANUS research lines. For externally reviewable work, see:

- [Janus-Fundamentum](https://github.com/Hawkar-usls/Janus-Fundamentum)
- [AIFC](https://github.com/Hawkar-usls/AIFC)
- [janus-io-public](https://github.com/Hawkar-usls/janus-io-public)
- [janus-distributed-ai-swarm](https://github.com/Hawkar-usls/janus-distributed-ai-swarm)

## License

MIT License.

## Author

Hawkar / Oleksandr Ahapov — Ukraine
