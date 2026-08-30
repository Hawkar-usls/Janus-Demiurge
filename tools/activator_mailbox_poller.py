#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Iterable

from tools.activator_oidc_identity import REQUEST_SCHEMA as OIDC_REQUEST_SCHEMA, verify_request_envelope

HOME_REPOSITORY = "Hawkar-usls/Hawkar-usls"
TARGET_REPOSITORY = "Hawkar-usls/Janus-Demiurge"
HOME_BRANCH = "janus/transport-mailbox"
TARGET_BRANCH = "janus/activator-mailbox"
HOME_OUTBOX = ".janus/mailbox/outbox"
TARGET_INBOX = ".janus/mailbox/inbox"
MESSAGE_SCHEMA = "janus.activator.mailbox_message.v1.0"
ALLOWED_KINDS_V1 = {"DISPATCH_PACKET"}
BLOCKED_KINDS = {"EXECUTION_GRANT"}
PACKET_ID_RE = re.compile(r"^dsp-[0-9a-f]{64}$")
GRANT_ID_RE = re.compile(r"^xg-[0-9a-f]{64}$")


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "JANUS-Demiurge-Credentialless-Mailbox/1.1",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )


def public_json(url: str, *, opener: Callable[..., Any] = urllib.request.urlopen) -> Any:
    try:
        response = opener(_request(url), timeout=20.0)
        return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def home_branch_url() -> str:
    branch = urllib.parse.quote(HOME_BRANCH, safe="")
    return f"https://api.github.com/repos/{HOME_REPOSITORY}/branches/{branch}"


def home_tree_url(commit_sha: str) -> str:
    return f"https://api.github.com/repos/{HOME_REPOSITORY}/git/trees/{commit_sha}?recursive=1"


def _valid_object_id(kind: str, object_id: Any) -> bool:
    value = str(object_id or "")
    if kind == "DISPATCH_PACKET":
        return PACKET_ID_RE.fullmatch(value) is not None
    if kind == "EXECUTION_GRANT":
        return GRANT_ID_RE.fullmatch(value) is not None
    return False


def target_response_raw_url(object_kind: str, object_id: str, *, oidc: bool = False) -> str:
    if not _valid_object_id(object_kind, object_id):
        raise ValueError("UNSAFE_OR_INVALID_MAILBOX_OBJECT_ID")
    if object_kind != "DISPATCH_PACKET":
        raise ValueError("MAILBOX_EXECUTION_IDENTITY_GATE_REQUIRED")
    suffix = "oidc-ack" if oidc else "ack"
    return (
        f"https://raw.githubusercontent.com/{TARGET_REPOSITORY}/{TARGET_BRANCH}/"
        f"{TARGET_INBOX}/{object_id}.{suffix}.json"
    )


