#!/usr/bin/env python3
"""JANUS CPU Quantum Retro Emulator v1 -- exact small-system mathematics.

No quantum processor, spacetime CTC, physical postselection oracle or
backwards-time communication is implemented. The *physical* process runs
forward in ordinary CPU time. Conditional results require a later herald.
Origin: JANUS Principle and JANUS Retro Lab A/B experiments.

Implements:
  - arbitrary small pure statevector, H/X/Z/S/T/CNOT/CZ/SWAP
  - Bell entanglement; late X-choice; exact early reduced probabilities
  - normalized late postselection with explicit, non-free success probability
  - eight Bell pairs = an 8-bit conditional decoding toy
  - P-CTC-inspired K=Tr_loop(U)/d nonlinear postselection effective map
  - pure-Python all-attempts Monte Carlo and leakage-control diagnostics
  - full provenance and hard fail-closed prohibition on production promotion

References: Lloyd et al. PRL 106 040403 (2011);
Huang et al. PRR 8 023084 (2026); Qiskit Aer simulator docs.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import time

SQ=1/math.sqrt(2)
H=((SQ,SQ),(SQ,-SQ))
X=((0,1),(1,0))
Z=((1,0),(0,-1))
S=((1,0),(0,1j))
T=((1,0),(0,complex(math.cos(math.pi/4),math.sin(math.pi/4))))


class StateVector:
    def __init__(self, n: int, data=None):
        if not 1<=n<=16:
            raise ValueError("Statevector restricted to 1..16 qubits on CPU")
        self.n=n
        if data is None:
            self.a=[0j]*(1<<n)
            self.a[0]=1.+0j
        else:
            if len(data)!=(1<<n):
                raise ValueError("State length must equal 2^n")
            self.a=[complex(x) for x in data]
            if abs(self.norm()-1)>1e-9:
                raise ValueError("Initial state is not normalized")

    def norm(self):
        return sum(z.real*z.real+z.imag*z.imag for z in self.a)

    def apply(self, q, matrix):
        if not 0<=q<self.n:
            raise ValueError("Invalid target qubit")
        b=1<<q
        v=self.a
        m00,m01=complex(matrix[0][0]),complex(matrix[0][1])
        m10,m11=complex(matrix[1][0]),complex(matrix[1][1])
        for i in range(len(v)):
            if i&b:
                continue
            j=i|b
            x,y=v[i],v[j]
            v[i]=m00*x+m01*y
            v[j]=m10*x+m11*y
        return self

    def h(self,q):return self.apply(q,H)
    def x(self,q):return self.apply(q,X)
    def z(self,q):return self.apply(q,Z)
    def s(self,q):return self.apply(q,S)
    def t(self,q):return self.apply(q,T)

    def cx(self,control,target):
        if control==target or not 0<=control<self.n or not 0<=target<self.n:
            raise ValueError("Invalid CNOT qubits")
        bc,bt=1<<control,1<<target
        for i in range(len(self.a)):
            if i&bc and not i&bt:
                j=i|bt
                self.a[i],self.a[j]=self.a[j],self.a[i]
        return self

    def cz(self,control,target):
        if control==target or not 0<=control<self.n or not 0<=target<self.n:
            raise ValueError("Invalid CZ qubits")
        bc,bt=1<<control,1<<target
        for i in range(len(self.a)):
            if i&bc and i&bt:
                self.a[i]=-self.a[i]
        return self

    def swap(self,q,r):
        if q==r or not 0<=q<self.n or not 0<=r<self.n:
            raise ValueError("Invalid SWAP qubits")
        bq,br=1<<q,1<<r
        for i in range(len(self.a)):
            if bool(i&bq)!=bool(i&br) and not i&bq:
                j=i^bq^br
                self.a[i],self.a[j]=self.a[j],self.a[i]
        return self

    def marginal(self,q):
        p1=sum((z.real*z.real+z.imag*z.imag) for i,z in enumerate(self.a) if i&(1<<q))
        return (max(0.,1.-p1),p1)

    def project(self,q,bit):
        """Normalized conditional state. The herald probability is NOT free."""
        if bit not in (0,1):raise ValueError("bad outcome")
        p=self.marginal(q)[bit]
        if p<=1e-15:
            return 0.0,None
        scale=1/math.sqrt(p)
        v=[z*scale if bool(i&(1<<q))==bool(bit) else 0j
           for i,z in enumerate(self.a)]
        return p,StateVector(self.n,v)


def bell_late_message(bit):
    """Bell pair with late Pauli-X message: unconditional early bit stays 50/50."""
    st=StateVector(2).h(0).cx(0,1)
    prior=st.marginal(0)
    if bit:st.x(1)
    after=st.marginal(0)
    weight,conditional=st.project(1,0)  # future herald
    early_conditional=conditional.marginal(0) if conditional is not None else None
    return {
      "future_message_bit":bit,
      "early_marginal_before_late_choice":list(prior),
      "early_marginal_after_late_choice":list(after),
      "late_zero_herald_probability":weight,
      "early_distribution_given_LATER_herald":list(early_conditional),
      "unconditioned_early_readout_contains_future_bit":False,
    }


def bell_byte(message):
    """16-qubit statevector: 8 Bell pairs, early q even, late q odd."""
    if not 0<=message<256:raise ValueError("byte outside range")
    st=StateVector(16)
    for k in range(8):
        st.h(2*k).cx(2*k,2*k+1)
    for k in range(8):
        if (message>>k)&1:
            st.x(2*k+1)
    if abs(st.norm()-1)>1e-10:raise RuntimeError("bad Bell state norm")
    initial_early_marginals=[list(st.marginal(2*k)) for k in range(8)]
    success=1.
    for k in range(8):
        herald,st=st.project(2*k+1,0)
        success*=herald
        if st is None:raise RuntimeError("unexpected impossible herald")
    decoded=sum((1<<k) if st.marginal(2*k)[1]>.5 else 0 for k in range(8))
    return {
       "future_message_byte":f"{message:02x}",
       "unconditioned_early_marginal_each_bit":initial_early_marginals,
       "late_herald_all_zero_probability":success,
       "early_byte_given_later_herald":f"{decoded:02x}",
       "conditional_decoding_correct":decoded==message,
       "unconditional_early_byte_correct_probability":1/256,
       "operational_early_decoding_available":False,
       "late_herald_information_is_required":True
    }


def pctc_consistency_map():
    """Illustrative P-CTC transfer operator K=Tr_loop(CNOT_CR_to_loop)/2.

    On a chronology-respecting qubit, K=|0><0|. This is an EFFECTIVE
    renormalized conditional map, not a unitary signal channel and cannot
    be applied before knowing that postselection succeeded.
    """
    # joint 2-qubit CNOT on CR=qubit0, loop=qubit1
    cols=[]
    for basis in range(4):
        v=[0j]*4;v[basis]=1
        st=StateVector(2,v).cx(0,1)
        cols.append(st.a)
    k=[[sum(cols[in_cr+2*loop][out_cr+2*loop] for loop in range(2))/2
        for in_cr in range(2)] for out_cr in range(2)]
    # K|psi> normalized only on success, with total success prob ||Kpsi||^2
    samples={}
    for name,psi in {"zero":(1.,0.),"one":(0.,1.),"plus":(SQ,SQ)}.items():
        out=[sum(k[i][j]*psi[j] for j in range(2)) for i in range(2)]
        p=sum(abs(z)**2 for z in out)
        samples[name]={"acceptance_probability":round(p,12),
                       "final_conditional_probabilities":
                         [round(abs(z)**2/p,12) for z in out] if p>1e-15 else None,
                       "zero_probability_rejected":p<=1e-15}
    return {
      "map":"K = partial_trace_loop(CNOT_CR_to_loop) / 2",
      "K_real": [[float(z.real) for z in row] for row in k],
      "input_examples":samples,
      "physical_CTC_supplied":False,
      "nonlinear_renormalization_requires_postselection":True,
      "correct_interpretation":"A conditional P-CTC-inspired consistency operator, not an early-accessible communications device."
    }


def byte_monte_carlo(shots,seed,noise):
    if not 1000<=shots<=500000 or not 0<=noise<=.5:
        raise ValueError("bad sampling budget or noise")
    early=random.Random(seed^0x1A4F9)
    future=random.Random(seed^0x30BB7)
    corruption=random.Random(seed^0xD10F3)
    right_bits=right_bytes=selected=selected_right_bytes=0
    h0=hashlib.sha256();h1=hashlib.sha256()
    for _ in range(shots):
        # Strict conceptual chronology: t0 early before t1 future choice.
        a=early.getrandbits(8)
        h0.update(bytes([a]))
        m=future.getrandbits(8)
        h1.update(bytes([m]))
        err=sum((1<<j) for j in range(8) if corruption.random()<noise)
        late=a^m^err
        right_bits+=8-(a^m).bit_count()
        right_bytes+=int(a==m)
        if late==0:
            selected+=1
            selected_right_bytes+=int(a==m)
    return {
     "shots":shots,"seed":seed,"noise_per_late_bit":noise,
     "early_stream_sha256":h0.hexdigest(),
     "future_stream_sha256":h1.hexdigest(),
     "all_shots_bit_accuracy":right_bits/(8*shots),
     "all_shots_exact_byte_accuracy":right_bytes/shots,
     "late_postselection_acceptance":selected/shots,
     "accepted_count":selected,
     "accepted_exact_byte_accuracy":selected_right_bytes/selected if selected else None,
     "expected_all_shots_exact_byte_accuracy":1/256,
     "expected_selected_exact_byte_accuracy":(1-noise)**8,
     "matched_byte_is_not_a_usable_future_message":True,
     "physical_backward_channel_connected":False,
    }


def run(shots, seed):
    start=time.monotonic()
    pair=[bell_late_message(bit) for bit in (0,1)]
    bytes_=[bell_byte(m) for m in (0,0xA5,255)]
    examples=[byte_monte_carlo(shots,seed+int(1000*r),r) for r in (0.,.05,.20)]
    for record in bytes_:
        if abs(record["late_herald_all_zero_probability"]-1/256)>1e-10:
            raise RuntimeError("8-pair herald probability wrong")
        if not record["conditional_decoding_correct"]:
            raise RuntimeError("conditional 8-bit decode wrong")
    if any(abs(x["early_marginal_after_late_choice"][0]-.5)>1e-10 for x in pair):
        raise RuntimeError("unconditional early signaling incorrectly observed")
    pctc=pctc_consistency_map()
    if pctc["K_real"] != [[1.,0.],[0.,0.]]:
        raise RuntimeError("PCTC partial trace consistency failure")
    return {
      "schema":"janus.cpu_quantum_emulator.retro_audit.v1",
      "created_utc":datetime.now(timezone.utc).isoformat(),
      "engine":"Python stdlib exact statevector on GitHub hosted CPU, up to 16 qubits",
      "backend":"CPU_STATEVECTOR",
      "source_file":"experiments/ocean_transformer/janus_cpu_quantum_emulator.py",
      "quantum_ops":["H","X","Z","S","T","CNOT","CZ","SWAP","marginal","postselect"],
      "scaling":"Dense statevector uses 2^n complex amplitudes and exponential cost; no universal exponential quantum speedup is claimed.",
      "real_hardware_used":False,
      "real_timelike_curve_supplied":False,
      "genuine_time_reversal_implemented":False,
      "real_future_to_past_channel":False,
      "model_references":[
        {"doi":"10.1103/PhysRevLett.106.040403","role":"P-CTC mathematical model"},
        {"doi":"10.1103/tm83-sxpm","role":"quantum hardware postselection experiment; NOT the same 4-qubit circuit"},
        {"url":"https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.AerSimulator.html","role":"classical simulator backend architecture"},
        {"url":"https://github.com/quantumlib/qsim","role":"CPU vectorized statevector implementation"},
      ],
      "pair_exact":pair,
      "eight_pair_exact":bytes_,
      "pctc_illustrative_effective_operator":pctc,
      "monte_carlo":examples,
      "physical_channel_safety_gate":{
        "promote_to_JANUS":False,
        "reason":"No early unconditioned classical information about late independently chosen byte; simulated conditional output requires later postselection.",
        "required_for_future_candidate":"Real precommitted early measurement, authenticated physically independent late message, no late herald or metadata before time t0, independent replication, prospective error control."
      },
      "elapsed_seconds":round(time.monotonic()-start,3),
      "verdict":"SIMULATION_VERIFIED__LATE_POSTSELECTION_CORRELATION__NO_EARLY_MESSAGE",
      "production_checkpoint_changed":False,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--shots",type=int,default=65536)
    p.add_argument("--seed",type=int,default=20261106)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    result=run(args.shots,args.seed)
    file=Path(args.out)
    file.parent.mkdir(parents=True,exist_ok=True)
    if file.exists():raise RuntimeError("REFUSE_OVERWRITE")
    file.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"schema":result["schema"],"verdict":result["verdict"],
     "8bit":result["eight_pair_exact"],"pair":result["pair_exact"],
     "PCTC":result["pctc_illustrative_effective_operator"],
     "monte_carlo":result["monte_carlo"],
     "elapsed_seconds":result["elapsed_seconds"]},indent=2))


if __name__=="__main__":
    main()
