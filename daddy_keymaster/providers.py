"""DADDY_KEYMASTER provider activation preflight.

This is *not* a cloud client: no credentials, host access or network.
Read-only, local evidence can identify missing gates; only a separately reviewed
authenticated provider driver may grant live capacity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SOURCES = ("oracle_always_free", "boinc_volunteer", "ray_cluster")
GATES = {
    "oracle_always_free": ("account_owner_authenticated", "home_region_confirmed",
        "always_free_label_confirmed", "account_limits_readonly", "no_billable_resources",
        "approved_instance_running", "private_access_verified"),
    "boinc_volunteer": ("owner_operated_project", "project_tls_verified",
        "volunteer_explicit_consent", "signed_work_units", "server_validator_ready",
        "revocation_tested"),
    "ray_cluster": ("owner_controlled_nodes", "private_network_only",
        "token_auth_enabled", "trusted_job_allowlist", "endpoint_not_public",
        "revocation_tested"),
}
WAIT = {
    "oracle_always_free": "WAIT_ORACLE_ACCOUNT_AND_AUTHENTICATED_READONLY_ATTESTATION",
    "boinc_volunteer": "WAIT_OWN_BOINC_SERVER_AND_CONSENTING_VOLUNTEERS",
    "ray_cluster": "WAIT_PRIVATE_RAY_CLUSTER_AND_OWNER_APPROVAL",
}


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def checked_input(obj):
    if (not isinstance(obj, dict) or
        obj.get("schema") != "janus.daddy_keymaster.provider_activation_requests.v1" or
        obj.get("authority_delta") != 0 or
        obj.get("estimated_monthly_cost_usd") != 0 or
        obj.get("deploy_without_review") is not False or
        obj.get("remote_execution") is not False or
        obj.get("secrets_in_repository") is not False or
        set(obj.get("providers", {})) != set(SOURCES)):
        raise ValueError("DADDY_PROVIDER_ACTIVATION_POLICY_REJECTED")
    for source, value in obj["providers"].items():
        if not isinstance(value, dict) or set(value) != set(GATES[source]):
            raise ValueError("DADDY_PROVIDER_GATES_MISMATCH:" + source)
        if any(type(v) is not bool for v in value.values()):
            raise ValueError("DADDY_PROVIDER_GATE_NON_BOOLEAN:" + source)
    return obj


def oci_shape_preflight(instance):
    """Sanitize *locally obtained* OCI CLI 'compute instance get' data.

    Valid shape != authorization, free-tier label, cost, or running workload.
    A 1-OCPU/6-GB cap is conservatively below conflicting quota presentations.
    """
    if not isinstance(instance, dict) or not isinstance(instance.get("data"), dict):
        raise ValueError("DADDY_OCI_INSTANCE_GET_FORMAT")
    data = instance["data"]
    shape = data.get("shape")
    state = data.get("lifecycle-state")
    config = data.get("shape-config")
    if not isinstance(config, dict):
        raise ValueError("DADDY_OCI_SHAPE_CONFIG_REQUIRED")
    ocpus, memory = config.get("ocpus"), config.get("memory-in-gbs")
    if (type(ocpus) not in (int, float) or type(memory) not in (int, float) or
        type(ocpus) is bool or type(memory) is bool or
        not 0 < ocpus < 1000 or not 0 < memory < 10000):
        raise ValueError("DADDY_OCI_SHAPE_NUMERIC_REJECTED")
    # Do NOT copy OCIDs, IP addresses, instance tags or raw instance data.
    admissible = shape == "VM.Standard.A1.Flex" and ocpus <= 1 and memory <= 6
    result = {
        "schema": "janus.daddy_keymaster.oci_shape_preflight.v1",
        "shape": shape if shape in ("VM.Standard.A1.Flex", "VM.Standard.E2.1.Micro") else "OTHER",
        "lifecycle_state": state if state in ("RUNNING", "STOPPED", "TERMINATED") else "OTHER",
        "ocpus": ocpus, "memory_gb": memory,
        "fits_conservative_a1_shape": bool(admissible),
        "instance_currently_running": state == "RUNNING",
        "home_region_proven": False,
        "always_free_billing_proven": False,
        "ownership_proven": False,
        "network_reachability_tested": False,
        "enables_remote_dispatch": False,
        "status": ("SHAPE_PREFLIGHT_PASS_OWNERSHIP_STILL_UNKNOWN" if
                   admissible and state == "RUNNING" else
                   "SHAPE_PREFLIGHT_NOT_READY"),
        "authority_delta": 0,
    }
    result["receipt_sha256"] = digest(result)
    return result


def compile_status(requests, *, instance=None):
    checked_input(requests)
    results = {}
    for source in SOURCES:
        bits = requests["providers"][source]
        missing = [name for name in GATES[source] if not bits[name]]
        results[source] = {
            "source_selected": True,
            "provider": source,
            "owner_claims_present": [name for name in GATES[source] if bits[name]],
            "missing_requirements": missing,
            "readiness": WAIT[source] if missing else
                "CLAIMS_PRESENT_NEEDS_INDEPENDENT_AUTHENTICATED_VERIFICATION",
            "actual_capacity_attested": False,
            "remote_dispatch_allowed": False,
            "activation_authority": False,
        }
    if instance is not None:
        results["oracle_always_free"]["local_shape_preflight"] = oci_shape_preflight(instance)
    output = {
        "schema": "janus.daddy_keymaster.provider_readiness.v1",
        "status": "NO_EXTERNAL_PROVIDER_ACTIVATED",
        "providers": results,
        "source_requests_sha256": digest(requests),
        "authority_delta": 0,
        "cloud_instances_created": 0,
        "paid_resources_created": 0,
        "network_connections_attempted": 0,
        "warning": "SELF_ASSERTED_GATES_ARE_NOT_EVIDENCE_OF_OWNERSHIP_OR_FREE_BILLING",
    }
    output["receipt_sha256"] = digest(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=Path,
                        default=Path("daddy_keymaster/PROVIDER_ACTIVATION_REQUESTS.json"))
    parser.add_argument("--oci-instance-get", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    source = args.requests.read_bytes()
    if len(source) > 16000:
        raise ValueError("DADDY_REQUEST_TOO_LARGE")
    instance = None
    if args.oci_instance_get:
        raw = args.oci_instance_get.read_bytes()
        if len(raw) > 100000:
            raise ValueError("DADDY_OCI_LOCAL_INPUT_TOO_LARGE")
        instance = json.loads(raw)
    output = compile_status(json.loads(source), instance=instance)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(encode(output) + b"\n")
    print(json.dumps({"status": output["status"],
                      "oracle": output["providers"]["oracle_always_free"]["readiness"],
                      "boinc": output["providers"]["boinc_volunteer"]["readiness"],
                      "ray": output["providers"]["ray_cluster"]["readiness"],
                      "authority_delta": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
