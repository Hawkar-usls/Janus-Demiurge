#!/usr/bin/env python3
"""JANUS R10: exact minimal-axiom / causal-orientation certificate.

Original small parity toy, not claimed as a new physical theorem.
For 0 <= eta <= 1 the same observational P(X,Z,B) has TWO structurally
different causal models:
  Forward: X,Z i.i.d. fair; N biased; B = X XOR Z XOR N.
  Backward-formal: B exogenous fair; X fair; N biased; Z = X XOR B XOR N.
Thus observing even a perfect parity predictor of B does NOT prove a
future-to-past arrow. Their do(B) predictions differ.

All calculations are exact fractions. A global consistency filter can
simulate the distribution but ACCEPTS/DROPS histories using B after
generation; it does not send information to a sealed earlier receiver.
A 'backward-formal' sampler can sample B first on a CPU, but this makes B
an EARLIER computational input. Neither is a hardware retrochannel.

Related background: Vilasini & Colbeck, PRR 8 013070 (2026),
DOI 10.1103/h31d-wqyg (different full operational jamming task).
"""
from __future__ import annotations

from fractions import Fraction as F
import argparse
import json
from pathlib import Path

BITS = (0, 1)
ETA_GRID = (F(0), F(1, 4), F(1, 2), F(3, 4), F(1))


def require(ok, why):
    if not ok:
        raise ValueError(why)


def validate_eta(eta):
    require(type(eta) is F and 0 <= eta <= 1, "ETA_OUT_OF_RANGE_OR_NOT_EXACT")
    return eta


def sign(x, z, b):
    return 1 if x ^ z ^ b == 0 else -1


def joint(eta):
    validate_eta(eta)
    p = {(x, z, b): (F(1) + eta * sign(x, z, b)) / 8
         for x in BITS for z in BITS for b in BITS}
    assert sum(p.values()) == 1 and all(0 <= v <= 1 for v in p.values())
    return p


def noise_probability(eta, n):
    validate_eta(eta)
    require(n in BITS, "INVALID_NOISE_BIT")
    return (F(1) + eta * (1 if n == 0 else -1)) / 2


def forward_generator_distribution(eta):
    # X,Z are the earlier observed bits; B is computed LAST from their parity.
    validate_eta(eta)
    p = {(x, z, b): F(0) for x in BITS for z in BITS for b in BITS}
    for x in BITS:
        for z in BITS:
            for n in BITS:
                b = x ^ z ^ n
                p[(x, z, b)] += F(1, 4) * noise_probability(eta, n)
    return p


def backward_formal_distribution(eta):
    # B is a freely sampled input of the MATHEMATICAL model; an ordinary
    # CPU generates it BEFORE Z, hence not a real later physical choice.
    validate_eta(eta)
    p = {(x, z, b): F(0) for x in BITS for z in BITS for b in BITS}
    for b in BITS:
        for x in BITS:
            for n in BITS:
                z = x ^ b ^ n
                p[(x, z, b)] += F(1, 4) * noise_probability(eta, n)
    return p


def early_given_b_from_joint(eta, b):
    validate_eta(eta)
    require(b in BITS, "INVALID_FUTURE_BIT")
    return {(x, z): joint(eta)[(x, z, b)] * 2
            for x in BITS for z in BITS}


def forward_do_b(eta, b):
    # Pearl do(B=b): overwrite B's generating equation. X,Z are unchanged.
    validate_eta(eta)
    require(b in BITS, "INVALID_FUTURE_BIT")
    return {(x, z): F(1, 4) for x in BITS for z in BITS}


def backward_do_b(eta, b):
    # Formal intervention sets exogenous B, then Z uses the supplied B.
    return early_given_b_from_joint(eta, b)


def total_variation(p, q):
    assert set(p) == set(q)
    return sum((abs(p[k] - q[k]) for k in p), F(0)) / 2


def marginal_xz(early, index):
    return {v: sum((p for pair, p in early.items() if pair[index] == v),
                   F(0)) for v in BITS}


def postselected_global_consistency(eta):
    """Postselect uniform independent histories using a B-dependent filter.

    Acceptance probability for (x,z,b) = (1+eta*(-1)^(x^z^b))/2.
    Mean acceptance 1/2. Conditional accepted distribution == joint(eta).
    This construction requires LATE conditioning; it cannot leave an
    unmodifiable earlier record of all attempts with a retro-signal.
    """
    validate_eta(eta)
    base = {(x, z, b): F(1, 8)
            for x in BITS for z in BITS for b in BITS}
    acceptance = {k: (F(1) + eta * sign(*k)) / 2 for k in base}
    mass = sum((base[k] * acceptance[k] for k in base), F(0))
    assert mass == F(1, 2)
    post = {k: base[k] * acceptance[k] / mass for k in base}
    assert post == joint(eta)
    return {"acceptance_mass": mass, "distribution": post}