def response_exists(
    object_kind: str,
    object_id: str,
    *,
    oidc: bool = False,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> bool:
    try:
        response = opener(_request(target_response_raw_url(object_kind, object_id, oidc=oidc)), timeout=10.0)
        return int(getattr(response, "status", 200)) == 200
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise


def verify_message(envelope: Dict[str, Any]) -> bool:
    if not isinstance(envelope, dict):
        return False
    claimed = str(envelope.get("message_hash") or "")
    if len(claimed) != 64:
        return False
    body = dict(envelope)
    body.pop("message_hash", None)
    if canonical_hash(body) != claimed:
        return False
    if envelope.get("schema") != MESSAGE_SCHEMA:
        return False
    if envelope.get("source_repository") != HOME_REPOSITORY or envelope.get("target_repository") != TARGET_REPOSITORY:
        return False
    kind = str(envelope.get("object_kind") or "")
    if kind in BLOCKED_KINDS or kind not in ALLOWED_KINDS_V1:
        return False
    if not _valid_object_id(kind, envelope.get("object_id")):
        return False
    for field in (
        "command_authority_granted", "claim_authority_granted",
        "scientific_evidence_authority_granted", "external_effect_authorized",
        "physical_runtime_effect_authorized",
    ):
        if envelope.get(field) is not False:
            return False
    obj = envelope.get("object")
    return (
        isinstance(obj, dict)
        and envelope.get("object_id") == obj.get("packet_id")
        and envelope.get("object_hash") == obj.get("packet_hash")
    )


def _decode_blob(blob: Dict[str, Any]) -> Dict[str, Any] | None:
    if not isinstance(blob, dict):
        return None
    content = blob.get("content")
    encoding = blob.get("encoding")
    if not isinstance(content, str) or encoding != "base64":
        return None
    raw = base64.b64decode(content.encode("ascii"), validate=False)
    value = json.loads(raw.decode("utf-8"))
    return value if isinstance(value, dict) else None


def iter_home_envelopes(*, opener: Callable[..., Any] = urllib.request.urlopen) -> Iterable[Dict[str, Any]]:
    branch = public_json(home_branch_url(), opener=opener)
    if branch is None:
        return []
    if not isinstance(branch, dict):
        raise ValueError("HOME_MAILBOX_BRANCH_RESPONSE_NOT_OBJECT")
    commit = branch.get("commit")
    commit_sha = str(commit.get("sha") or "") if isinstance(commit, dict) else ""
    if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        raise ValueError("HOME_MAILBOX_BRANCH_SHA_INVALID")

    tree = public_json(home_tree_url(commit_sha), opener=opener)
    if not isinstance(tree, dict) or not isinstance(tree.get("tree"), list):
        raise ValueError("HOME_MAILBOX_TREE_MALFORMED")
    if tree.get("truncated") is True:
        raise RuntimeError("HOME_MAILBOX_TREE_TRUNCATED_UNKNOWN_RESOURCE_LIMIT")

    prefix = HOME_OUTBOX + "/"
    rows: list[Dict[str, Any]] = []
    for item in tree["tree"]:
        if not isinstance(item, dict) or item.get("type") != "blob":
            continue
        path = str(item.get("path") or "")
        if not path.startswith(prefix) or not path.endswith(".json"):
            continue
        blob_url = str(item.get("url") or "")
        if not blob_url.startswith(f"https://api.github.com/repos/{HOME_REPOSITORY}/git/blobs/"):
            continue
        envelope = _decode_blob(public_json(blob_url, opener=opener))
        if isinstance(envelope, dict):
            rows.append(envelope)
    return rows


def poll(
    out_dir: str | Path,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
    oidc_decoder=None,
) -> Dict[str, Any]:
    root = Path(out_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    accepted: list[Dict[str, Any]] = []
    rejected = 0
    rejected_oidc = 0
    blocked_execution_identity_required = 0
    skipped_existing = 0

    for envelope in iter_home_envelopes(opener=opener):
        kind = str(envelope.get("object_kind") or "")
        if kind in BLOCKED_KINDS:
            blocked_execution_identity_required += 1
            continue

        schema = envelope.get("schema")
        identity_verification = None
        oidc = schema == OIDC_REQUEST_SCHEMA
        if oidc:
            identity_verification = verify_request_envelope(envelope, decoder=oidc_decoder)
            if identity_verification.get("ok") is not True:
                rejected_oidc += 1
                continue
        elif not verify_message(envelope):
            rejected += 1
            continue

        object_id = str(envelope["object_id"])
        if response_exists("DISPATCH_PACKET", object_id, oidc=oidc, opener=opener):
            skipped_existing += 1
            continue

        suffix = "oidc-packet" if oidc else "packet"
        path = (root / f"{object_id}.{suffix}.envelope.json").resolve()
        if path.parent != root:
            rejected += 1
            continue
        path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        verification_path = None
        if identity_verification is not None:
            verification_path = (root / f"{object_id}.oidc-source-verification.json").resolve()
            if verification_path.parent != root:
                rejected_oidc += 1
                path.unlink(missing_ok=True)
                continue
            verification_path.write_text(
                json.dumps(identity_verification, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        accepted.append({
            "protocol": "OIDC_V1_1" if oidc else "LEGACY_V1_0",
            "object_kind": "DISPATCH_PACKET",
            "object_id": object_id,
            "path": str(path),
            "identity_proof": bool(oidc),
            "identity_verification_path": str(verification_path) if verification_path else None,
        })

    manifest = {
        "schema": "janus.demiurge.mailbox_poll_manifest.v1.1",
        "accepted": accepted,
        "rejected_invalid": rejected,
        "rejected_oidc_identity": rejected_oidc,
        "blocked_execution_identity_required": blocked_execution_identity_required,
        "skipped_existing_response": skipped_existing,
        "credentialless_execution_enabled": False,
        "execution_claim_allowed": False,
        "execution_claim_allowed_before_identity_verification": False,
        "oidc_packet_identity_enabled": True,
        "bidirectional_oidc_response_required_for_v1_1": True,
        "discovery": "GIT_TREES_RECURSIVE_NOT_CONTENTS_DIRECTORY_LISTING",
        "tree_truncation_semantics": "UNKNOWN_RESOURCE_LIMIT",
        "silence_interpretation": "NOOP_NOT_NEGATIVE_EVIDENCE",
        "cross_repository_write_performed": False,
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Poll JANUS HOME public mailbox with optional OIDC v1.1 identity verification")
    parser.add_argument("--out-dir", default="runtime/activator-mailbox/requests")
    args = parser.parse_args()
    manifest = poll(args.out_dir)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
