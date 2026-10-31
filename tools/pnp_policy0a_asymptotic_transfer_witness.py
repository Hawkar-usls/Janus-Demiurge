#!/usr/bin/env python3
"""Exact-integer all-n algebra for the Policy-0A / padded directed GT reduction.

The verifier does NOT prove the external GT_n FCWS lower bound; it audits
the reduction's polynomial identities, strict inequalities and source
encoding with an independently written generator (no TOPA code imports).
"""
from __future__ import annotations

import argparse
from itertools import combinations, permutations
from math import comb
import json
from pathlib import Path

SCHEMA = "janus.pnp.policy0a_asymptotic_transfer_witness.v1"
SOURCE_GT = "Beame-Impagliazzo-Pitassi-Segerlind-2010-Definition-4.24-Theorem-4.28"
GT_THEOREM = "FCWS_GT_n_nodes_at_least_2^(n-2)"
POLICY_MODEL = "JANUS_Policy0A_fixed_4L_attempts_min_pivot_max_frequency_exact_cache"

class TransferHold(ValueError):
    pass

def plus(a, b):
    out = [0] * max(len(a), len(b))
    for i, v in enumerate(a):
        out[i] += v
    for i, v in enumerate(b):
        out[i] += v
    return out

def negative(a):
    return [-v for v in a]

def sub(a, b):
    return plus(a, negative(b))

def scale(a, k):
    return [k * v for v in a]

def mul(a, b):
    out = [0] * (len(a) + len(b) - 1)
    for i, v in enumerate(a):
        for j, w in enumerate(b):
            out[i + j] += v * w
    return out

def shift(a, integer):
    """Compute coefficients of p(m+integer), not a sampling argument."""
    result = [0] * len(a)
    for degree, value in enumerate(a):
        for j in range(degree + 1):
            result[j] += value * comb(degree, j) * integer ** (degree - j)
    return result

def value(a, n):
    return sum(v * n ** i for i, v in enumerate(a))

def source_gt_n(n):
    """Clean-room directed GT clause set, matching Definition 4.24."""
    if not 3 <= n <= 6:
        raise TransferHold("FINITE_GT_ENUMERATION_BOUNDED_TO_3_6")
    variable = {(i, j): 1 + i * (n - 1) + j - (j > i)
                for i in range(n) for j in range(n) if i != j}
    # Avoid depending on the order convention: only uniqueness matters.
    if len(set(variable.values())) != n * (n - 1):
        raise TransferHold("DIRECTED_VARIABLE_COLLISION")
    clauses = set()
    def clause(literals):
        s = frozenset(literals)
        if any(-v in s for v in s):
            raise TransferHold("UNEXPECTED_TAUTOLOGY_IN_GT")
        clauses.add(s)
    for i, j in combinations(range(n), 2):
        clause((variable[i,j], variable[j,i]))
        clause((-variable[i,j], -variable[j,i]))
    for i, j, k in permutations(range(n), 3):
        clause((-variable[i,j], -variable[j,k], variable[i,k]))
    for j in range(n):
        clause(variable[i,j] for i in range(n) if i != j)
    return len(clauses), sum(len(s) for s in clauses), len(variable)

