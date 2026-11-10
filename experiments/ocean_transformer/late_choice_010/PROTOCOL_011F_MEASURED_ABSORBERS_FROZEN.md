# JANUS-011F — measured optical absorbers, frozen protocol

Date: 2026-11-11. This is historical optical n,k data plus theoretical forward-optics and false-precursor controls. NO physical backwards-time signal claimed.

## Original external source (pinned before numerical replay)

Johnson & Christy, Optical Constants of the Noble Metals, Phys Rev B 6 4370 (1972), DOI 10.1103/PhysRevB.6.4370, measured optical n,k by reflection/transmission on evaporated gold and silver films (roughly 18.5 to 50 nm). Original open CC0 refractiveindex.info database curated by Polyanskiy, source commit SHA e6d15e364f70de1cad8a96a20f75689f2fba8b21 (2026-11-07). Source paths: database/data/main/Au/nk/Johnson.yml and database/data/main/Ag/nk/Johnson.yml. Exact pinned original downloadable URL prefix: https://raw.githubusercontent.com/polyanskiy/refractiveindex.info-database/e6d15e364f70de1cad8a96a20f75689f2fba8b21/database/data/main/ . Require SHA256 of downloaded original source bytes, complete monotonically increasing tabulated nk data, k>=0, same exact primary wavelengths in both files. If a source file is missing or malformed, fail closed.

This historical spectral source provides no impulse-response measurement, future hardware intervention or independent temporal witness. It cannot by itself test a physical signal from future to past. Source was located and previewed publicly before this freeze; freeze applies to 011F numerical method, NOT to genuinely blinded selection of prior unseen material data.

## Fixed numerical comparison

Primary: independent exact original wavelength samples lambda=0.4509,0.5486,0.7045,0.8920 micrometers; freestanding homogeneous planar vacuum-metal-vacuum film, d=0.04 micrometers (40 nm), coherent normal incidence, no substrate/roughness/scattering. Secondary thickness sensitivity d=0.03 and 0.05 micrometers, both nominally comparable to original evaporated film ranges. Calculated film outputs ARE NOT Johnson Christy directly measured reflectance/transmittance.

Complex optical index N=n+i*k, field phase convention exp(i*kz-i*omega*t), alpha=4*pi*k/lambda and intensity skin depth=1/alpha. Fresnel coefficients r01=(1-N)/(1+N), r12=-r01, t01=2/(1+N), t12=2N/(1+N), beta=2*pi*N*d/lambda, z=exp(i*beta). Exact single homogeneous slab r=(r01+r12*z*z)/(1+r01*r12*z*z), t=t01*t12*z/(1+r01*r12*z*z), R=abs(r)^2, T=abs(t)^2, A=1-R-T. Vacuum on each side. Must show 0<=R,T,A<=1 up to floating precision, sum=1. A is model absorption, not measured photon survival. No one-sided approximate surface formula.

Dispersion: compare all input n,k across wavelengths and calculate an explicitly DESCRIPTIVE numerical group-delay derivative d phase(t)/d angular-frequency, from local neighbor sample points after phase unwrap. Do not equate group delay with earliest causal arrival, nor treat finite-band n,k as a full verified Kramers Kronig reconstruction. Spectral tails and complete time-domain impulse are not known. Negative model group delay, if obtained, does not prove physical early energy or information.

## Frozen false-precursor controls

Exact delayed unit impulse at time tau=5 has zero true output before tau. Truncated frequency inverse using omega between minus pi/2 and plus pi/2 gives bandlimited sinc response sin(Omega*(t-tau))/(pi*(t-tau)) and can be nonzero before tau. Five-sample centered moving average reads 2 future samples and yields spurious pre-impulse output at tau-2, whereas trailing causal average has zero before tau. Misassigning clock timestamp -6 shifts true tau=5 to displayed t=-1 without changing physics. Full declared time grid -8..12; no selecting favorable pre-event windows.

## Physical acceptance

Measured n,k constraints: yes. Derived passive single-film spectral attenuation/reflection: yes, under ideal slab assumptions. Independent advanced Green coefficient or absorber radiation boundary uniquely determined from these data: NO. Physical time-domain impulse measured: NO. Genuine late choice QRNG after independently committed early A: NO. Actual retrocausal physical signal: NO. An advanced Green choice is not derived from ordinary thin film attenuation. No after-the-fact fit of lambda, pulse filtering, optical thickness or clock offset to manufacture future signals.

Sources: Johnson & Christy DOI 10.1103/PhysRevB.6.4370; Wheeler & Feynman 1945 DOI 10.1103/RevModPhys.17.157; full-band optical causality/Kramers-Kronig requires analytic extrapolation outside finite spectrum.

No modifications to original sealed JANUS-010, past 011A-E, NAS, containers, QPU, or confidential user material. Code and derived results in a draft PR and append-only JSON, no raw copyrighted paper content redistributed.
