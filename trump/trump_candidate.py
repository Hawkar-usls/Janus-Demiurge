#!/usr/bin/env python3
"""JANUS TRUMP candidate runtime loader.

TRUMP is allowed to WAKE and execute admitted candidate research tissue, but the
runtime never upgrades candidate output into proof/scientific authority.

The executable candidate is fetched from an exact Fundamentum commit/path and
verified against its immutable Git blob SHA before import.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import urllib.parse
import urllib.request
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "TRUMP_MANIFEST.json"
USER_AGENT = "JANUS-TRUMP-CANDIDATE/0.1"


class TrumpCandidateError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def load_manifest(path: Path = MANIFEST_PATH) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_manifest(data)
    return data


def validate_manifest(manifest: dict) -> None:
    if manifest.get("schema") != "janus.trump.manifest.v0.1":
        raise TrumpCandidateError("TRUMP_MANIFEST_SCHEMA_MISMATCH")
    if manifest.get("status") != "CANDIDATE_RUNTIME_TISSUE":
        raise TrumpCandidateError("TRUMP_NOT_CANDIDATE_RUNTIME_TISSUE")
    activation = manifest.get("activation", {})
    required_true = ("wake_allowed", "use_allowed", "candidate_experiment_allowed", "self_improvement_allowed")
    if any(activation.get(k) is not True for k in required_true):
        raise TrumpCandidateError("TRUMP_CANDIDATE_WAKE_OR_USE_DISABLED")
    required_false = (
        "proof_authority",
        "scientific_claim_promotion_authority",
        "command_authority",
        "external_effect_authority",
        "physical_runtime_effect_authority",
    )
    if any(activation.get(k) is not False for k in required_false):
        raise TrumpCandidateError("TRUMP_AUTHORITY_CEILING_VIOLATION")
    boundary = manifest.get("scientific_boundary", {})
    if boundary.get("P_VS_NP") != "OPEN" or boundary.get("P_equals_NP_proved") is not False:
        raise TrumpCandidateError("TRUMP_SCIENTIFIC_BOUNDARY_VIOLATION")
    sources = manifest.get("candidate_sources")
    if not isinstance(sources, list) or not sources:
        raise TrumpCandidateError("TRUMP_NO_CANDIDATE_SOURCE")
    for source in sources:
        if source.get("repository") != "Hawkar-usls/Janus-Fundamentum":
            raise TrumpCandidateError("TRUMP_SOURCE_REPOSITORY_NOT_ADMITTED")
        commit = str(source.get("pinned_commit", ""))
        blob = str(source.get("git_blob_sha", ""))
        path = str(source.get("path", ""))
        if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
            raise TrumpCandidateError("TRUMP_SOURCE_COMMIT_INVALID")
        if len(blob) != 40 or any(c not in "0123456789abcdef" for c in blob):
            raise TrumpCandidateError("TRUMP_SOURCE_BLOB_INVALID")
        if path.startswith("/") or ".." in Path(path).parts:
            raise TrumpCandidateError("TRUMP_SOURCE_PATH_INVALID")
        sb = source.get("scientific_boundary", {})
        if sb.get("P_VS_NP") != "OPEN" or sb.get("claims_p_eq_np") is not False:
            raise TrumpCandidateError("TRUMP_SOURCE_SCIENTIFIC_BOUNDARY_VIOLATION")


def primary_source(manifest: dict) -> dict:
    for source in manifest["candidate_sources"]:
        if source.get("runtime_role") == "PRIMARY_EXECUTABLE_CANDIDATE":
            return source
    raise TrumpCandidateError("TRUMP_PRIMARY_CANDIDATE_MISSING")


def raw_source_url(source: dict) -> str:
    owner, repo = source["repository"].split("/", 1)
    safe_path = "/".join(urllib.parse.quote(p, safe="") for p in source["path"].split("/"))
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{source['pinned_commit']}/{safe_path}"


def fetch_source_bytes(source: dict, opener: Callable[..., Any] = urllib.request.urlopen) -> bytes:
    req = urllib.request.Request(raw_source_url(source), headers={"User-Agent": USER_AGENT})
    with opener(req, timeout=30) as response:
        data = response.read()
    actual = git_blob_sha(data)
    if actual != source["git_blob_sha"]:
        raise TrumpCandidateError(f"TRUMP_SOURCE_BLOB_MISMATCH:{actual}")
    return data


def import_candidate_module(data: bytes, source: dict):
    with tempfile.TemporaryDirectory(prefix="janus-trump-") as tmp:
        path = Path(tmp) / "candidate.py"
        path.write_bytes(data)
        spec = importlib.util.spec_from_file_location("janus_trump_candidate_source", path)
        if spec is None or spec.loader is None:
            raise TrumpCandidateError("TRUMP_CANDIDATE_IMPORT_SPEC_FAILED")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.modules.pop(spec.name, None)
        missing = [name for name in source.get("required_entrypoints", []) if not callable(getattr(module, name, None))]
        if missing:
            raise TrumpCandidateError("TRUMP_ENTRYPOINT_MISSING:" + ",".join(missing))
        return module


def base_receipt(manifest: dict, source: dict) -> dict:
    return {
        "schema": "janus.trump.candidate_runtime_receipt.v0.1",
        "component": "TRUMP",
        "mode": "CANDIDATE_RUNTIME_TISSUE",
        "manifest_digest": sha256_json(manifest),
        "source": {
            "repository": source["repository"],
            "commit": source["pinned_commit"],
            "path": source["path"],
            "git_blob_sha": source["git_blob_sha"],
        },
        "authority": {
            "proof_authority": False,
            "scientific_claim_promotion_authority": False,
            "command_authority": False,
            "external_effect_authority": False,
            "physical_runtime_effect_authority": False,
        },
        "scientific_boundary": {
            "TRUMP_finished": False,
            "polynomial_time_SAT_proved": False,
            "P_equals_NP_proved": False,
            "P_VS_NP": "OPEN",
        },
    }


def seal_receipt(receipt: dict) -> dict:
    out = dict(receipt)
    out["receipt_hash"] = sha256_json(receipt)
    return out


def status_receipt() -> dict:
    manifest = load_manifest()
    source = primary_source(manifest)
    receipt = base_receipt(manifest, source)
    receipt.update({
        "terminal": "TRUMP_CANDIDATE_RUNTIME_AVAILABLE",
        "wake_allowed": True,
        "use_allowed": True,
        "self_improvement_allowed": True,
        "source_loaded": False,
        "execution_performed": False,
    })
    return seal_receipt(receipt)


def verify_source_receipt() -> dict:
    manifest = load_manifest()
    source = primary_source(manifest)
    data = fetch_source_bytes(source)
    receipt = base_receipt(manifest, source)
    receipt.update({
        "terminal": "TRUMP_CANDIDATE_SOURCE_VERIFIED",
        "source_loaded": True,
        "execution_performed": False,
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "source_bytes": len(data),
    })
    return seal_receipt(receipt)


def selftest_receipt() -> dict:
    manifest = load_manifest()
    source = primary_source(manifest)
    data = fetch_source_bytes(source)
    module = import_candidate_module(data, source)
    module.selftest()
    receipt = base_receipt(manifest, source)
    receipt.update({
        "terminal": "TRUMP_CANDIDATE_SELFTEST_PASS",
        "source_loaded": True,
        "execution_performed": True,
        "operation": "CANDIDATE_SELFTEST",
        "candidate_result_promoted": False,
    })
    return seal_receipt(receipt)


def solve_receipt(clauses: list, cap_exponent: int, extension_exponent: int) -> dict:
    manifest = load_manifest()
    source = primary_source(manifest)
    data = fetch_source_bytes(source)
    module = import_candidate_module(data, source)
    result = module.solve_fail_closed(
        clauses,
        cap_exponent=cap_exponent,
        extension_exponent=extension_exponent,
    )
    if result.get("scientific_boundary", {}).get("P_VS_NP") != "OPEN":
        raise TrumpCandidateError("TRUMP_RESULT_SCIENTIFIC_BOUNDARY_VIOLATION")
    receipt = base_receipt(manifest, source)
    receipt.update({
        "terminal": "TRUMP_CANDIDATE_COMPUTATION_COMPLETE",
        "source_loaded": True,
        "execution_performed": True,
        "operation": "SOLVE_FAIL_CLOSED_CANDIDATE",
        "candidate_result_promoted": False,
        "input_digest": hashlib.sha256(canonical_bytes(clauses)).hexdigest(),
        "result": result,
    })
    return seal_receipt(receipt)


def _read_json_input(path: str | None) -> Any:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.load(sys.stdin)


def main() -> int:
    parser = argparse.ArgumentParser(description="JANUS TRUMP candidate runtime")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("verify-source")
    sub.add_parser("selftest")
    solve = sub.add_parser("solve")
    solve.add_argument("--input", help="JSON file containing a CNF array; default stdin")
    solve.add_argument("--cap-exponent", type=int, default=2)
    solve.add_argument("--extension-exponent", type=int, default=1)
    args = parser.parse_args()

    if args.command == "status":
        out = status_receipt()
    elif args.command == "verify-source":
        out = verify_source_receipt()
    elif args.command == "selftest":
        out = selftest_receipt()
    elif args.command == "solve":
        clauses = _read_json_input(args.input)
        if not isinstance(clauses, list):
            raise TrumpCandidateError("TRUMP_INPUT_MUST_BE_CNF_ARRAY")
        out = solve_receipt(clauses, args.cap_exponent, args.extension_exponent)
    else:
        raise AssertionError(args.command)

    print(json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
