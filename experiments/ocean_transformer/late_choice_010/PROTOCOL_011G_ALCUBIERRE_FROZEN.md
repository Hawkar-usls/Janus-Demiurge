# JANUS-011G — Alcubierre warp metric from Einstein constraints: FROZEN protocol

Date 2026-11-11. Scientific class: **classical general relativity mathematical model only**. No warp apparatus, negative-energy material source, curved spacetime laboratory, or experimentally transmitted bit exists in this run.

## Literature and video

- M. Alcubierre, "The warp drive: hyper-fast travel within general relativity", Classical and Quantum Gravity **11**, L73 (1994). DOI 10.1088/0264-9381/11/5/001 ; original arXiv gr-qc/0009013.
- M. Alcubierre and F. S. N. Lobo, "Warp drive basics", arXiv:2103.05610 (2021): negative energy conditions, possible horizons and hypothetical links to closed timelike curves; these are not demonstrations of communication into the past.
- User reference: https://youtu.be/PwOk0GKDv9c . The video content/transcript could not be independently fetched, so no statements are attributed to the video, and no specific numerical values are inferred from it.

## Exact metric and derivation under stated assumptions

Coordinates (t,x,y,z), flat spatial metric gamma_ij=delta_ij, lapse alpha=1 in geometric units, shift beta^x=-v f(r), beta^y=beta^z=0; bubble center x_s(t), r=sqrt((x-x_s)^2+y^2+z^2), v=dx_s/dt constant at the snapshot. c=G=1 for Einstein constraints.

ds^2 = -dt^2 + [dx-v f(r)dt]^2 +dy^2+dz^2.

Extrinsic curvature with the shift-only derivative: K_ij = (partial_i beta_j + partial_j beta_i)/2 up to an overall convention sign (the contraction is sign-independent), K=partial_x beta_x, KijKij=(partial_x beta_x)^2+((partial_y beta_x)^2+(partial_z beta_x)^2)/2. The spatial Ricci scalar is R(3)=0. Hamiltonian constraint R(3)+K^2-KijKij=16 pi rho gives

rho_geo = - v^2/(32 pi) [ (partial_y f)^2+(partial_z f)^2 ].

For the physical velocity v_s and SI ENERGY density (J/m^3):

rho_E = -(c^2 v_s^2/(32 pi G)) * (df/dr)^2 * (y^2+z^2)/r^2
      = -(c^4/(32 pi G))*(v_s/c)^2*(df/dr)^2*sin^2(theta).

This is the local energy density seen by Eulerian observers only and its negativity in the wall violates the **weak** energy condition for this specific metric; it is NOT the full required stress-energy tensor or a demonstrated physical material source. No attempt at solving a specific positive-energy matter model is made.

Angular integral of sin^2(theta) is 8 pi/3. Integrate local Eulerian energy over spatial flat volume at a time slice:

E_slice = -(c^4/(12 G)) (v_s/c)^2 * I,
I = integral_0^infty r^2*(df/dr)^2 dr.

The integral is a **coordinate slice volume integral of a particular observer's local energy density**, not invariant ADM energy, gravitational conserved mass, engineering fuel required or a stable warp construction.

## Shape, fixed numbers, test boundaries

Use **Alcubierre original smooth compactish wall shape**:

f(r)= [tanh(sigma*(r+R))-tanh(sigma*(r-R))]/[2*tanh(sigma*R)].
sigma=1/Delta (Delta in meters, width parameter, NOT precise physical 10–90% thickness). Derivative exact:
f'(r)= sigma*[sech^2(sigma*(r+R))-sech^2(sigma*(r-R))]/[2*tanh(sigma R)].
f(0)=1, f->0 as r->infinity. Numerically stable sech^2 without overflow.

No optimization / fit after first outcome. Frozen cases:
- baseline R=100 m, Delta=10 m, beta=v_s/c =0, 0.1, 1, 2.
- thickness sensitivity fixed R=100m, beta=1, Delta=1, 10, 20m.
- radius sensitivity R=10m, 100m for beta=1, Delta=R/10.
- report exact dimensionless profile values (f(0), f(R)), center/boundary sample densities at y=R,z=0 (equatorial wall), and primary total E_slice in J plus absolute mass-equivalent |E|/c² (kg / Earth masses), **not measured energy**.

Numerical radial Simpson quadrature on r in [0,R+20 Delta] with 16,000 *even* subintervals, and independent numerical convergence audit at 8,000/16,000 intervals. Tail beyond 20 Delta exponentially suppressed at these baseline parameters; convergence threshold 1e-5 relative. Prove sign nonpositive, speed scaling beta², wall thickness approximate scaling R²/Delta only in thin-wall limit.

Along x direction, approximate coordinate null rays for constant v: dxi/dt= ±c - v_s*(1-f(|xi|)), xi=x-x_s. For beta>1 forward-coordinate component vanishes where f=1-1/beta; bisection for the FRONT positive axis branch, within the specified stationary constant-speed assumption. This is not a demonstration of a *global* event horizon nor closed timelike curves, and beta<=1 lacks the corresponding finite front root.

## Strict science gates

- This computation uses original GR geometry and the Einstein Hamiltonian constraint. It does NOT build a warp engine, exotic matter, a finite-energy stable solution, or a solution to quantum gravity.
- A superluminal effective coordinate velocity in the Alcubierre ansatz is not evidence of faster-than-light local motion; no physical bubble control or independent chronology.
- The WEC-negative wall is a *hypothetical* requirement and is not shown to be engineerable; the particular metric's negative densities must not be generalized to every proposed warp metric.
- A possible coordinate horizon is not an observational claim, and one warp bubble does not by itself transmit to a previously recorded event or establish a CTC. The link to physical retrocausality is hypothetical and needs additional global geometry and physically realizable stress-energy.
- No original source video transcript was accessed. No QPU, NAS or Docker containers modified. Frozen JANUS-PHYSICAL-010 and JANUS 011A-F remain unchanged.
- Registry record must append separate theory result JSON with source citations, exact model assumptions, quantitative CI, SHA digest and no-physics gate, not rewrite any prior conclusions.
