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

HOME_REPOSITORY = "Hawkar-usls/Hawkar-usls"
TARGET_REPOSITORY = "Hawkar-usls/Janus-Demiurge"
HOME_BRANCH = "janus/transport-mailbox"
TARGET_BRANCH = "janus/activator-mailbox"
HOME_OUTBOX = ".janus/mailbox/outbox"
TARGET_INBOX = ".janus/mailbox/inbox"
MESSAGE_SCHEMA = "janus.activator.mailbox_message.v1.0"
ALLOWED_KINDS = {"DISPATCH_PACKET", "EXECUTION_GRANT"}
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
            "User-Agent": "JANUS-Demiurge-Credentialless-Mailbox/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )


def public_json(url: str, *, opener: Callable[..., Any] = urllib.request.urlopen) -> Any:
    try:
        response = opener(_request(url), timeout=20.0)
        raw = response.read()
        return json.loads(raw.decode("utf-8"))
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


def target_response_raw_url(object_kind: str, object_id: str) -> str:
    if not _valid_object_id(object_kind, object_id):
        raise ValueError("UNSAFE_OR_INVALID_MAILBOX_OBJECT_ID")
    suffix = "ack" if object_kind == "DISPATCH_PACKET" else "execution"
    return (
        f"https://raw.githubusercontent.com/{TARGET_REPOSITORY}/{TARGET_BRANCH}/"
        f"{TARGET_INBOX}/{object_id}.{suffix}.json"
    )


def response_exists(object_kind: str, object_id: str, *, opener: Callable[..., Any] = urllib.request.urlopen) -> bool:
    try:
        response = opener(_request(target_response_raw_url(object_kind, object_id)), timeout=10.0)
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
    if envelope.get("source_repository") != HOME_REPOSITORY:
        return False
    if envelope.get("target_repository") != TARGET_REPOSITORY:
        return False
    kind = str(envelope.get("object_kind") or "")
    if kind not in ALLOWED_KINDS:
        return False
    if not _valid_object_id(kind, envelope.get("object_id")):
        return False
    if envelope.get("command_authority_granted") is not False:
        return False
    if envelope.get("claim_authority_granted") is not False:
        return False
    if envelope.get("scientific_evidence_authority_granted") is not False:
        return False
    if envelope.get("external_effect_authorized") is not False:
        return False
    if envelope.get("physical_runtime_effect_authorized") is not False:
        return False
    obj = envelope.get("object")
    if not isinstance(obj, dict):
        return False
    if kind == "DISPATCH_PACKET":
        return (
            envelope.get("object_id") == obj.get("packet_id")
            and envelope.get("object_hash") == obj.get("packet_hash")
        )
    return (
        envelope.get("object_id") == obj.get("grant_id")
        and envelope.get("object_hash") == obj.get("grant_hash")
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
    # Do not use the Contents directory listing here: GitHub caps it at 1,000
    # entries, which is incompatible with an append-only long-lived mailbox.
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
        # Tree truncation is UNKNOWN_RESOURCE_LIMIT, never evidence that no mail
        # exists. Refuse a partial traversal instead of silently dropping rows.
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


def poll(out_dir: str | Path, *, opener: Callable[..., Any] = urllib.request.urlopen) -> Dict[str, Any]:
    root = Path(out_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    accepted: list[Dict[str, str]] = []
    rejected = 0
    skipped_existing = 0

    for envelope in iter_home_envelopes(opener=opener):
        if not verify_message(envelope):
            rejected += 1
            continue
        kind = str(envelope["object_kind"])
        object_id = str(envelope["object_id"])
        if response_exists(kind, object_id, opener=opener):
            skipped_existing += 1
            continue
        suffix = "packet" if kind == "DISPATCH_PACKET" else "grant"
        path = (root / f"{object_id}.{suffix}.envelope.json").resolve()
        if path.parent != root:
            # Defense in depth even though deterministic ID grammar already
            # excludes separators, absolute paths and traversal components.
            rejected += 1
            continue
        path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        accepted.append({"object_kind": kind, "object_id": object_id, "path": str(path)})

    manifest = {
        "schema": "janus.demiurge.mailbox_poll_manifest.v1.0",
        "accepted": accepted,
        "rejected_invalid": rejected,
        "skipped_existing_response": skipped_existing,
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
    parser = argparse.ArgumentParser(description="Poll JANUS HOME public mailbox without a cross-repository credential")
    parser.add_argument("--out-dir", default="runtime/activator-mailbox/requests")
    args = parser.parse_args()
    manifest = poll(args.out_dir)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
