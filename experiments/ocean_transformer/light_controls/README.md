# JANUS Ocean LIGHT-007 — independent offline scientific controls

**Status: synthetic-only research unit tests. NO physical photon observations, IBM service sessions, QPU calls, or evidence of retrocausality.**

## Historical LIGHT source

- Original: [stochastic_light_interface_model.json, creation commit Jan 27 2026](https://github.com/Hawkar-usls/janus-meta-registry/blob/8fa51d5ec7b79a67f473613552e5740293857511/data/proofs/stochastic_light_interface_model.json), original Git blob SHA `d86db6212d62b23621fb023c0317f38b94c21ef4`.
- Later normalized JSON: Git blob SHA `901f0f094cf078115ad6b1b64f2cf6de639a4ff8`; preserve this as a separate fixture, never silently overwrite the original.
- Historical source is **Markdown-fenced JSON**, not an executable Python physical model. These fixtures verify the semantic payload and their provenance, not experimental truth.
- The January hypothesis, "Light is a noisy, multi-user API", describes a useful engineering analogy for the roles of photons, absorption, photobiological responses, external variations and time jitter.
- The historical use of "decoherence" for moving leaves/shadows mixes distinct concepts; classical jitter/occlusion, quantum decoherence and photosynthesis have different mechanisms. This protocol does not treat them as equivalent.

## Five separate reproducible tests

1. **LIGHT-CTRL-00 spectral energy** — exact analytic relation E = hc/lambda for 450, 660 and 730 nm from the historical record. Verify blue photons have higher energy than red and far-red. This does not demonstrate any biological photoreceptor response or encode software commands.
2. **LIGHT-CTRL-01 photon-counting noise** — 2048 seeded synthetic Poisson count bins at rates 4 and 12 counts/bin; a Fano-factor and mean-rate sanity check. This is one idealized independent-arrival model, *not* a universal law for coherent, thermal or quantum light and not a physical photon detector.
3. **LIGHT-CTRL-02 forward light delay** — a seeded classical pulse source drives a simulated detector with delay 3 bins, weak delayed spillover, and additive jitter. Train lag/levels only on t=16..511, keep t=512..639 unused, freeze a SHA-tagged prediction for t=640..1023, then compare held-out MAE to a constant baseline. Future input time or misaligned source must be rejected. No real independent timestamp, no physical speed-of-light measurement.
4. **LIGHT-CTRL-03 late-choice selection trap** — exactly 4096 seeded synthetic [A,C,B] bits. A is independent of C in *all original shots*, while late-B-based filtering generates a highly significant false association. Reuse original CTRL-006 QPU-005 Fisher test to show why postselection is forbidden. This is a demonstration of selection/collider bias, not an executed delayed-choice experiment.
5. **LIGHT-CTRL-04 historical provenance** — compare exact Git blob hashes of the original Markdown-fenced LIGHT and later JSON-normalized LIGHT; validate semantic equality. Also run the unchanged CTRL-006 historical banana/bridge/QPU-005 provenance check to preserve linkage.

## Reproduction (Python 3.11, stdlib only)

```bash
python -m unittest discover -v -s experiments/ocean_transformer/light_controls -p 'test_light_controls_007.py'
python experiments/ocean_transformer/light_controls/light_controls_007.py prepare --output artifacts/light007_precommit.json
python experiments/ocean_transformer/light_controls/light_controls_007.py score --input artifacts/light007_precommit.json --output artifacts/light007_forward_delay_score.json
python experiments/ocean_transformer/light_controls/light_controls_007.py all --output artifacts/light007_complete_report.json
```

Each output file is write-once. The separate CI also runs noise, selection and provenance controls and emits a SHA-256 artifact manifest. It has only GitHub read permission and deliberately clears IBM credentials; **no physical-provider workflow or preregistered QPU-005 source code is edited.**

## Future scientific tests (NOT EXECUTED)

Use a time-tagged photodiode or photon-counting detector, independently timestamped random LED modulations, controlled spectral/intensity and dark-count calibration, device latency checks, and predeclared train/test and directionality gates. Independent optical laboratory and a third-party data custodian are required for stronger future-to-past causal claims. The software simulation alone cannot establish communication from the future.

Any new physical protocol must be preregistered separately and cannot backdate or relabel synthetic fixtures as physical observations.
