#!/usr/bin/env python3
"""JANUS R9 EXACT mathematical causal certificate. Python stdlib, no floating point.

Two independent mathematical statements (never conflate them):
1) Under classical forward-only information R, with later independent fair B,
   any early A=f(R), or pair (X,Z)=g(R), is independent of B. Proof is
   probability factorization, not an estimate based on a finite sample.
2) In the generalized process-matrix framework of Oreshkov–Costa–Brukner
   (Nature Communications 3,1092,2012; DOI 10.1038/ncomms2076), W made
   from anticommuting Pauli strings is valid as an abstract process and
   the prescribed instruments win a causal game with (2+sqrt(2))/4 > 3/4.
   This is NOT proof that a real clock-ordered future bit can be read in the past.

All matrix entries and scores live in the exact field Q(sqrt(2)); no
rounding or Monte Carlo in the proof. A complete exhaustive finite check
cross-validates the early-independent theorem; the theorem itself is general.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path


@dataclass(frozen=True)
class E:
    """a + b sqrt(2), with rational a,b (exact arithmetic)."""
    a: F
    b: F = F(0)

    def __add__(self, other):
        if not isinstance(other,E):
            other=E(F(other))
        return E(self.a+other.a,self.b+other.b)

    __radd__=__add__

    def __neg__(self):
        return E(-self.a,-self.b)

    def __sub__(self,other):
        return self + -other

    def __mul__(self,other):
        if not isinstance(other,E):
            other=E(F(other))
        return E(self.a*other.a+2*self.b*other.b,
                 self.a*other.b+self.b*other.a)

    __rmul__=__mul__

    def is_positive(self):
        a,b=self.a,self.b
        if a>=0 and b>=0:
            return a>0 or b>0
        if a<=0 and b<=0:
            return False
        if a>0 and b<0:
            return a*a > 2*b*b
        # a<0, b>0
        return 2*b*b > a*a

    def encoded(self):
        return {"rational":str(self.a),"sqrt2_coefficient":str(self.b)}


I=((F(1),F(0)),(F(0),F(1)))
X=((F(0),F(1)),(F(1),F(0)))
Z=((F(1),F(0)),(F(0),F(-1)))
ZMEAS={
  0:((F(1),F(0)),(F(0),F(0))),
  1:((F(0),F(0)),(F(0),F(1))),
}
XMEAS={
  0:((F(1,2),F(1,2)),(F(1,2),F(1,2))),
  1:((F(1,2),F(-1,2)),(F(-1,2),F(1,2))),
}


def kron(a,b):
    return tuple(tuple(a[i][j]*b[k][l]
                       for j in range(len(a)) for l in range(len(b)))
                 for i in range(len(a)) for k in range(len(b)))


def kron4(a,b,c,d):
    return kron(kron(kron(a,b),c),d)


def matmul(a,b):
    n=len(a)
    return tuple(tuple(sum((a[i][k]*b[k][j] for k in range(n)),F(0))
                       for j in range(n)) for i in range(n))


def matsum(a,b):
    return tuple(tuple(a[i][j]+b[i][j] for j in range(len(a)))
                 for i in range(len(a)))


def matzero(a):
    return all(v==0 for row in a for v in row)


def mattrace(m):
    return sum((m[i][i] for i in range(len(m))), F(0))


II=kron4(I,I,I,I)
P=kron4(I,Z,Z,I)
Q=kron4(Z,I,X,Z)


def algebraic_process(visibility=F(1)):
    if type(visibility) is not F or not F(0)<=visibility<=F(1):
        raise ValueError("VISIBILITY_OUTSIDE_PROVED_PROCESS_RANGE")
    return tuple(tuple(E(II[i][j]/4, visibility*(P[i][j]+Q[i][j])/8)
                       for j in range(16)) for i in range(16))


def local_A(a,x):
    return kron(ZMEAS[x],ZMEAS[a])


def local_B(b,task,y):
    if task==0:
        return kron(XMEAS[y],ZMEAS[b^y])
    if task==1:
        return kron(ZMEAS[y],ZMEAS[0])
    raise ValueError("INVALID_CAUSAL_GAME_TASK")


def generalized_born(w,ma,mb):
    m=kron(ma,mb)
    return sum((w[i][j]*m[j][i] for i in range(16) for j in range(16)),
               E(F(0)))


def analytic_probability(visibility,a,b,task,x,y):
    sign=1 if (x==b if task==0 else y==a) else -1
    return E(F(1,4), visibility*F(sign,8))


def validate_ocb_algebra():
    assert matmul(P,P)==II and matmul(Q,Q)==II
    assert matzero(matsum(matmul(P,Q),matmul(Q,P)))
    assert mattrace(P)==0 and mattrace(Q)==0
    for vis in (F(0),F(1,2),F(3,4),F(1)):
        w=algebraic_process(vis)
        assert sum((w[i][i] for i in range(16)),E(F(0)))==E(F(4))
        assert E((1-vis)/4).a>=0 and E((1+vis)/4).a>=0
        # Formal CPTP normalization follows for *all* instruments:
        # term P contains Z_Bin tensor I_Bout, whose trace against ANY
        # CPTP Choi M_B equals Tr[Z_Bin * Tr_Bout M_B]=Tr[Z I]=0.
        # term Q contains Z_Ain tensor I_Aout, so its factor against
        # ANY CPTP M_A vanishes identically for the same reason.
        # Trace M_A=Trace M_B=2 => Tr[W (M_A tensor M_B)]=4/4=1.
    return True


def prove_causal_game():
    validate_ocb_algebra()
    cases=[]
    for vis in (F(0),F(1,2),F(3,4),F(1)):
        w=algebraic_process(vis)
        scores=[]
        for task in (0,1):
            win=E(F(0))
            for a in (0,1):
                for b in (0,1):
                    normalization=E(F(0))
                    for x in (0,1):
                        for y in (0,1):
                            actual=generalized_born(w,local_A(a,x),
                                                    local_B(b,task,y))
                            expected=analytic_probability(vis,a,b,task,x,y)
                            assert actual==expected, "EXACT_BORN_MISMATCH"
                            assert actual.is_positive(), "NEGATIVE_PROBABILITY"
                            normalization+=actual
                            if x==b if task==0 else y==a:
                                win+=actual*F(1,4)
                    assert normalization==E(F(1)), "NORMALIZATION_FAILED"
            scores.append(win)
        p=(scores[0]+scores[1])*F(1,2)
        expected=E(F(1,2),vis*F(1,4))
        assert scores==[expected,expected] and p==expected
        causal_bound=E(F(3,4))
        advantage=p-causal_bound
        # Algebraic sign check contains no float or numerical approximation.
        violates=advantage.is_positive()
        assert violates == (2*vis*vis>F(1))
        cases.append({
          "visibility":str(vis),
          "exact_score":p.encoded(),
          "causal_game_bound":causal_bound.encoded(),
          "exact_advantage":advantage.encoded(),
          "violates_definite_order":violates,
          "valid_process_spectrum_eigenvalues":[str((1-vis)/4),
                                                 str((1+vis)/4)],
          "spectrum_multiplicity_each":8
        })
    assert cases[-1]["exact_advantage"]==E(F(-1,4),F(1,4)).encoded()
    assert cases[-1]["violates_definite_order"]
    return cases


def prove_independent_future_no_go():
    # General theorem:
    # if R independent B, P(R=r,B=b)=P(R=r)/2.
    # For arbitrary early F=f(R), or pair (X,Z)=g(R):
    # P(X=x,Z=z,B=b) =
    #   sum_{r:g(r)=(x,z)} P(R=r)/2 =
    #   P(X=x,Z=z) P(B=b).
    # Exact finite sanity check is exhaustive over all 16^2 Boolean
    # functions from a four-valued R. Weights are intentionally nonuniform.
    weights=(F(1,10),F(2,10),F(3,10),F(4,10))
    assert sum(weights)==1
    models=0
    for f in range(16):
        for g in range(16):
            pair={}
            for r,w in enumerate(weights):
                pair[((f>>r)&1,(g>>r)&1)]=pair.get(
                    ((f>>r)&1,(g>>r)&1),F(0))+w
            for (x,z),pxz in pair.items():
                for b in (0,1):
                    joint=sum((weights[r]*F(1,2)
                               for r in range(4)
                               if (f>>r)&1==x and (g>>r)&1==z),
                              F(0))
                    assert joint==pxz*F(1,2), "NO_GO_CONTRADICTED"
            models+=1
    assert models==256
    return {
      "theorem":"If B is an independent fair future bit and early F=f(R), then P(F=B)=1/2 and I(F;B)=0; for any early pair (X,Z)=g(R), P(X,Z|B)=P(X,Z).",
      "proof":"P(X=x,Z=z,B=b)=sum_{r:g(r)=(x,z)} P(R=r)P(B=b) = P(X=x,Z=z)/2.",
      "finite_exact_cross_checks":models,
      "finite_check_state_count":4,
      "nonuniform_state_probabilities":[str(w) for w in weights],
      "quantum_CPU_simulator_exemption":False,
      "assumptions":["R contains all information accessible before future B",
                     "B is fair and statistically independent of R",
                     "No physical future-to-past channel or advance leaked B"]
    }


def prove_postselection_counterexample():
    # X, Z, B independent fair bits. Select iff B=X XOR Z.
    all_events=[(x,z,b,F(1,8)) for x in (0,1) for z in (0,1)
                for b in (0,1)]
    acceptance=sum((p for x,z,b,p in all_events if b==(x^z)),F(0))
    assert acceptance==F(1,2)
    selected={(x,z,b):(p/acceptance if b==(x^z) else F(0))
              for x,z,b,p in all_events}
    hypothetical={(x,z,b):(F(1,4) if b==(x^z) else F(0))
                  for x,z,b,p in all_events}
    assert selected==hypothetical
    return {
      "selected_fraction_of_original_attempts":"1/2",
      "postselected_conditional_equals_ideal_jamming_table":True,
      "unconditional_past_message":False,
      "interpretation":"Selection on a later bit can exactly counterfeit ideal parity-jamming statistics but rejects half of complete earlier attempts."
    }


def report():
    result={
      "schema":"janus.mathematical_causality_exact_certificate.r9",
      "mathematical_basis":"Q(sqrt(2)), rational fractions and exact 16x16 Pauli tensors; no floating-point and no Monte Carlo",
      "ocb_doi":"10.1038/ncomms2076",
      "field":"a + b*sqrt(2), a,b rational",
      "process":"W(v)=(I + (v/sqrt(2))*(I Z Z I + Z I X Z))/4",
      "process_pauli_square_identity":True,
      "process_pauli_anticommutation":True,
      "process_trace":4,
      "all_CPTP_normalized_by_partial_trace_identity":True,
      "ocb_game_cases":prove_causal_game(),
      "fixed_causal_bound":"3/4",
      "bound_proof":"For either definite direction A<B or B<A, one of two equally weighted guessing tasks has independent hidden input, success <=1/2; other task <=1. Therefore total <=(1/2)*(1+1/2)=3/4. Convex mixtures preserve bound.",
      "strict_violation_at_v1":"(sqrt(2)-1)/4>0; exact because 2>1",
      "standard_forward_cpu_no_go":prove_independent_future_no_go(),
      "postselection_false_positive":prove_postselection_counterexample(),
      "theorem_proved":"Generalized OCB process-matrix model admits correlations incompatible with convex mixtures of definite causal orders.",
      "physical_theorem_not_proved":"A standard forward-only CPU, or the physical universe, implements a genuine time-ordered future-to-past channel.",
      "physical_retrocausal_channel_deduced":False,
      "future_b_known_as_model_parameter_if_simulated":True,
      "no_quantum_hardware_used":True,
      "production_promotion":False,
      "scientific_verdict":"FORMAL_NONCAUSAL_PROCESS_EXISTENCE_PROVEN__INDEPENDENT_FUTURE_CPU_NO_GO_PROVEN__PHYSICAL_RETROCAUSALITY_UNDETERMINED"
    }
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    if args.out.exists():
        raise RuntimeError("REFUSE_OVERWRITE")
    v=report()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(v,indent=2,sort_keys=True)+"\n",
                        encoding="utf-8")
    print(json.dumps({
      "exact_OCB_score":v["ocb_game_cases"][-1]["exact_score"],
      "causal_bound":v["fixed_causal_bound"],
      "exact_violation":v["strict_violation_at_v1"],
      "all_forward_CPU_future_independence_checks":
        v["standard_forward_cpu_no_go"]["finite_exact_cross_checks"],
      "physical_future_to_past":v["physical_retrocausal_channel_deduced"]
    },sort_keys=True))


if __name__=="__main__":
    main()
