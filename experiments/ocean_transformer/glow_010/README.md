# JANUS Ocean GLOW-010 — actual laboratory data, honest timescale separation

**Results:** REAL PUBLISHED MATERIALS MEASUREMENTS ANALYZED. NO physical SUNLU
PLA Glow sample was ever accessed. No evidence for retrocausality. Original
JANUS QPU-005, OPEN-009, BANANA, LIGHT-007/008 and their frozen registrations
are not edited.

## 1. Macroscopic persistent afterglow (real published fitted lifetimes)

Original laboratory publication: Edinburgh Instruments, Georgios Arnaoutakis,
*AN_P28 — Kinetics of Persistent Luminescence Phosphors*, 2017,
https://edin.b-cdn.net/wp-content/uploads/2023/03/Luminescence-Phosphors_App28.pdf

Experiment: Glotech SrAl2O4:Eu2+,Dy3+ micro-crystalline powder, excited 300–350 nm
for 300 s, monitored at 520 nm for 3600 s. Table 1 publishes six sets of
**four fitted decay constants**, plus reported average lifetimes:

- Excitation 300 nm: τ = 1.29, 29.27, 221.1, 1955 s; mean 1776.99 s
- Excitation 310 nm: τ = 0.94, 26.66, 172.6, 1089 s; mean 849.53 s
- Excitation 320 nm: τ = 5.32, 48.04, 221, 1137 s; mean 803.19 s
- Excitation 330 nm: τ = 10.47, 57.52, 240.9, 1170 s; mean 773.17 s
- Excitation 340 nm: τ = 9.75, 54.38, 229.3, 1115 s; mean 719.85 s
- Excitation 350 nm: τ = 11.58, 59.84, 243.6, 1167 s; mean 757.25 s

Their four-component fits report χ²=1.16–1.88; their three-component fits
report χ² >3. This is the **original authors' finding**, not an
independent re-fit by JANUS. Our previous illustrative single constant
τ=900 s differs from those six reported means by MAE 245.667 s.
This is NOT an afterglow intensity prediction MAE; it compares reported
lifetime parameters only. Original amplitudes A_i and per-second raw
intensities are unavailable from the publication table alone. Therefore
our experiment **does not invent 3600 fake observations or declare a
mono-versus-bi-versus-power winner for macroscopic afterglow**.

Reproducible:
python -m unittest discover -v -s experiments/ocean_transformer/glow_010 -p test_published_lifetimes_010.py
python experiments/ocean_transformer/glow_010/published_lifetimes_010.py --output result_literature.json

## 2. Open licensed raw laboratory nanosecond photoluminescence

Full public source:
https://doi.org/10.5281/zenodo.6991932
Article: Delgado et al., *Advanced Photonics Research* 3 (2022) 2100179,
https://doi.org/10.1002/adpr.202100179
**License:** CC BY 4.0 (credit original authors); original archive
'loadingcurve.zip' MD5 423e3e457d3458a0aac0b20365ebfd4b.

Raw time vs observed intensity arrays from source files
'Decaydata/sample{1,2,3}_biexp_w_bg.txt':
- S1: Eu doped SrAl2O4, **no Dy/B**;
- S2: Eu+B doped, **no Dy**;
- S3: Eu+Dy doped, closest nominal composition to SrAl2O4:Eu,Dy
  but **not the SUNLU PLA composite**.
- Each is 441 original points at t=105–6705 **NANOSECONDS**, with source
  background-corrected intensity values, including negative observations.

Each of the 3 samples independently:
- first 264 chronological points train only;
- 177 consecutive later points held out;
- fit 3 predeclared formulas with nonnegative bounded parameters and
  train-only weights 1/sqrt(max(Iobs,25)):
  1. **mono**: b + A exp(-t/τ)
  2. **bi**: b + A1 exp(-t/τ1) + A2 exp(-t/τ2)
  3. **power**: b + A(1+t/t0)^(-α)
- bounded multi-start SciPy nonlinear least squares, independent of
  future held-out labels (verified adversarial unit test).
- Evaluate unweighted mean absolute errors on ALL held-out samples,
  plus full-unit weighted RMSE. Biexp has 5 parameters, mono has 3,
  power has 4. These hyperparameters and dataset comparison were selected
  retrospectively; the study is **exploratory not prospectively confirmed**.

One evaluated run (CI #42720254895) returned MAE:

| Real lab sample | mono | biexp | shifted power |
| --- | ---: | ---: | ---: |
| S1 Eu | 2354.456 | 638.879 | **360.362** |
| S2 Eu+B | 820.850 | 333.875 | **225.446** |
| S3 Eu+Dy | 59.784 | 17.940 | **7.962** |

The shifted power law generalized to the later part of each curve
better on this selected split, despite biexp fitting training data
better. A deterministic 12-point block bootstrap gives exploratory
paired MAE improvement CIs but does NOT create independent sample
replication or eliminate post-hoc model-selection bias.

**CRITICAL DISTINCTION:** These time scales are nanoseconds and measure
FAST photon-excited emission, not green delayed luminescence caused by
trap release over seconds to hours. None of their fitted τ parameters
are suitable as the real decay kernel for SUNLU PLA Glow.

Run:
python -m pip install 'numpy==2.2.6' 'scipy==1.15.3'
python -m unittest discover -v -s experiments/ocean_transformer/glow_010 -p test_fit_real_lab_decay_010.py
python experiments/ocean_transformer/glow_010/fit_real_lab_decay_010.py --output real_fast_fit.json

## 3. Source acquisition checks and known blocker for real slow-time curves

Additional open 2026 Zenodo material:
https://zenodo.org/records/18862107
A 13.4MB archive contains 29 modern OriginLab `.opju` projects,
published MD5 3a11f363c6ce6cb3d465611682577662. SHA-256 of archive
7ed5ad435d37d217b1a2fd46ee8909c1e86424efeac6155106b4238d8695d40c.

The zip was downloaded/verified and all files inventoried using GitHub
Actions. A standalone open-source liborigin command-line reader pinned
to git b053b99c56cc33d87866d31c4ebbd10e1066a043 failed to parse
three tested modern `.opju` project files. This is an **explicit decoder
limitation, not a fabricated zero intensity**. We do not attempt
undocumented binary parsing or claim successful extraction.

To fit real **macroscopic afterglow** curves next, a trustworthy
export to CSV (e.g. via Origin Viewer/Origin) is required, then evaluate
the same three models with a declared split and unknown amplitude,
background, excitation-wavelength and temperature controls. Before
an independent replication, no specific decay family is declared
universally correct.

## No future-signal or quantum-hardware claims

Independent physical signal timing, traps and future-choice controls
remain separate. For true retrocausal tests, precommit early detector
readout before an independently random later physical intervention with
external timestamps and no postselection. This study makes no such
physical claim. IBM QPU minutes = 0; user NAS, ESP32 and other hardware
are untouched.
