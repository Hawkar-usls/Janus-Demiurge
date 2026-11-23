# JANUS-LOGOS-001 · Universal Structure (R0)

This repository module is a **scoped numerical reproduction of known Feigenbaum universality**. It is associated with the philosophical [God Code](../../data/JANUS-GOD-CODE-v1.0.json) dossier without assigning theological meaning to the calculation.

## What was actually done

The generator computed superstable critical-point periods 2^n to n=8 for the logistic map `r*x*(1-x)`, a distinct sine map `a*sin(pi*x)` (both quadratic critical maximum), and a quartic map `1-a*x^4` (outside the same universality class). Parameters were found by scanning and bisection at 85-digit precision, with no Feigenbaum constant in the search procedure. Ratios were scored **after** root recovery.

Observed final estimated delta: logistic **4.669191002485**, sine **4.669151333605**, quartic **7.285086100551**. The quartic result is **not supposed** to equal the quadratic-class constant. The numerical values approximate established results, not new physics.

The independent witness imports no generator code, uses Python float64 `math`, re-iterates every reported superstable orbit, checks minimal period and numerical ratios, and rejects (1) an altered sine root, (2) a falsely relabeled quartic control. It was executed locally with `PASS_SCOPED_NUMERICAL_UNIVERSALITY_REPLICATION`; a second GitHub Actions runner must independently confirm it.

## Reproduce

```bash
python -m pip install 'mpmath==1.3.0'
python research/logos_001/generate.py --depth 8 --out /tmp/logos001.json
python research/logos_001/verify.py /tmp/logos001.json --self-test
cmp /tmp/logos001.json data/JANUS-LOGOS-001-R0-RESULT-v1.0.json
```

The independent verifier needs Python standard library only; the generator requires mpmath. Actions jobs run on **separate GitHub-hosted workers**. Actions have `contents: read` permission and no schedule. No paid AI model, Rowan experiment, NAS resource, or deployment is touched.

## Scientific boundaries and prospective next phases

- R0: **Numerical** replication of previously known mathematical universality, not independent physical experimentation.
- R1 (not run): symbolic law discovery on properly licensed and held-out scientific benchmarks. Freeze target selection and leakage controls before any trial.
- R2 (not run): match budget for 2/3/4/adaptive agent roles. Include neutral role-name randomization and precommitted metrics.
- R3 (not run): truly independent laboratory/instrument or external verified computational pipeline.
- The frozen protocol was written **after** the first local exploratory R0 run. Do not claim that first run was preregistered.
- None of these results demonstrates a divine programmer, validates simulation ontology, or settles P vs NP.

Sources: [Wolfram MathWorld — Feigenbaum constant](https://mathworld.wolfram.com/FeigenbaumConstant.html); [2020 numerical study of Feigenbaum delta spectrum](https://www.sciencedirect.com/science/article/pii/S100757042030160X).