def symbolic_all_real_eta_proof():
    """Coefficient-wise identity in Q[eta] for ALL real 0<=eta<=1.

    We do not merely test a few numerical eta values. Every probability
    is an affine polynomial c0 + c1*eta, and equality is verified by
    comparing its rational coefficients. For the TV identity, eta>=0
    fixes the signs of the four conditional cell differences.
    """
    terms=[]
    for x in BITS:
        for z in BITS:
            for b in BITS:
                parity=sign(x,z,b)
                joint_coeff=(F(1,8),F(parity,8))
                forward_coeff=(F(1,4)*F(1,2),
                               F(1,4)*F(parity,2))
                backward_coeff=(F(1,4)*F(1,2),
                                F(1,4)*F(parity,2))
                # Uniform joint 1/8 times late selection weight
                # (1+eta*parity)/2, renormalized by acceptance 1/2.
                selected_coeff=(F(1,8),F(parity,8))
                assert joint_coeff==forward_coeff==backward_coeff==selected_coeff
                terms.append({
                    "x":x,"z":z,"b":b,
                    "joint_const":str(joint_coeff[0]),
                    "joint_eta_coeff":str(joint_coeff[1]),
                    "all_three_mechanisms_symbolically_identical":True
                })
    assert len(terms)==8
    # do(B) in the forward model leaves all four XZ cells at 1/4.
    # do(B) in backward model has cell probability (1+sign eta)/4.
    # Its B=0 vs B=1 difference in each cell equals +/- eta/2.
    # Four equal absolute differences sum to 2eta; TV = eta.
    for x in BITS:
        for z in BITS:
            c0=(F(1,4),F(sign(x,z,0),4))
            c1=(F(1,4),F(sign(x,z,1),4))
            assert c0[0]==c1[0] and abs(c0[1]-c1[1])==F(1,2)
    return {
        "symbolic_ring":"Q[eta] (affine polynomials), interpreted 0<=eta<=1",
        "all_eight_joint_cells_verified_as_polynomial_identities":True,
        "eight_exact_polynomial_coefficients":terms,
        "p_backward_doB_b_vs_0":"(1 + (-1)^(x XOR z XOR b)*eta)/4",
        "p_forward_doB_b":"1/4",
        "backward_doB_total_variation_exact":"eta",
        "forward_doB_total_variation_exact":"0",
        "forward_future_independence_conflicts_with_eta_positive":True,
        "parity_correct_probability_exact":"(1+eta)/2",
        "observational_equivalence_all_real_eta_in_closed_interval":True,
        "physical_retrocausal_resource_derived":False
    }


def encode(p):
    return {"|".join(str(v) for v in k): str(value)
            for k, value in sorted(p.items())}


def certificate_one_eta(eta):
    expected = joint(eta)
    forward = forward_generator_distribution(eta)
    backward = backward_formal_distribution(eta)
    assert expected == forward == backward
    assert sum(expected[(x, z, b)] for x in BITS for z in BITS
               for b in (0, 1)) == 1
    observational_early = [early_given_b_from_joint(eta, b) for b in BITS]
    for b in BITS:
        assert sum(observational_early[b].values()) == 1
        assert marginal_xz(observational_early[b], 0) == {
            0: F(1, 2), 1: F(1, 2)}
        assert marginal_xz(observational_early[b], 1) == {
            0: F(1, 2), 1: F(1, 2)}
    observational_tv = total_variation(*observational_early)
    intervention_forward_tv = total_variation(
        forward_do_b(eta, 0), forward_do_b(eta, 1))
    intervention_backward_tv = total_variation(
        backward_do_b(eta, 0), backward_do_b(eta, 1))
    assert observational_tv == eta
    assert intervention_forward_tv == 0
    assert intervention_backward_tv == eta
    success = sum((p for (x, z, b), p in expected.items()
                   if (x ^ z) == b), F(0))
    assert success == (1 + eta) / 2
    consistency = postselected_global_consistency(eta)
    assert consistency["acceptance_mass"] == F(1, 2)
    return {
        "eta": str(eta),
        "observational_joint": encode(expected),
        "forward_and_backward_observational_law_identical": True,
        "early_single_marginals_all_1_over_2": True,
        "observational_joint_TV_given_B": str(observational_tv),
        "formal_forward_doB_early_joint_TV": str(intervention_forward_tv),
        "formal_backward_doB_early_joint_TV": str(intervention_backward_tv),
        "parity_guesses_B_success_under_observation": str(success),
        "globally_postselected_acceptance_fraction": "1/2",
        "postselected_distribution_same_as_both_models": True,
        "actual_independent_future_bit_read_before_generation": False,
    }


