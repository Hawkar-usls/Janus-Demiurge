# JANUS Ocean OPEN-CAUSALITY-009 — NOAA, drand and GLOW

**PROSPECTIVE SOFTWARE RESEARCH, NOT A PHYSICAL RETROCAUSALITY CLAIM**

Calendar: Eight target days, November 12–19, 2026 (UTC). No substitution,
post-hoc retuning or best-of-N selection. The original physical QPU-005,
LIGHT-008 and earlier banana/LIGHT experiments are untouched.

## OPEN-LIGHT-009A — real public NOAA SURFRAD

Read official Bondville Illinois (bon) 1-minute data from
https://gml.noaa.gov/aftp/data/radiation/surfrad/bon/

Use four historical days ending four days before the preparation run.
Column 9 (zero-index 8) is downwelling shortwave GHI in W/m²;
column 10 is its QC flag. Require all 1440 rows for every source day,
QC=0 and at least 45/60 valid points per hourly mean, or refuse the day.

At 03:17 UTC on date D, freeze 24 hourly predictions for target D+2.
Models: (a) a fixed physics-informed transparency/diurnal hybrid,
(b) last available same-hour GHI persistence,
(c) four-day same-hour mean,
(d) geometric Haurwitz clear sky. The hybrid is NOT a trained
transformer. It is a fixed benchmark for the future model.
No TARGET observations are accessed during preparation.

At 03:17 UTC on date D+5, retrieve the exact unique original
GitHub Actions artifact for target D+2, require a server timestamp before
the target day, then measure all 24 hours of MAE (W/m²) against the
real NOAA release. Require at least a 3-day disclosure embargo.
Missing source days/labels fail closed, not silently zero.
Archive NOAA source SHA-256 for independent reanalysis.

## OPEN-FUTURE-009B — signed independent future drand

Eight cohorts of 128 distinct future Quicknet rounds at 60-second
spacing, first round at 08:00 UTC each target day; 1024 total.
Two days before the target, run the frozen, previously trained
JanusTinyTransformer from GitHub run 42596763409 using only publicly
known round and position metadata. This checkpoint was trained on
synthetic quantum/Born-rule examples, NOT drand data; chance performance
is expected. Freeze all 128 probabilities and threshold bits as one
write-once GitHub artifact with verifiable publication time.

Later at 12:48 UTC, retrieve ONLY that original dated artifact and
use drand-client@1.4.2 with pinned Quicknet BLS verification to fetch
all 128 exact target rounds. Refuse missing/incorrect signatures or
late publication. Score raw accuracy, exact binomial p, and Brier
against 0.25 chance reference without postselection.

One fixed 1024-bit pooled one-sided threshold: 562/1024 successes
gives p < 0.001 under the independent fair-bit null. Eight cohorts
must be complete; an early anomaly is not a stopping rule or proof
of retrocausality. A public random beacon is not a separate
physical quantum receiver or independent later free choice
coupled to an earlier measurement.

After November 19, heavy daily future-precommit jobs are skipped.
After November 22, heavy NOAA verification jobs are skipped.

## OPEN-GLOW-009C — persistent luminescence optical memory

SUNLU SDS dated 2023 identifies strontium aluminate at 5 wt.% in
one glow-PLA composition; this does not certify every modern SUNLU
spool or its actual Eu/Dy dopant content. Research on
SrAl2O4:Eu2+,Dy3+ shows a broad excitation band and green ~520nm
afterglow, with multi-component decay.

Fixed illustrative scenario:
- Sample 10×10×1mm, density 1.23g/cm³: ~0.123g polymer composite,
  of which ~6.15mg strontium aluminate if 5 wt.% applies.
- Excitation 365nm, 1mW absorbed at surface BEFORE losses, 5min;
  assumed optical absorption 10%, delayed photon yield 5%,
  effective time constant 900s.
- Predicted TOTAL green light output on switch-off ~0.994866µW,
  at 1min 0.930704µW, 5min 0.712853µW,
  10min 0.510781µW.
- With 1% detector capture, responsivity 0.3A/W and 100kOhm
  transimpedance, example initial output ~2.985mV; 10% ~29.85mV.
- One fixed 3% ASSUMED broadband-to-365nm-equivalent fraction lets
  a NOAA predicted GHI timeline drive a synthetic phosphor-memory
  equation, then later observed GHI drives the same equation.
  This tests sensitivity to uncertain inputs, NOT actual
  measured glow output and NOT an empirically known UV fraction.

Physical model: dN/dt = absorbed-pump-photon-rate * stored-yield - N/tau,
and afterglow green power = N*(hc/520nm)/tau.
Its long tail contains PREVIOUS illumination memory; failure to model
it could mimic temporal anomalies. Single tau=900s is a simplifying
scenario; published multi-exponential kinetics cannot be reduced to
a universal one-tau model without an actual material calibration.
Unknown absorption, phosphor distribution, sample geometry, trapping,
optical collection and sensor responsivity prevent claims about real
SUNLU brightness.

To validate experimentally: dark enclosure, known LED irradiation,
the time of LED switch-off, green-filtered calibrated photodiode,
blank PLA control, and measurement of actual phosphor decay. Shield
eyes and skin from UV and avoid unsupported high-power emitters.

## Audit and safety

Run offline tests with Python 3.11:
python -m unittest discover -v -s experiments/ocean_transformer/open_causality_009 -p test_open_causality_009.py

Sources and expected evidence:
- NOAA: https://www.gml.noaa.gov/data/dataset.php?item=bnd-surfrad-minute-2026
- drand: https://docs.drand.love/developer/http-api/
- SUNLU SDS: https://sunlu.kyiv.ua/content/files/21_msds_sunlu_pla_grow_in_the_dark_filament-99280517.pdf
- Persistent luminescence: https://www.edinst.com/resource/application-note-kinetics-of-persistent-luminescence-phosphors/

Each forecast must have an append-only external timestamped GitHub artifact
before its targets, retained raw source hashes, and independent late review.
No original QPU-005 code, local NAS, actual PLA sensor, physical optical lab,
or quantum provider are touched by these workflows.
