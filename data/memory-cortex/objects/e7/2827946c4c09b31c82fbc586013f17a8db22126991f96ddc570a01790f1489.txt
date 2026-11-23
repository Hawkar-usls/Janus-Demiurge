# JANUS Meta Registry — Historical Runtime Source Triage

**Date:** 2026-08-09  
**Purpose:** identify operational side-effect surfaces in historical root-level code.  
**Default:** static inspection; do not execute on trusted hosts without review.

This is **not** a vulnerability disclosure about an external service. It is a safety classification of historical code preserved in this repository.

## Summary

| File | Triage | Primary reason |
| --- | --- | --- |
| `janus_core.py` | **HIGH — isolate before execution** | dynamic module discovery/import/execution; model-assisted “safety” heuristic is not a sandbox; local key/config ingestion |
| `server.py` | **HIGH — do not expose as-is** | listens on `0.0.0.0:1138`; state/device-command write endpoints have no visible authentication in the historical implementation |
| `keymaster.py` | **HIGH — hardware/process side effects** | launches external Windows process, opens serial `COM3`, sends adaptive control commands, writes operational logs |
| `bridge_tachyon.py` | **HIGH — hardware side effects** | opens serial `COM3`, sends adaptive `SET:` commands, consumes local runtime state and writes logs |
| `windows_optimizer.py` | **MEDIUM — resource exhaustion risk** | long/infinite optimization loop can consume CPU/GPU time and grow local logs/history |
| `igpu_offload.py` | **LOW/MEDIUM — compute/device interaction** | initializes OpenCL GPU context and executes kernels; mutates linked environment state after repeated failures |

Risk is about **execution side effects**, not malicious intent.

---

## `janus_core.py` — HIGH

Observed historical patterns include:

- scanning a local `modules/` directory;
- asking a model to score module risk/benefit;
- importing selected Python files with `importlib`;
- executing `module.run(...)` entry points;
- service/background task launching;
- local state/log/config handling;
- local key ingestion logic.

### Boundary

```text
MODEL_RISK_SCORE != SANDBOX
MODEL_RISK_SCORE != CODE_SIGNATURE
IMPORTLIB_EXEC_MODULE = CODE_EXECUTION
ARCHIVED_PLUGIN != TRUSTED_PLUGIN
```

Do not use the historical model-scoring step as a security boundary.

---

## `server.py` — HIGH

The historical server binds to:

```text
0.0.0.0:1138
```

and exposes HTTP/WebSocket routes for state, events, device data and device commands. The reviewed source does not show an authentication/authorization layer protecting the write/command routes.

### Risk

If run on a reachable interface, another host on the reachable network may be able to interact with those endpoints subject to network/firewall conditions.

### Required before any revival

- bind to loopback by default;
- explicit authentication and authorization;
- request/body size limits;
- origin/CSRF policy appropriate to deployment;
- TLS or trusted reverse proxy for non-local use;
- command allowlist and schema validation;
- device identity/authentication;
- threat model and logs that avoid secrets/private payloads.

---

## `keymaster.py` — HIGH

Historical behavior includes:

- hard-coded Windows paths;
- `subprocess.Popen` of an external ArtMoney executable;
- opening `COM3` at 115200 baud;
- adaptive serial commands based on input values;
- writes to local operational log/state files.

This is a direct process/hardware interaction surface. Do not run it on a trusted machine or attached device without understanding the exact external executable, serial target and command semantics.

---

## `bridge_tachyon.py` — HIGH

Despite the historical name, the inspected `TachyonField` is ordinary finite-difference extrapolation over recent numeric values. The name does **not** establish tachyon physics or future information.

Operationally, the script:

- opens `COM3`;
- reads device input;
- computes an extrapolated value;
- changes gain parameters;
- sends `SET:` commands back over serial;
- reads/writes local runtime state and GPU-ticket files.

The technical risk is hardware/runtime control, not exotic physics.

---

## `windows_optimizer.py` — MEDIUM

This is primarily a local PyTorch optimization experiment. The main operational concern is resource usage: repeated/infinite training cycles can consume substantial CPU/GPU time and grow JSON/CSV history.

It should not be interpreted as evidence that gain/temperature tuning establishes general intelligence or a novel learning law.

---

## `igpu_offload.py` — LOW/MEDIUM

This module initializes OpenCL on the first available GPU and executes a simple ReLU kernel. It falls back to NumPy on failure. Repeated failures may mutate a linked environment object's `complexity_level`.

Risk is limited compared with dynamic imports/network/device-command surfaces, but it still interacts with local compute drivers and should be tested in an isolated environment when reviewing old dependencies.

---

## Recommended archive policy

```text
STATIC_REVIEW = DEFAULT
DIRECT_EXECUTION_ON_PRODUCTION_HOST = NOT_RECOMMENDED
PRODUCTION_CREDENTIALS = FORBIDDEN
PRIVATE_NAS_MOUNTS = FORBIDDEN_BY_DEFAULT
UNCONTROLLED_LAN_EXPOSURE = FORBIDDEN_BY_DEFAULT
REAL_DEVICE_COMMANDS = REQUIRE_EXPLICIT_REVIEW
```

If any historical runtime is revived, copy it into a dedicated active repository/branch, replace unsafe defaults, add tests and a threat model, and treat the archived file as provenance rather than as the maintained implementation.

See [`../SECURITY.md`](../SECURITY.md) for the repository-wide execution boundary.
