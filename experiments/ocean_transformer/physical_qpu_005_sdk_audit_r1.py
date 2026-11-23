#!/usr/bin/env python3
"""Read-only SDK and launch-gate admission for JANUS QPU-005 (R1).

No IBM credentials, provider session, backend lookup, or Sampler.run() is allowed.
This amendment is not a change to the preregistered physical experiment.
"""
from __future__ import annotations

import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def run_audit() -> dict:
    import physical_qpu_005_ibm as ibm
    import physical_qpu_005_protocol as frozen
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
    from qiskit_ibm_runtime.executor_sampler import Sampler

    sdk = {"qiskit": version("qiskit"),
           "qiskit-ibm-runtime": version("qiskit-ibm-runtime")}
    if sdk != {"qiskit": "2.6.2", "qiskit-ibm-runtime": "0.50.0"}:
        raise RuntimeError("AUDIT_SDK_VERSION_DRIFT")
    if not (callable(QiskitRuntimeService) and callable(SamplerV2)
            and callable(Sampler)):
        raise RuntimeError("IBM_SDK_IMPORT_INCOMPATIBLE")

    # Production frozen circuit is constructed with real Qiskit, without backend.
    with patch("qiskit_ibm_runtime.QiskitRuntimeService",
               side_effect=AssertionError("REMOTE_PROVIDER_FORBIDDEN_IN_AUDIT")):
        circuit = ibm.circuit_structure()
        if circuit["actual_physical_circuit_executed"] is not False:
            raise AssertionError("FALSE_HARDWARE_CLAIM")
        if circuit["gates_in_program_order"][-2:] != ["if_else", "measure"]:
            raise AssertionError("DYNAMIC_BRANCH_MISSING")
        if circuit["gates_in_program_order"].count("measure") != 3:
            raise AssertionError("EXACT_MEASUREMENTS_CHANGED")
        # Absence of credentials MUST fail before any service or QPU call.
        with patch.dict(os.environ, {"IBM_QUANTUM_API_KEY": "",
                                     "IBM_QUANTUM_OPEN_INSTANCE": ""}):
            try:
                ibm.submit("/tmp/SHOULD_NEVER_BE_WRITTEN_qpu005.json")
            except RuntimeError as exc:
                if str(exc) != "MISSING_IBM_QUANTUM_OPEN_CREDENTIALS":
                    raise
            else:
                raise AssertionError("MISSING_CREDENTIALS_DID_NOT_BLOCK_SUBMISSION")

    manual = (ROOT / ".github/workflows/janus-physical-qpu-005-manual.yml").read_text()
    required = (
        "workflow_dispatch:",
        "github.event_name == 'workflow_dispatch'",
        "github.ref == 'refs/heads/main'",
        "github.actor == 'Hawkar-usls'",
        "github.run_attempt == 1",
        "inputs.approve_provider_run == true",
        "inputs.confirm_open_plan == true",
        "inputs.phase == 'submit'",
        "Verify frozen plan hash before provider calls",
        "EXPECTED_FROZEN_SHA:",
        "environment: janus-qpu005-approval",
        "concurrency:",
        "cancel-in-progress: false",
        "permissions:",
        "contents: read",
        "actions: read",
    )
    if any(s not in manual for s in required):
        raise AssertionError("HARDWARE_WORKFLOW_GUARD_MISSING")
    if any(line.lstrip().startswith(("schedule:", "push:", "pull_request:"))
           for line in manual.splitlines()):
        raise AssertionError("HARDWARE_WORKFLOW_NOT_MANUAL_ONLY")

    proposal = frozen.plan()
    frozen.verify_plan(proposal)
    return {
        "schema": "janus.ocean.qpu005_sdk_admission_r1",
        "baseline_experiment": "JANUS-RETRO-PHYSICAL-005",
        "baseline_merge_commit": "8fa54f25c5bf3f5593db6b7ddc2a3a8da5f78f19",
        "frozen_preregistration_sha256": proposal["preregistered_sha256"],
        "frozen_protocol_source_sha256": hashlib.sha256(
            (HERE / "physical_qpu_005_protocol.py").read_bytes()).hexdigest(),
        "frozen_adapter_source_sha256": hashlib.sha256(
            (HERE / "physical_qpu_005_ibm.py").read_bytes()).hexdigest(),
        "offline_sdk": sdk,
        "qiskit_dynamic_circuit_structure": "PASS",
        "ibm_service_and_sampler_imports": "PASS",
        "legacy_sampler_v2": "AVAILABLE_BUT_DEPRECATED_SINCE_RUNTIME_0_50",
        "new_client_side_sampler_import": "PASS_NOT_USED_IN_FROZEN_ADAPTER",
        "credentials_absent_submit_refusal": "PASS",
        "workflow_static_guard_audit": "PASS",
        "provider_service_created": False,
        "provider_api_requested": False,
        "physical_backend_compilation_tested": False,
        "real_qpu_job_submitted": False,
        "qpu_time_used": False,
        "physical_retrocausality_proven": False,
        "limitations": [
            "No hardware target or scheduling capability validated",
            "No provider authentication or Open Plan tier inspection",
            "Environment protection must be separately configured and reviewed",
            "Duplicate fresh manual dispatches are NOT globally prevented",
            "Legacy SamplerV2 requires later separately reviewed migration",
        ],
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    args = p.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("REFUSE_OVERWRITE_EVIDENCE")
    result = run_audit()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "OFFLINE_SDK_AUDIT_PASS",
                      "sdk": result["offline_sdk"],
                      "qpu_time_used": False}, sort_keys=True))