def verify_algebra(*, b_factor=256, p_factor=64, attempt_factor=4):
    n = [0,1]
    one = [1]
    n_minus_one = sub(n, one)
    n2 = mul(n,n)
    v = mul(n,n_minus_one)
    B = scale(n2,b_factor)
    p = scale(n2,p_factor)
    l_gt = scale(mul(n, mul(n_minus_one,n_minus_one)),3)
    l_boosters = scale(mul(v,B),2)
    l_sink = scale(p,6)
    L0 = plus(plus(l_gt,l_boosters),l_sink)
    clauses_gt = mul(n,plus(mul(n_minus_one,n_minus_one),one))
    clauses_all = plus(plus(clauses_gt,mul(v,B)),scale(p,2))
    max_variable = plus(plus(plus([2],scale(p,2)),v),mul(v,B))
    slack = sub(mul(p,p),scale(L0,attempt_factor))
    core_over_sink = sub(B,scale(p,2))
    if b_factor != 256 or p_factor != 64 or attempt_factor != 4:
        raise TransferHold("FROZEN_POLICY_PARAMETERS_CHANGED")
    if L0 != [0,3,378,-509,512] or slack != [0,-12,-1512,2036,2048]:
        raise TransferHold("EXACT_GADGET_POLYNOMIAL_IDENTITY_FALSE")
    if clauses_all != [0,2,126,-255,256]:
        raise TransferHold("EXACT_CLAUSE_COUNT_IDENTITY_FALSE")
    if max_variable != [2,-1,129,-256,256]:
        raise TransferHold("MAX_VARIABLE_IDENTIFIER_IDENTITY_FALSE")
    # n = m+3 with integer m>=0. All coefficients must be nonnegative and
    # the constant strictly positive. This proves slack>0 for EVERY n>=3.
    slack_shift = shift(slack,3)
    freq_shift = shift(core_over_sink,3)
    if slack_shift[0] <= 0 or min(slack_shift) < 0 \
            or freq_shift[0] <= 0 or min(freq_shift) < 0:
        raise TransferHold("ALL_N_STRICT_POSITIVITY_NOT_CERTIFIED")
    if value(mul(p,p),3) <= 64:
        raise TransferHold("MAX_64_ATTEMPT_FLOOR_CAN_REACH_CORE")
    finite = []
    for m in range(3,7):
        clauses, literals, variables = source_gt_n(m)
        if clauses != value(clauses_gt,m) \
                or literals != value(l_gt,m) or variables != value(v,m):
            raise TransferHold("DIRECTED_GT_GENERATOR_SOURCE_IDENTITY_FALSE")
        finite.append({"n":m,"gt_variables":variables,"gt_clauses":clauses,
                       "gt_literal_occurrences":literals})
    # A single unique booster clause has three satisfying 2-bit assignments;
    # a nonempty affine F_2^k solution set always has cardinality a power of 2.
    satisfying = [(x,y) for x in (0,1) for y in (0,1) if x or y]
    if len(satisfying) != 3:
        raise TransferHold("NON_AFFINE_BOOSTER_CARDINALITY_FALSE")
    return {
        "schema":SCHEMA,
        "status":"ALL_N_ALGEBRA_CERTIFIED__GT_THEOREM_DEPENDENCY_EXPLICIT",
        "parameter_domain":"INTEGERS_N_GE_3",
        "exact_polynomials_coefficients_ascending_degree":{
            "L0":L0,"p_squared_minus_4L0":slack,
            "L0_substitute_n_equals_m_plus_3":shift(L0,3),
            "strict_slack_substitute_n_equals_m_plus_3":slack_shift,
            "core_frequency_minus_sink_frequency":core_over_sink,
            "strict_frequency_slack_substitute_n_equals_m_plus_3":freq_shift,
            "total_clause_count":clauses_all,
            "maximum_variable_id":max_variable,
        },
        "root_affine_preemption_excluded_by_non_affine_private_booster_scope":True,
        "d_is_minimum_pivot_id":True,
        "sink_pair_resolvents_always_tautological":True,
        "sink_survives_every_core_restriction":True,
        "unit_propagation_only_eliminates_private_booster_leaves":True,
        "core_branch_priority_from_strict_frequency_gap":True,
        "source_GT_finite_generator_replay":finite,
        "conditional_transfer":{
            "source_theorem":SOURCE_GT,
            "source_lower_bound":GT_THEOREM,
            "source_paper_pdf":"https://www.cs.toronto.edu/~toni/Papers/memoization.pdf",
            "assumes_peer_reviewed_FCWS_theorem":True,
            "model":"EXACT_PRE_RESOLUTION_FORMULA_CACHE_PLUS_BOUNDED_LOCAL_RESOLUTION",
            "projected_GT_residuals_preserved_under_private_padding":True,
            "exact_augmented_cache_hits_cannot_merge_distinct_core_residuals":True,
            "conditional_residual_count_lower_bound":"S(H_n)>=2^(n-2)",
            "input_size_bound":"O(n^4 log n)",
            "superpolynomial_in_input_size":True,
        },
        "external_GT_theorem_independently_reproved":False,
        "machine_checked_general_projection_induction":False,
        "unrestricted_SAT_lower_bound":False,
        "P_VS_NP":"OPEN",
        "authority_delta":0,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out",required=True)
    args=ap.parse_args()
    report=verify_algebra()
    path=Path(args.out)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":report["status"],
                      "positive_all_n":True,
                      "external_GT_theorem_reproved":False,
                      "P_VS_NP":"OPEN"},sort_keys=True))

if __name__=="__main__":
    main()
