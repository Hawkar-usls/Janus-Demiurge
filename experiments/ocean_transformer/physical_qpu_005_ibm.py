#!/usr/bin/env python3
"""Opt-in IBM Quantum hardware adapter for JANUS-RETRO-PHYSICAL-005.

NEVER scheduled. No hardware submission unless explicitly invoked with a
separately configured IBM Quantum Open Plan API key and instance CRN.
The one-run experiment is fixed by physical_qpu_005_protocol.plan().

The compiled circuit encodes order but per-shot timing is NOT independently
certified. One processor is not a spacelike-separated optical experiment.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path

import physical_qpu_005_protocol as protocol


def build_circuit():
    from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
    q = QuantumRegister(3, "q")
    early = ClassicalRegister(1, "early")
    setting = ClassicalRegister(1, "setting")
    late = ClassicalRegister(1, "late")
    circ = QuantumCircuit(q, early, setting, late, name="JANUS_PQPU_005")
    circ.h(q[0])
    circ.cx(q[0], q[1])
    circ.barrier(q)
    circ.measure(q[0], early[0])
    circ.barrier(q)
    circ.h(q[2])
    circ.measure(q[2], setting[0])
    circ.barrier(q)
    with circ.if_test((setting[0], 1)):
        circ.h(q[1])
    circ.measure(q[1], late[0])
    return circ


def circuit_structure():
    circ = build_circuit()
    names = [op.operation.name for op in circ.data]
    if names != ["h", "cx", "barrier", "measure", "barrier",
                 "h", "measure", "barrier", "if_else", "measure"]:
        raise RuntimeError("QPU_CIRCUIT_TIMELINE_MODIFIED")
    return {
        "qpu_qubits": 3,
        "classical_registers": list(protocol.REGISTERS),
        "gates_in_program_order": names,
        "conditional_basis_setting_generated_after_early_readout_in_program": True,
        "shot_level_hardware_timestamps_verified": False,
        "actual_physical_circuit_executed": False,
    }


def require_credentials():
    # Never print secrets or backend exceptions. No fallback to simulation.
    token=os.getenv("IBM_QUANTUM_API_KEY","")
    instance=os.getenv("IBM_QUANTUM_OPEN_INSTANCE","")
    if not token or not instance:
        raise RuntimeError("MISSING_IBM_QUANTUM_OPEN_CREDENTIALS")
    return token, instance


def service_from_secrets():
    from qiskit_ibm_runtime import QiskitRuntimeService
    token,instance=require_credentials()
    return QiskitRuntimeService(
        channel="ibm_quantum_platform", token=token, instance=instance)


def _compiled_circuit(backend, artifact_dir):
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
    from qiskit import qpy
    pm = generate_preset_pass_manager(
        backend=backend, optimization_level=0, seed_transpiler=20261109)
    isa=pm.run(build_circuit())
    # Only submit if essential measurements and dynamic branch survive compilation.
    ops=[node.operation.name for node in isa.data]
    if "if_else" not in ops or ops.count("measure") < 3:
        raise RuntimeError("TRANSPILER_DROPPED_DYNAMIC_EXPERIMENT")
    buf=BytesIO()
    qpy.dump(isa,buf)
    code=buf.getvalue()
    out=Path(artifact_dir)
    out.mkdir(parents=True,exist_ok=True)
    compiled=out/"actual_compiled_circuit.qpy"
    if compiled.exists():
        raise RuntimeError("REFUSE_OVERWRITE_COMPILED_QPU_CIRCUIT")
    compiled.write_bytes(code)
    return isa,hashlib.sha256(code).hexdigest()


def submit(output):
    """Submit exactly one job. Deliberately does NOT block waiting for queue."""
    service=service_from_secrets()
    backend=service.least_busy(operational=True,simulator=False,dynamic_circuits=True)
    if backend.configuration().simulator or not backend.status().operational:
        raise RuntimeError("NONPHYSICAL_OR_OFFLINE_QPU_SELECTED")
    isa,compiled_sha=_compiled_circuit(backend,Path(output).parent)
    from qiskit_ibm_runtime import SamplerV2
    sampler=SamplerV2(mode=backend)
    # ONE QPU workload with a fixed number of 4096 shots.
    job=sampler.run([isa],shots=protocol.SHOTS)
    metadata={
        "schema":protocol.SCHEMA,
        "phase":"REAL_QPU_JOB_SUBMITTED",
        "provider":"IBM_QUANTUM",
        "backend_name":backend.name,
        "backend_simulator":False,
        "job_id":job.job_id(),
        "compiled_circuit_sha256":compiled_sha,
        "precommit_sha256":protocol.plan()["preregistered_sha256"],
        "submitted_one_fixed_4096_shot_qpu_job":True,
        "all_shots_raw_not_yet_retrieved":True,
        "physical_retrocausality_proven":False,
    }
    protocol.write_once(output,metadata)
    print(json.dumps({"status":"ONE_REAL_QPU_JOB_SUBMITTED",
                      "job_id":metadata["job_id"],
                      "backend":metadata["backend_name"],
                      "retrocausality_proven":False},sort_keys=True))


def retrieve(submission_path, output):
    """Read only the originally submitted job, no hidden retries."""
    submitted=json.loads(Path(submission_path).read_text())
    if (submitted.get("schema")!=protocol.SCHEMA or
        submitted.get("phase")!="REAL_QPU_JOB_SUBMITTED" or
        submitted.get("precommit_sha256")!=protocol.plan()["preregistered_sha256"] or
        submitted.get("submitted_one_fixed_4096_shot_qpu_job") is not True):
        raise ValueError("NOT_THE_PREREGISTERED_QPU_JOB")
    service=service_from_secrets()
    job=service.job(submitted["job_id"])
    backend=job.backend()
    if backend.name!=submitted["backend_name"] or backend.configuration().simulator:
        raise ValueError("QPU_BACKEND_CHANGED_OR_SIMULATED")
    # A queued/incomplete job causes a failure; no request for a replacement job.
    if str(job.status()).lower() not in ("jobstatus.done", "done", "completed"):
        raise RuntimeError("PREREGISTERED_QPU_JOB_NOT_FINISHED_YET")
    pub=job.result()[0]
    raw_data=pub.data
    early=raw_data.early.get_bitstrings()
    setting=raw_data.setting.get_bitstrings()
    late=raw_data.late.get_bitstrings()
    if not (len(early)==len(setting)==len(late)==protocol.SHOTS):
        raise ValueError("PROVIDER_DID_NOT_RETURN_ALL_4096_SHOTS")
    data=[[a,c,b] for a,c,b in zip(early,setting,late)]
    metadata={
        "provider":"IBM_QUANTUM",
        "backend_name":submitted["backend_name"],
        "backend_simulator":False,
        "job_id":submitted["job_id"],
        "compiled_circuit_sha256":submitted["compiled_circuit_sha256"],
    }
    report=protocol.assess(protocol.plan(),data,metadata)
    report["provider_service_job_pointer"]=submitted["job_id"]
    report["provider_metadata_not_independently_notarized"]=True
    report["raw_result_from_qpu_job_not_random_generator"]=True
    protocol.write_once(output,report)
    print(json.dumps({
        "status":report["status"],"job_id":submitted["job_id"],
        "shots":report["shot_count"],
        "fisher_p":report["primary"]["fisher_exact_two_sided_p"],
        "physical_retrocausality_proven":False,
    },sort_keys=True))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=("structure","submit","retrieve"))
    parser.add_argument("--submission")
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    if args.mode=="structure":
        protocol.write_once(args.output,circuit_structure())
    elif args.mode=="submit":
        submit(args.output)
    else:
        if not args.submission:
            parser.error("--submission required")
        retrieve(args.submission,args.output)

if __name__=="__main__":
    main()
