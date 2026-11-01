"""Bounded process-separated probation for one SHA-pinned modern JANUS organ.

The historical Nexus ABI and E-drive graph are *data* here, never executable
modules. Child is a clean Python process, not a kernel sandbox. Explicit owner
approval remains mandatory; only the repo-local fixed allowlist is admitted.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "demiurge" / "LEGACY_PROCESS_PROBATION_POLICY.json"
SCHEMA = "janus.demiurge.legacy_process_probation_policy.v1"
REQUEST_SCHEMA = "janus.demiurge.legacy_subprocess_request.v1"
RECEIPT_SCHEMA = "janus.demiurge.legacy_subprocess_receipt.v1"
MAX_REQUEST_BYTES = 300000
MAX_STDOUT_BYTES = 12000
FILE_NAMES = {
    "nexus": "restored/legacy_nexus_conductor.py",
    "graph_port": "restored/legacy_core_graph_query_port.py",
    "graph_query": "restored/memory_graph_query.py",
    "worker": "tools/legacy_probation_worker.py",
}


class ProcessProbationHold(ValueError):
    """A policy or process failed without granting any runtime authority."""


def canonical_bytes(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _load_policy() -> dict:
    if POLICY_PATH.is_symlink() or not POLICY_PATH.is_file() or POLICY_PATH.stat().st_size > 12000:
        raise ProcessProbationHold("MISSING_IMMUTABLE_POLICY_HOLD")
    try:
        policy = json.loads(POLICY_PATH.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        raise ProcessProbationHold("POLICY_JSON_HOLD") from exc
    return policy


def _check_policy(policy: dict) -> None:
    if not isinstance(policy, dict) or policy.get("schema") != SCHEMA:
        raise ProcessProbationHold("POLICY_SCHEMA_HOLD")
    if policy.get("mode") != "OWNER_APPROVED_SYNTHETIC_PROBATION_ONLY":
        raise ProcessProbationHold("POLICY_MODE_HOLD")
    if policy.get("enabled") is not True or policy.get("target") != "legacy_graph_query":
        raise ProcessProbationHold("POLICY_DISABLED_OR_TARGET_HOLD")
    if policy.get("files") != FILE_NAMES:
        raise ProcessProbationHold("UNEXPECTED_CODE_PATH_HOLD")
    hashes = policy.get("file_sha256")
    if not isinstance(hashes, dict) or set(hashes) != set(FILE_NAMES):
        raise ProcessProbationHold("SOURCE_PINSET_HOLD")
    for name, rel in FILE_NAMES.items():
        want = hashes[name]
        if (not isinstance(want, str) or len(want) != 64
                or any(c not in "0123456789abcdef" for c in want)):
            raise ProcessProbationHold("BAD_SOURCE_PIN_HOLD")
        path = ROOT / rel
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 120000:
            raise ProcessProbationHold("SOURCE_FILE_HOLD")
        if hashlib.sha256(path.read_bytes()).hexdigest() != want:
            raise ProcessProbationHold("CODE_IDENTITY_MISMATCH_HOLD")
    artifact = policy.get("archive_artifact_sha256")
    if (not isinstance(artifact, str) or len(artifact) != 64
            or any(c not in "0123456789abcdef" for c in artifact)):
        raise ProcessProbationHold("ARCHIVE_PIN_HOLD")
    permissions = policy.get("authority")
    if not isinstance(permissions, dict) or any(permissions.get(key) is not False for key in (
        "runs_untrusted_legacy_python", "production_activation",
        "allows_graph_mutation", "models_may_be_promoted",
        "grants_security_sandbox", "dispatches_external_jobs"
    )):
        raise ProcessProbationHold("AUTHORITY_FIREWALL_HOLD")


def _run_with_policy(artifact: dict, start_id: str, end_id: str, *,
                     operator_approved: bool, timeout_seconds: float,
                     policy: dict) -> dict:
    if operator_approved is not True:
        raise PermissionError("OPERATOR_PROBATION_APPROVAL_REQUIRED")
    _check_policy(policy)
    if type(timeout_seconds) not in (int, float) or not 0.3 <= timeout_seconds <= 10.0:
        raise ProcessProbationHold("TIMEOUT_POLICY_HOLD")
    if not isinstance(artifact, dict):
        raise ProcessProbationHold("ARCHIVE_OBJECT_HOLD")
    if not all(isinstance(x, str) and 0 < len(x) < 96 for x in (start_id, end_id)):
        raise ProcessProbationHold("GRAPH_QUERY_ID_HOLD")
    canon = canonical_bytes(artifact)
    if len(canon) > MAX_REQUEST_BYTES - 4096:
        raise ProcessProbationHold("ARCHIVE_INPUT_BOUND_HOLD")
    digest = hashlib.sha256(canon).hexdigest()
    if digest != policy["archive_artifact_sha256"]:
        raise ProcessProbationHold("ARCHIVE_SOURCE_SHA_MISMATCH")
    request = {
        "schema": REQUEST_SCHEMA, "target": "legacy_graph_query",
        "graph": artifact, "start_id": start_id, "end_id": end_id,
        "artifact_sha256": digest, "file_sha256": policy["file_sha256"],
    }
    payload = canonical_bytes(request)
    if len(payload) > MAX_REQUEST_BYTES:
        raise ProcessProbationHold("REQUEST_BOUND_HOLD")
    script = ROOT / FILE_NAMES["worker"]
    # -I ignores user site and PYTHONPATH; -S skips site initialization;
    # -B disables bytecode writes. This is NOT network/filesystem sandboxing.
    command = [sys.executable, "-I", "-S", "-B", str(script)]
    # No inherited tokens/credentials. Temporary cwd contains no owner data.
    with tempfile.TemporaryDirectory(prefix="janus_legacy_child_") as cwd:
        try:
            completed = subprocess.run(command, input=payload, capture_output=True,
                                       cwd=cwd, env={}, timeout=float(timeout_seconds),
                                       check=False)
        except subprocess.TimeoutExpired as exc:
            raise ProcessProbationHold("SUBPROCESS_TIMEOUT_KILLED") from exc
        except OSError as exc:
            raise ProcessProbationHold("SUBPROCESS_LAUNCH_HOLD") from exc
    if completed.returncode != 0:
        raise ProcessProbationHold("CHILD_NONZERO_EXIT_HOLD")
    if len(completed.stdout) > MAX_STDOUT_BYTES or not completed.stdout:
        raise ProcessProbationHold("CHILD_OUTPUT_BOUND_HOLD")
    try:
        response = json.loads(completed.stdout.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ProcessProbationHold("CHILD_BAD_JSON_HOLD") from exc
    if not isinstance(response, dict) or response.get("schema") != RECEIPT_SCHEMA:
        raise ProcessProbationHold("CHILD_RECEIPT_SCHEMA_HOLD")
    if response.get("status") != "PASS_PROCESS_SEPARATED_SYNTHETIC_PROBATION":
        raise ProcessProbationHold("CHILD_PROBATION_HOLD")
    if response.get("archive_artifact_sha256") != digest:
        raise ProcessProbationHold("CHILD_ARCHIVE_BINDING_HOLD")
    organ = response.get("organ_receipt")
    if (not isinstance(organ, dict) or organ.get("schema") != "janus.demiurge.legacy_graph_query_evidence.v1"
            or organ.get("source_archive_only") is not True
            or organ.get("mutation_authority") is not False
            or organ.get("scientific_authority") is not False
            or not isinstance(organ.get("found"), bool)
            or not isinstance(organ.get("path"), list)
            or len(organ["path"]) > 9
            or not all(isinstance(x, str) and len(x) < 96 for x in organ["path"])):
        raise ProcessProbationHold("CHILD_ORGAN_RECEIPT_HOLD")
    auth = response.get("authority")
    if not isinstance(auth, dict) or any(auth.get(k) is not False for k in (
        "production_activation", "model_promoted", "graph_mutation",
        "legacy_source_executed", "os_security_sandbox_proven",
        "network_namespace_isolated"
    )):
        raise ProcessProbationHold("CHILD_AUTHORITY_CEILING_HOLD")
    # Return the limited child receipt (never stderr, env vars, source strings).
    return response


def run_approved_process_probation(artifact: dict, start_id: str, end_id: str, *,
                                   operator_approved=False, timeout_seconds=4.0) -> dict:
    """Public entrypoint: only repo-pinned policy may authorize a subprocess."""
    return _run_with_policy(artifact, start_id, end_id,
                            operator_approved=operator_approved,
                            timeout_seconds=timeout_seconds,
                            policy=_load_policy())
