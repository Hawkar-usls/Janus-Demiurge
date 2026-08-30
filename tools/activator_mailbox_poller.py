#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
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


def home_listing_url() -> str:
    path = urllib.parse.quote(HOME_OUTBOX, safe="/")
    return f"https://api.github.com/repos/{HOME_REPOSITORY}/contents/{path}?ref={urllib.parse.quote(HOME_BRANCH, safe='')}"


def target_response_raw_url(object_kind: str, object_id: str) -> str:
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
    kind = envelope.get("object_kind")
    if kind not in ALLOWED_KINDS:
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


def iter_home_envelopes(*, opener: Callable[..., Any] = urllib.request.urlopen) -> Iterable[Dict[str, Any]]:
    listing = public_json(home_listing_url(), opener=opener)
    if listing is None:
        return []
    if not isinstance(listing, list):
        raise ValueError("HOME_MAILBOX_LISTING_NOT_ARRAY")
    rows: list[Dict[str, Any]] = []
    for item in listing:
        if not isinstance(item, dict) or item.get("type") != "file":
            continue
        name = str(item.get("name") or "")
        if not name.endswith(".json"):
            continue
        download_url = str(item.get("download_url") or "")
        if not download_url:
            continue
        envelope = public_json(download_url, opener=opener)
        if isinstance(envelope, dict):
            rows.append(envelope)
    return rows


def poll(out_dir: str | Path, *, opener: Callable[..., Any] = urllib.request.urlopen) -> Dict[str, Any]:
    root = Path(out_dir)
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
        path = root / f"{object_id}.{suffix}.envelope.json"
        path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        accepted.append({"object_kind": kind, "object_id": object_id, "path": str(path)})

    manifest = {
        "schema": "janus.demiurge.mailbox_poll_manifest.v1.0",
        "accepted": accepted,
        "rejected_invalid": rejected,
        "skipped_existing_response": skipped_existing,
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
