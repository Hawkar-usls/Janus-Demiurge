# JANUS Keymaster — Mechanism Composition / Lockpick lane

This directory extends the existing Keymaster without changing its learning/attribution contract.

## Two independent lanes

- `janus_model/keymaster.py`: read-only repository collection for TRAIN_ONLY learning and attribution.
- `janus_model/keymaster_mechanism_composer.py`: deterministic proof-carrying mechanism composition.

The composition lane treats **Janus-Fundamentum as scientific authority**. It may search, combine, rank, and emit missing-interface gates, but it cannot promote a theorem, open D1, or claim P=NP.

## How branch pickup works

The scheduled workflow scans configured Fundamentum branch families (`main`, `codex/*`, `research/*`, `feature/*`) every two hours. It indexes authority-like JSON artifacts from `registry/` and `research/`.

A new result enters the authoritative composition graph only when it carries an explicit typed contract:

```json
{
  "schema": "janus.keymaster.mechanism.v1",
  "id": "...",
  "input_type": "...",
  "output_type": "...",
  "status": "PROVED",
  "semantics": "EXACT",
  "construction_poly": true,
  "state_poly": true,
  "reconstruction_poly": true,
  "verification_poly": true,
  "universal_scope": true,
  "roles": ["REPRESENTATION"],
  "authority": {}
}
```

PASS/PROVED-looking artifacts without this contract are placed in `normalization_queue`; they are not silently converted into edges.

## Search modes

The v0 engine performs forward, backward and meet-in-the-middle reachability over exact polynomial interfaces. It emits a `missing_interface_queue` for Lockpick work and attaches known scoped barriers when available.

A candidate or audit-pass mechanism may appear in the shadow graph, but never in the authoritative graph until Fundamentum promotes it.

## Scientific firewall

A complete graph path is **not a proof**. Every candidate path still requires independent theorem replay, source verification, and one total polynomial lifecycle bound in the original input length.

Permanent output ceiling:

```text
D1 = EMPTY
P_VS_NP = OPEN
automatic theorem promotion = false
```
