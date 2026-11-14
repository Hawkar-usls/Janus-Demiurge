#!/usr/bin/env python3
"""JANUS-011G: Alcubierre geometry from Einstein Hamiltonian constraint.

Mathematical stress-energy requirements, NOT an engine or physical time travel.
Original: Alcubierre (1994) CQG 11 L73, DOI 10.1088/0264-9381/11/5/001.

Geometric ADM: flat gamma, unit lapse, shift beta_x=-v_s f.
K^2-KijKij=-v_s^2/2 * [(d_y f)^2+(d_z f)^2] at c=G=1.
rho_E=-c^4/(32*pi*G)*(v_s/c)^2*(df/dr)^2*sin^2(theta).
E_slice=-c^4/(12*G)*(v_s/c)^2*int_0^infty r^2*f_r^2 dr.

Do NOT equate coordinate-slice energy to invariant ADM mass or engineering fuel.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path

G = 6.67430e-11
C = 299792458.
M_EARTH = 5.9722e24
M_SUN = 1.98847e30
N_FINE=16000
N_COARSE=8000
SCHEMA="janus.physical011g.alcubierre_einstein_negative_energy.v1"

def require_physical(R, delta, beta):
    if any(not math.isfinite(v) for v in (R,delta,beta)):
        raise ValueError("FINITE_PARAMETERS_REQUIRED")
    if R<=0 or delta<=0 or beta<0:
        raise ValueError("R_POSITIVE_DELTA_POSITIVE_BETA_NONNEGATIVE")

def sech_sq(x):
    """Stable 1/cosh(x)^2 for arbitrarily large |x|."""
    q=math.exp(-2*abs(x))
    return 4*q/(1+q)**2

def shape_f(r,R,delta):
    if r<0:raise ValueError("RADIUS_NONNEGATIVE")
    require_physical(R,delta,0)
    sig=1./delta
    return (math.tanh(sig*(r+R))-math.tanh(sig*(r-R)))/(2*math.tanh(sig*R))

def df_dr(r,R,delta):
    if r<0:raise ValueError("RADIUS_NONNEGATIVE")
    require_physical(R,delta,0)
    sig=1./delta
    return sig*(sech_sq(sig*(r+R))-sech_sq(sig*(r-R)))/(2*math.tanh(sig*R))

def simpson_integral(R,delta,n):
    require_physical(R,delta,0)
    if type(n) is not int or n<4 or n%2:raise ValueError("EVEN_SIMPSON_SUBINTERVALS_REQUIRED")
    upper=R+20*delta
    h=upper/n
    def val(r):
        d=df_dr(r,R,delta)
        return r*r*d*d
    total=val(0)+val(upper)
    for i in range(1,n):
        total+=(4 if i%2 else 2)*val(h*i)
    return h*total/3.

def wall_density(R,delta,beta,theta=math.pi/2):
    require_physical(R,delta,beta)
    derivative=df_dr(R,R,delta)
    return -C**4/(32*math.pi*G)*beta**2*derivative**2*math.sin(theta)**2

def energy_from_integral(radial_i,beta):
    if radial_i<0 or not math.isfinite(radial_i) or beta<0:
        raise ValueError("INVALID_RADIAL_INTEGRAL")
    return -(C**4/(12*G))*beta*beta*radial_i

def possible_forward_axis_horizon(R,delta,beta):
    """Only a 1D comoving coordinate null ray stagnation; not global horizon."""
    require_physical(R,delta,beta)
    if beta<=1:return None
    target=1-1/beta
    hi=R+20*delta
    if not shape_f(0,R,delta)>target>shape_f(hi,R,delta):
        raise ValueError("NO_BRACKET_FOR_FORWARD_COORDINATE_HORIZON")
    low=0.
    for _ in range(100):
        mid=(low+hi)/2
        if shape_f(mid,R,delta)>target:
            low=mid
        else:
            hi=mid
    root=(low+hi)/2
    return {"positive_x_axis_r_m":root,
            "f_shape_at_zero_coordinate_outgoing_speed":shape_f(root,R,delta),
            "forward_ray_comoving_speed_m_per_s":C*(1-beta*(1-shape_f(root,R,delta))),
            "strict_status":"coordinate outgoing ray stagnation in frozen constant-speed 1D model, NOT global causal event horizon, NO CTC proven"}

def case(R,delta,beta):
    require_physical(R,delta,beta)
    I_coarse=simpson_integral(R,delta,N_COARSE)
    I_fine=simpson_integral(R,delta,N_FINE)
    if abs(I_coarse-I_fine)/max(I_fine,1e-300)>1e-5:
        raise ValueError("RADIAL_QUADRATURE_CONVERGENCE_NOT_PROVEN")
    E=energy_from_integral(I_fine,beta)
    density=wall_density(R,delta,beta)
    return {
       "bubble_R_m":R,
       "shape_wall_delta_parameter_m":delta,
       "shape_sigma_inverse_m":1/delta,
       "speed_beta_v_over_c":beta,
       "speed_m_per_s":beta*C,
       "shape_at_center_f0":shape_f(0,R,delta),
       "shape_at_wall_fR":shape_f(R,R,delta),
       "d_shape_dr_at_wall_per_m":df_dr(R,R,delta),
       "wall_energy_density_J_per_m3_at_equator":density,
       "wall_energy_density_J_per_m3_on_motion_axis":wall_density(R,delta,beta,theta=0),
       "all_eulerian_local_energy_density_nonpositive_for_radial_profile":True,
       "radial_integral_I_m":I_fine,
       "simpson_coarse_radial_integral_I_m":I_coarse,
       "radial_numerical_relative_convergence":abs(I_coarse-I_fine)/max(I_fine,1e-300),
       "coordinate_slice_integrated_local_energy_J":E,
       "negative_energy_magnitude_J":abs(E),
       "negative_energy_magnitude_mass_equivalent_kg":abs(E)/C**2,
       "negative_energy_magnitude_mass_equivalent_earth_masses":abs(E)/(C**2*M_EARTH),
       "negative_energy_magnitude_mass_equivalent_solar_masses":abs(E)/(C**2*M_SUN),
       "thin_wall_approx_radial_I_R2_over_3Delta_m":R*R/(3*delta),
       "approximation_relative_error":(I_fine-R*R/(3*delta))/I_fine,
       "forward_axis_coordinate_null_stagnation":possible_forward_axis_horizon(R,delta,beta),
       "source_stress_energy_tensor_fully_constructed":False,
       "physically_existent_negative_energy_source_supplied":False
    }

def evaluate():
    primary=[case(100.,10.,beta) for beta in (0.,.1,1.,2.)]
    thin=[case(100.,delta,1.) for delta in (1.,10.,20.)]
    radius=[case(R,R/10,1.) for R in (10.,100.)]
    by_beta={p["speed_beta_v_over_c"]:p for p in primary}
    b01=by_beta[.1]["coordinate_slice_integrated_local_energy_J"]
    b1=by_beta[1.]["coordinate_slice_integrated_local_energy_J"]
    b2=by_beta[2.]["coordinate_slice_integrated_local_energy_J"]
    if not (abs(b01/b1-.01)<1e-13 and abs(b2/b1-4)<1e-13):
        raise AssertionError("SPEED_SQUARED_SCALING_FAILURE")
    if by_beta[0.]["coordinate_slice_integrated_local_energy_J"]!=0:
        raise AssertionError("ZERO_SPEED_SHOULD_HAVE_ZERO_ENERGY")
    return {
       "schema":SCHEMA,
       "scientific_class":"CLASSICAL_EINSTEIN_HAMILTONIAN_CONSTRAINT_MATHEMATICAL_ANZATZ_ONLY",
       "original_literature":{
         "Alcubierre_1994_DOI":"10.1088/0264-9381/11/5/001",
         "original_archived_preprint":"gr-qc/0009013",
         "Alcubierre_Lobo_2021":"arXiv:2103.05610",
         "user_linked_video":"https://youtu.be/PwOk0GKDv9c",
         "user_video_verified_transcript_available":False
       },
       "metric":"ds^2=-c^2dt^2+[dx-v_s*f(r)*dt]^2+dy^2+dz^2, r=sqrt((x-x_s)^2+y^2+z^2)",
       "Einstein_3plus1_Hamiltonian_derivation":{
         "flat_spatial_Ricci_3":0,
         "lapse_alpha_geometric_units":1,
         "shift_beta_x_geometric_units":"-v_s*f(r), with c=1",
         "K_ij_contraction":"K^2-KijKij=-v_s^2/2*((partial_y f)^2+(partial_z f)^2)",
         "Einstein_equation_constraint":"R(3)+K^2-KijKij=16*pi*rho_geom",
         "SI_Eulerian_local_energy_density":"rho_E= -(c^4/(32*pi*G))*(v_s/c)^2*(df/dr)^2*sin^2(theta)",
         "angular_integral_sin_squared_theta":8*math.pi/3,
         "coordinate_slice_energy_integral":"E=-c^4/(12*G)*(v_s/c)^2*integral_0^infinity[r^2*(df/dr)^2]dr",
         "shape":"[tanh((r+R)/Delta)-tanh((r-R)/Delta)]/[2*tanh(R/Delta)]",
         "negative_density_in_nonzero_wall_weak_energy_condition_violation":True,
         "full_Einstein_tensor_or_realistic_matter_model_constructed":False
       },
       "numerical_method":{
         "Simpson_even_steps_fine":N_FINE,
         "Simpson_even_steps_coarse":N_COARSE,
         "radial_upper_limit_m":"R+20*Delta, exponentially suppressed tail",
         "fixed_before_first_run":True,
         "G_SI_m3_kg_s2":G,
         "c_SI_m_per_s":C,
         "energy_is_slice_integral_not_invariant_ADM_energy_or_fuel":True,
         "beta_may_exceed_one_as_coordinate_ansatz_not_local_material_speed":True
       },
       "baseline_speed_sweep_R100_Delta10":primary,
       "frozen_thickness_sweep_R100_beta1":thin,
       "frozen_radius_sweep_beta1_Delta_R_over_10":radius,
       "physical_and_temporal_admission":{
         "negative_energy_density_in_this_metric_required":True,
         "negative_energy_source_constructed_or_measured":False,
         "real_warp_bubble_generated":False,
         "observed_effective_superluminal_travel":False,
         "physical_early_independently_committed_result":False,
         "physically_late_independent_free_choice":False,
         "genuine_closed_timelike_curve_constructed":False,
         "retrocausality_proven":False,
         "external_lab_trials":0,
         "model_excludes_weak_field_positive_energy_warp_variants":True,
         "scientific_status":"REPRODUCED_CLASSICAL_ALCUBIERRE_NEGATIVE_ENERGY_REQUIREMENT_ONLY"
       },
       "frozen_010_and_011A_F_scientific_records_untouched":True,
       "NAS_QPU_and_containers_unmodified":True
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    args=p.parse_args()
    data=evaluate()
    path=Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf-8") as file:
        json.dump(data,file,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)
        file.write("\n")
    b=data["baseline_speed_sweep_R100_Delta10"]
    print("JANUS_011G_RESULT "+json.dumps({
       "R_m":100,"wall_parameter_Delta_m":10,
       "beta_0_1_energy_J":b[1]["coordinate_slice_integrated_local_energy_J"],
       "beta_1_energy_J":b[2]["coordinate_slice_integrated_local_energy_J"],
       "beta_2_energy_J":b[3]["coordinate_slice_integrated_local_energy_J"],
       "beta_1_negative_mass_equivalent_earth_masses":b[2]["negative_energy_magnitude_mass_equivalent_earth_masses"],
       "beta_1_wall_density_J_per_m3":b[2]["wall_energy_density_J_per_m3_at_equator"],
       "beta_2_forward_axis_coordinate_stagnation_radius_m":b[3]["forward_axis_coordinate_null_stagnation"]["positive_x_axis_r_m"],
       "thickness_sweep_Delta_and_energy": [[round(q["shape_wall_delta_parameter_m"],1),q["coordinate_slice_integrated_local_energy_J"]] for q in data["frozen_thickness_sweep_R100_beta1"]],
       "full_original_Einstein_tensor_computed":False,
       "original_metric_reproduced":True,
       "warp_engine_built":False,
       "retrocausality_proven":False
    },sort_keys=True),flush=True)

if __name__=="__main__":main()
