#!/usr/bin/env python3
"""JANUS R8 exact rational four-photon delayed-choice entanglement swap toy.

Idealized resource: |Phi+>_12 tensor |Phi+>_34 with photons 1 and 4
measured first in Z basis, and 2 and 3 measured afterward.

Victor's later independent setting B selects:
  SSM: computational basis measurement on 2 and 3.
  BSM: full Bell-basis measurement on 2 and 3.

All exact joint probabilities P(X,Z,V|do(B)) use Fraction and are derived
from this specified ideal state, NOT copied from Ma et al experimental
photons or reconstructed from detector time tags. The earlier P(X,Z)
is ALWAYS uniform irrespective of later measurement setting. Conditional
P(X,Z|B,V) can nevertheless differ dramatically.

Contrast:
- Hypothetical parity-jamming toy with X XOR Z = B and both single
  marginals independent of B; this assumes a nonphysical future-control
  resource, NOT the quantum dynamics of the four-photon apparatus.
- Classical postselection makes ordinary independent records *look*
  identical to the jamming conditional table while discarding half of
  all original attempts based on later data.

Sources: Ma et al., Nature Physics 8, 479-484 (2012),
DOI 10.1038/nphys2294; Vilasini-Colbeck, PRR 8, 013070 (2026),
DOI 10.1103/h31d-wqyg. The parity toy is NOT their full certified task.
"""
from __future__ import annotations
from fractions import Fraction
import argparse
import json
from pathlib import Path

BITS=(0,1)
SETTINGS=("SSM","BSM")
BELL_NAMES={0:("PHI_PLUS","PHI_MINUS"),1:("PSI_PLUS","PSI_MINUS")}


def standard_joint(setting):
    if setting not in SETTINGS:
        raise ValueError("UNKNOWN_VICTOR_SETTING")
    table={}
    for x in BITS:
        for z in BITS:
            if setting=="SSM":
                table[(x,z,f"{x}{z}")]=Fraction(1,4)
            else:
                for v in BELL_NAMES[x^z]:
                    table[(x,z,v)]=Fraction(1,8)
    assert sum(table.values())==1
    return table


def early_marginal(setting):
    t=standard_joint(setting)
    return {(x,z):sum(p for (xx,zz,_),p in t.items()
                       if xx==x and zz==z)
            for x in BITS for z in BITS}


def late_heralded_early(setting,v):
    t=standard_joint(setting)
    prob=sum(p for (_,_,vv),p in t.items() if vv==v)
    if not prob:
        raise ValueError("UNOBSERVED_LATE_HERALD")
    return {(x,z):sum(p for (xx,zz,vv),p in t.items()
                       if xx==x and zz==z and vv==v)/prob
            for x in BITS for z in BITS}


def ideal_jamming_early_given_late_bit(b):
    if b not in BITS:
        raise ValueError("INVALID_HYPOTHETICAL_LATE_BIT")
    return {(x,z):Fraction(1,2) if x^z==b else Fraction(0)
            for x in BITS for z in BITS}


def total_variation(p,q):
    assert set(p)==set(q)
    return sum(abs(p[k]-q[k]) for k in p)/2


def report():
    early={s:early_marginal(s) for s in SETTINGS}
    assert all(all(p==Fraction(1,4) for p in early[s].values())
               for s in SETTINGS)
    quantum_tv=total_variation(early["SSM"],early["BSM"])
    bsm_herald=late_heralded_early("BSM","PHI_PLUS")
    # BSM PHI+ projects early Z-basis records onto matching parity,
    # but ONLY after a late herald. Fourfold events/selection matter.
    assert bsm_herald[(0,0)]==bsm_herald[(1,1)]==Fraction(1,2)
    assert bsm_herald[(0,1)]==bsm_herald[(1,0)]==0
    jam={str(b):ideal_jamming_early_given_late_bit(b) for b in BITS}
    jt=total_variation(jam["0"],jam["1"])
    assert jt==1
    assert all(sum(jam[str(b)][(x,z)] for z in BITS)==Fraction(1,2)
               for x in BITS for b in BITS)
    assert all(sum(jam[str(b)][(x,z)] for x in BITS)==Fraction(1,2)
               for z in BITS for b in BITS)
    def dstr(d):
        return {f"{x}{z}":str(p) for (x,z),p in d.items()}
    def event_table(t):
        return [{"x":x,"z":z,"late_outcome":v,"probability":str(p)}
                for (x,z,v),p in sorted(t.items())]
    return {
      "schema":"janus.ma_delayed_choice_exact_four_photon.r8",
      "model_scope":"IDEAL_4_QUBIT_STATE_Z_EARLY_BASIS__NOT_EMPIRICAL_MA_2012_PHOTON_DATA",
      "state":"|Phi+>_12 tensor |Phi+>_34",
      "early_x":"Z basis measurement on photon 1",
      "early_z":"Z basis measurement on photon 4",
      "future_B":"independent intervention choosing SSM vs BSM measurement of photons 2 & 3",
      "standard_4_photon_ideal_exact_joint_tables":{s:event_table(standard_joint(s)) for s in SETTINGS},
      "standard_early_joint_distribution_by_future_choice":{s:dstr(early[s]) for s in SETTINGS},
      "standard_early_joint_TV_between_late_settings":float(quantum_tv),
      "BSM_PHI_PLUS_heralded_early_distribution":dstr(bsm_herald),
      "BSM_PHI_PLUS_herald_probability":str(sum(p for (_,_,v),p in standard_joint("BSM").items() if v=="PHI_PLUS")),
      "heralded_early_difference_is_not_unconditional_retrocausality":True,
      "hypothetical_nonphysical_late_jamming_parity":{
        "joint_early_by_future_bit":{k:dstr(v) for k,v in jam.items()},
        "joint_early_TV_between_future_choices":float(jt),
        "individual_early_marginals_independent_of_future":True,
        "required_resource":"An actual beyond-standard-QM jamming resource capable of changing early joint distribution under a later intervention; no such device connected.",
        "cpu_sample_requires_future_bit_as_input_before_early_sample":True,
        "not_full_Vilasini_Colbeck_operational_certification":True
      },
      "postselection_trap":{
        "selection":"retain ordinary i.i.d. P(X,Z,B)=1/8 trials iff B=X XOR Z",
        "unconditional_original_attempts_kept":"1/2",
        "selected_joint_distribution_equals_hypothetical_jamming":True,
        "late_herald_required":True,
        "postselection_accepted_as_physical_evidence":False
      },
      "physical_experiment_performed":False,
      "physical_retrocausal_signal_observed":False,
      "scientific_conclusion":"EXACT_QUANTUM_FOUR_PHOTON_NO_FUTURE_SIGNALLING__HYPOTHETICAL_JAMMING_REQUIRES_NEW_RESOURCE",
      "refs":["10.1038/nphys2294","10.1103/h31d-wqyg"]
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,required=True)
    arg=parser.parse_args()
    if arg.out.exists():
        raise RuntimeError("REFUSE_OVERWRITE")
    a=report()
    arg.out.parent.mkdir(parents=True,exist_ok=True)
    arg.out.write_text(json.dumps(a,indent=2,sort_keys=True)+"\n",encoding="utf8")
    print(json.dumps({
       "standard_early_joint_TV":a["standard_early_joint_TV_between_late_settings"],
       "ideal_jamming_early_joint_TV":a["hypothetical_nonphysical_late_jamming_parity"]["joint_early_TV_between_future_choices"],
       "physical_retrocausality":False
    }))


if __name__=="__main__":
    main()