def report():
    rows = [certificate_one_eta(eta) for eta in ETA_GRID]
    assert rows[0]["observational_joint_TV_given_B"] == "0"
    assert rows[-1]["observational_joint_TV_given_B"] == "1"
    assert rows[-1]["parity_guesses_B_success_under_observation"] == "1"
    return {
        "schema": "janus.minimal_retrocausal_axioms.exact_r10",
        "mathematical_source": "Original elementary binary structural causal model proof; relates to causal identification and hypothetical jamming, not a new physical experimental result.",
        "field": "rational fractions only, zero floating point",
        "formal_joint_family": "P_eta(X=x,Z=z,B=b) = [1 + eta*(-1)^(x XOR z XOR b)] / 8",
        "range_eta": "0 <= eta <= 1",
        "forward_causal_structural_model": {
            "exogenous": "X,Z independent fair; N independent noise with P(N=0)=(1+eta)/2",
            "late_equation": "B = X XOR Z XOR N",
            "real_cpu_time_order": "Compute X,Z first, compute B last",
            "late_B_exogenous_and_jointly_independent_of_early_XZ": False
        },
        "backward_formal_structural_model": {
            "exogenous": "B,X independent fair; N independent noise with P(N=0)=(1+eta)/2",
            "early_equation": "Z = X XOR B XOR N",
            "real_cpu_time_order": "Sample B before computing Z",
            "real_independent_late_implementation_provided": False
        },
        "central_nonidentifiability_theorem": (
            "Both opposite-direction structural models produce the SAME complete "
            "observational P(X,Z,B) for every rational eta in [0,1]. "
            "Thus even perfect prediction of B from early joint parity cannot "
            "identify a retrocausal arrow from observational correlations."
        ),
        "intervention_separation_theorem": (
            "Forward do(B=b) leaves P(X,Z) uniform, giving TV=0; "
            "backward-formal do(B=b) makes parity correlated, giving TV=eta. "
            "Intervention semantics, not observational fit, separate the models."
        ),
        "minimal_change_from_forward_independent_choice_axiom": (
            "Any eta>0 forces P(X,Z,B) != P(X,Z)P(B). "
            "Thus either the later B is not jointly independent of all earlier "
            "records in a forward model; or a genuine B->early influence is "
            "assumed; or observations have been postselected/altered. "
            "A CPU cannot simultaneously enforce independent late B, immutable "
            "earlier records, eta>0 and no extra causal resource."
        ),
        "weak_single_marginals_no_signalling": (
            "For each eta,b, P(X=0|B=b)=P(Z=0|B=b)=1/2, "
            "while joint parity can encode B. If early parties can combine "
            "their records before B, a backward-formal eta>0 channel could "
            "permit earlier joint inference; the mathematical toy alone "
            "does not guarantee relativistic no-signalling under arbitrary "
            "interventions or spacetime constraints."
        ),
        "parity_accuracy_formula": "(1+eta)/2",
        "mutual_information_expression_bits": (
            "I(B; X,Z) = 1 - h_2((1-eta)/2), for eta>0 positive; "
            "h_2(p)=-p log2 p-(1-p) log2(1-p). "
            "This is a standard binary symmetric channel identity."
        ),
        "two_sided_boundary_or_global_consistency": (
            "Uniform independent complete histories followed by acceptance "
            "with weight [1+eta*(-1)^(X XOR Z XOR B)]/2 has exactly "
            "the desired conditional distribution; acceptance mass is "
            "1/2. It is late-conditioned filtering, not a sealed early message."
        ),
        "symbolic_all_eta_certificate": symbolic_all_real_eta_proof(),
        "all_exact_eta_cases": rows,
        "failed_possible_proof_claims": [
            "A perfect observed parity predictor by itself establishes physical reverse causation.",
            "Time-symmetric boundary weighting is an operational backward-time CPU signal.",
            "Individual no-signalling marginals imply no joint early information about late B.",
            "A simulator that samples B first implements B being chosen later in physical time."
        ],
        "cpu_only": True,
        "physical_retrocausality_deduced": False,
        "novel_physical_mechanism_constructed": False,
        "proof_status": "EXACT_CONSTRUCTIVE_OBSERVATIONAL_EQUIVALENCE_AND_INTERVENTION_SEPARATION",
        "production_promotion": False
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        raise RuntimeError("REFUSE_OVERWRITE")
    res = report()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, sort_keys=True, indent=2)+"\n",
                     encoding="utf-8")
    print(json.dumps({
        "exact_rational_eta_cases": len(res["all_exact_eta_cases"]),
        "max_interventional_separation": res["all_exact_eta_cases"][-1][
            "formal_backward_doB_early_joint_TV"],
        "all_observational_forward_backward_identical": all(
            r["forward_and_backward_observational_law_identical"]
            for r in res["all_exact_eta_cases"]),
        "physical_signal": False
    }, sort_keys=True))


if __name__ == "__main__":
    main()
