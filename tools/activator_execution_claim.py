#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict

from tools.activator_mailbox_poller import canonical_hash
from tools.activator_readonly_execution import verify_grant

TARGET_REPOSITORY = "Hawkar-usls/Janus-Demiurge"
CLAIM_BRANCH = "janus/activator-mailbox"
CLAIM_ROOT = ".janus/mailbox/execution-claims"
SCHEMA = "janus.demiurge.execution_claim.v1.0"


def _claim_path(grant_id: str) -> str:
    return f"{CLAIM_ROOT}/{grant_id}.json"


def _api_url(grant_id: str) -> str:
    path = urllib.parse.quote(_claim_path(grant_id), safe="/")
    return f"https://api.github.com/repos/{TARGET_REPOSITORY}/contents/{path}"


def _raw_url(grant_id: str) -> str:
    return (
        f"https://raw.githubusercontent.com/{TARGET_REPOSITORY}/{CLAIM_BRANCH}/"
        f"{_claim_path(grant_id)}"
    )


def _request(url: str, *, token: str = "", data: bytes | None = None, method: str = "GET") -> urllib.request.Request:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "JANUS-Demiurge-Execution-Claim/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        headers["Content-Type"] = "application/json"
    return urllib.request.Request(url, data=data, method=method, headers=headers)


def _read_existing(grant_id: str, *, opener: Callable[..., Any]) -> Dict[str, Any] | None:
    try:
        response = opener(_request(_raw_url(grant_id)), timeout=15.0)
        return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def verify_claim(claim: Dict[str, Any]) -> bool:
    if not isinstance(claim, dict):
        return False
    claimed = str(claim.get("claim_hash") or "")
    if len(claimed) != 64:
        return False
    body = dict(claim)
    body.pop("claim_hash", None)
    return all([
        canonical_hash(body) == claimed,
        claim.get("schema") == SCHEMA,
        claim.get("target_repository") == TARGET_REPOSITORY,
        isinstance(claim.get("grant_id"), str),
        isinstance(claim.get("grant_hash"), str),
        claim.get("command_authority_granted") is False,
        claim.get("claim_authority_granted") is False,
        claim.get("scientific_evidence_authority_granted") is False,
        claim.get("external_effect_authorized") is False,
        claim.get("physical_runtime_effect_authorized") is False,
    ])


def acquire(
    grant: Dict[str, Any],
    *,
    token: str,
    transport_lane: str,
    workflow_run_id: str,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> Dict[str, Any]:
    if not verify_grant(grant):
        return {
            "terminal": "CLAIM_REJECTED_INVALID_GRANT",
            "grant_id": str(grant.get("grant_id") or ""),
            "grant_hash": str(grant.get("grant_hash") or ""),
            "execution_permitted": False,
        }
    if not str(token).strip():
        return {
            "terminal": "CLAIM_BLOCKED_NO_LOCAL_REPOSITORY_TOKEN",
            "grant_id": grant["grant_id"],
            "grant_hash": grant["grant_hash"],
            "execution_permitted": False,
        }

    claim = {
        "schema": SCHEMA,
        "created_at": time.time(),
        "target_repository": TARGET_REPOSITORY,
        "grant_id": grant["grant_id"],
        "grant_hash": grant["grant_hash"],
        "transport_lane": str(transport_lane),
        "workflow_run_id": str(workflow_run_id),
        "exactly_once_scope": "GRANT_ID_ACROSS_ALL_ACTIVATOR_TRANSPORT_LANES",
        "command_authority_granted": False,
        "claim_authority_granted": False,
        "scientific_evidence_authority_granted": False,
        "external_effect_authorized": False,
        "physical_runtime_effect_authorized": False,
    }
    claim["claim_hash"] = canonical_hash(claim)
    encoded = base64.b64encode((json.dumps(claim, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")).decode("ascii")
    payload = json.dumps({
        "message": f"Activator execution claim {grant['grant_id']}",
        "content": encoded,
        "branch": CLAIM_BRANCH,
    }, separators=(",", ":")).encode("utf-8")

    try:
        response = opener(_request(_api_url(grant["grant_id"]), token=token, data=payload, method="PUT"), timeout=20.0)
        status = int(getattr(response, "status", getattr(response, "code", 0)) or 0)
        if status in {200, 201}:
            return {
                "terminal": "CLAIM_ACQUIRED",
                "grant_id": grant["grant_id"],
                "grant_hash": grant["grant_hash"],
                "claim_hash": claim["claim_hash"],
                "transport_lane": transport_lane,
                "execution_permitted": True,
            }
        return {
            "terminal": "CLAIM_OUTCOME_UNDETERMINED",
            "grant_id": grant["grant_id"],
            "grant_hash": grant["grant_hash"],
            "execution_permitted": False,
            "http_status": status,
        }
    except urllib.error.HTTPError as exc:
        if exc.code not in {409, 422}:
            return {
                "terminal": "CLAIM_OUTCOME_UNDETERMINED",
                "grant_id": grant["grant_id"],
                "grant_hash": grant["grant_hash"],
                "execution_permitted": False,
                "http_status": exc.code,
            }
        existing = _read_existing(grant["grant_id"], opener=opener)
        if verify_claim(existing or {}) and existing.get("grant_hash") == grant["grant_hash"]:
            return {
                "terminal": "CLAIM_ALREADY_HELD",
                "grant_id": grant["grant_id"],
                "grant_hash": grant["grant_hash"],
                "existing_claim_hash": existing["claim_hash"],
                "existing_transport_lane": existing.get("transport_lane"),
                "execution_permitted": False,
            }
        return {
            "terminal": "CLAIM_CONFLICT_HASH",
            "grant_id": grant["grant_id"],
            "grant_hash": grant["grant_hash"],
            "execution_permitted": False,
        }
    except (urllib.error.URLError, TimeoutError, OSError):
        return {
            "terminal": "CLAIM_OUTCOME_UNDETERMINED",
            "grant_id": grant["grant_id"],
            "grant_hash": grant["grant_hash"],
            "execution_permitted": False,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Acquire an exactly-once execution claim across Activator transport lanes")
    parser.add_argument("--grant", required=True)
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--transport-lane", required=True)
    parser.add_argument("--workflow-run-id", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    import os
    grant = json.loads(Path(args.grant).read_text(encoding="utf-8"))
    result = acquire(
        grant,
        token=os.environ.get(args.token_env, ""),
        transport_lane=args.transport_lane,
        workflow_run_id=args.workflow_run_id,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")
    if result.get("terminal") not in {"CLAIM_ACQUIRED", "CLAIM_ALREADY_HELD"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
