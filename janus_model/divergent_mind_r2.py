"""JANUS R2: read-only GitHub source acquisition, double-HEAD freeze and questions.

No import-time network, writes, command execution, or runtime organ calls.
The optional CLI only GETs public GitHub APIs and prints an advisory receipt.
Unknown access, source drift, byte mismatch or schema mismatch means HOLD.
"""
from __future__ import annotations

import argparse
import base64
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from janus_model.divergent_mind import _canonical
from janus_model.divergent_mind_r1 import (
    CAPTURE_KIND, FIELD_NAMES, KEYS, SCHEMA, run, validate,
)
from janus_model.divergent_mind_r1_source_audit import git_blob_sha1


SCHEMA_R2 = "janus.divergent_mind.r2.capture_receipt.v1"
ALLOWED_REPOS = tuple(sorted({record[0] for record in FIELD_NAMES.values()}))
HEX40 = re.compile(r"[a-f0-9]{40}\Z")
MAX_HTTP_BYTES = 2_500_000
MAX_BLOB_BYTES = 2_000_000


class ReadFailure(ValueError):
    """Fail-closed uncertainty; never interpreted as a negative source fact."""

    def __init__(self, kind: str):
        super().__init__(kind)
        self.kind = kind


class SourceReader(Protocol):
    def get_head(self, repository: str) -> str: ...
    def get_blob(self, repository: str, commit: str, path: str) -> tuple[bytes, str]: ...


class PublicGitHubReader:
    """Opt-in public-only GET. Does not read credentials or follow user URLs."""

    def _json(self, url: str) -> dict:
        if not url.startswith("https://api.github.com/repos/Hawkar-usls/"):
            raise ReadFailure("UNKNOWN_UNAPPROVED_SOURCE_URL")
        request = Request(url, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "JANUS-Divergent-Mind-R2-readonly",
            "X-GitHub-Api-Version": "2022-11-28",
        }, method="GET")
        try:
            with urlopen(request, timeout=12) as response:
                if response.geturl().split("/")[2] != "api.github.com":
                    raise ReadFailure("UNKNOWN_UNEXPECTED_REDIRECT")
                raw = response.read(MAX_HTTP_BYTES + 1)
        except HTTPError as exc:
            raise ReadFailure(
                "UNKNOWN_RATE_LIMIT_OR_DENIED" if exc.code in {401, 403, 429}
                else "UNKNOWN_HTTP_SOURCE_ERROR"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ReadFailure("UNKNOWN_NETWORK") from exc
        if len(raw) > MAX_HTTP_BYTES:
            raise ReadFailure("UNKNOWN_OVERSIZED_RESPONSE")
        try:
            data = json.loads(raw)
        except (UnicodeDecodeError, ValueError) as exc:
            raise ReadFailure("UNKNOWN_INVALID_GITHUB_JSON") from exc
        if not isinstance(data, dict):
            raise ReadFailure("UNKNOWN_INVALID_GITHUB_SHAPE")
        return data

    def get_head(self, repository: str) -> str:
        if repository not in ALLOWED_REPOS:
            raise ReadFailure("UNKNOWN_UNAPPROVED_REPOSITORY")
        slug = repository.split("/")[1]
        obj = self._json(f"https://api.github.com/repos/Hawkar-usls/{slug}/branches/main")
        commit = obj.get("commit")
        value = commit.get("sha") if isinstance(commit, dict) else None
        if not isinstance(value, str) or not HEX40.fullmatch(value):
            raise ReadFailure("UNKNOWN_HEAD_SHA")
        return value

    def get_blob(self, repository: str, commit: str, path: str) -> tuple[bytes, str]:
        if repository not in ALLOWED_REPOS or not isinstance(commit, str) or not HEX40.fullmatch(commit):
            raise ReadFailure("UNKNOWN_UNAPPROVED_SOURCE")
        valid = {(x[0], x[1]) for x in FIELD_NAMES.values()}
        if (repository, path) not in valid:
            raise ReadFailure("UNKNOWN_UNAPPROVED_SOURCE_PATH")
        slug = repository.split("/")[1]
        url = (f"https://api.github.com/repos/Hawkar-usls/{slug}/contents/"
               f"{quote(path, safe='/')}?ref={commit}")
        obj = self._json(url)
        if obj.get("encoding") != "base64" or not isinstance(obj.get("content"), str):
            raise ReadFailure("UNKNOWN_NON_BASE64_SOURCE")
        git_sha = obj.get("sha")
        if not isinstance(git_sha, str) or not HEX40.fullmatch(git_sha):
            raise ReadFailure("UNKNOWN_BLOB_SHA")
        try:
            raw = base64.b64decode("".join(obj["content"].split()), validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise ReadFailure("UNKNOWN_BAD_BLOB_ENCODING") from exc
        if len(raw) > MAX_BLOB_BYTES or git_blob_sha1(raw) != git_sha:
            raise ReadFailure("HOLD_BLOB_BYTES_MISMATCH_OR_OVERSIZE")
        return raw, git_sha


def _native_excerpt(key: str, full: dict) -> dict:
    """Extract precisely the declared native fields, without labels/instructions."""
    if not isinstance(full, dict):
        raise ReadFailure("HOLD_NATIVE_SCHEMA_NOT_OBJECT")
    try:
        if key.startswith("hrain_"):
            return {name: full[name] for name in KEYS[key]}
        if key == "inaihr_state":
            result = {name: full[name] for name in
                      ("schema", "status", "generated_at", "candidate_count")}
            result["registry"] = {name: full["registry"][name] for name in
                                  ("repository", "source_commit")}
            result["attention"] = {name: full["attention"][name] for name in
                                   ("focus_key", "focus_age",
                                    "attention_weight_is_evidence_weight",
                                    "no_fixed_hypothesis_center")}
            recent = full["candidates"][-2:]
            result["recent_candidates"] = []
            for c in recent:
                result["recent_candidates"].append({
                    "id": c["id"],
                    "status": c["status"],
                    "attention_score": c["attention_score"],
                    "focus_key": c["focus_key"],
                    "source_ids": c["meaning"]["lineage"]["source_ids"],
                    "prior_candidate_id": c["meaning"]["lineage"]["prior_candidate_id"],
                    "independent_replication_established":
                        c["meaning"]["evidence"]["independent_replication_established"],
                    "authority": {k: c["authority"][k] for k in
                                  ("automatic_promotion", "causal", "mutation", "proof", "truth")},
                })
            return result
        if key == "eye_next_tests":
            return {
                "schema": full["schema"],
                "warning": full["warning"],
                **{group: [{field: entry[field] for field in
                            ("test_id", "available", "gain_per_cost")}
                           for entry in full[group]]
                   for group in ("available_ranked", "unavailable_counterfactual_value_ranked")}
            }
        if key == "eye_independence":
            return {
                "schema": full["schema"],
                "unknown_independence_conflicts": full["unknown_independence_conflicts"],
                "pair_count": len(full["pairs"]),
                "pairs_sample": [{name: pair[name] for name in
                                  ("a", "b", "independent_under_model",
                                   "shared_failure_domains")}
                                 for pair in full["pairs"][:3]],
            }
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise ReadFailure("HOLD_NATIVE_SCHEMA_CHANGED") from exc
    raise ReadFailure("HOLD_UNKNOWN_NATIVE_ORGAN_FILE")


def _failure(status: str, *, detail: dict | None = None) -> dict:
    return {
        "schema": SCHEMA_R2,
        "status": status,
        "detail": detail or {},
        "packet": None,
        "source_writeback": False,
        "authority_delta": 0,
        "scientific_claim_promotion": False,
    }


def capture(reader: SourceReader, *, policy: str = "require_frozen",
            reference: dict | None = None) -> dict:
    """Read full native blobs at one double-checked HEAD snapshot.

    require_frozen: exact R1 commit and blob pins must still be current;
    read_fresh: pin a newly observed consistent snapshot in memory only.
    """
    if policy not in {"require_frozen", "read_fresh"}:
        raise ValueError("explicit R2 capture policy required")
    if policy == "require_frozen":
        if reference is None:
            raise ValueError("frozen capture requires an audited reference")
        validate(reference)
    repos = ALLOWED_REPOS
    try:
        first = {repo: reader.get_head(repo) for repo in repos}
        if any(not isinstance(sha, str) or not HEX40.fullmatch(sha) for sha in first.values()):
            raise ReadFailure("UNKNOWN_BAD_HEAD")
        if policy == "require_frozen":
            pinned = {meta["origin"]["repository"]: meta["origin"]["commit"]
                      for meta in reference["sources"].values()}
            if any(first[repo] != pinned[repo] for repo in repos):
                return _failure("HOLD_SOURCE_HEAD_DRIFT", detail={
                    "stage": "BEFORE_ACQUISITION",
                    "pinned": pinned,
                    "observed": first,
                    "required_action": "REACQUIRE_AND_REVALIDATE_ALL_SOURCES",
                })
        sources: dict[str, dict] = {}
        for key, (repo, path, _) in FIELD_NAMES.items():
            raw, blob_sha = reader.get_blob(repo, first[repo], path)
            if not isinstance(raw, bytes) or len(raw) > MAX_BLOB_BYTES or git_blob_sha1(raw) != blob_sha:
                raise ReadFailure("HOLD_BLOB_BYTES_MISMATCH_OR_OVERSIZE")
            if policy == "require_frozen" and blob_sha != reference["sources"][key]["origin"]["blob_sha"]:
                raise ReadFailure("HOLD_FROZEN_BLOB_CHANGED")
            try:
                full = json.loads(raw)
            except (ValueError, UnicodeDecodeError) as exc:
                raise ReadFailure("HOLD_INVALID_NATIVE_JSON") from exc
            entry = _native_excerpt(key, full)
            sources[key] = {
                "origin": {
                    "repository": repo, "commit": first[repo],
                    "path": path, "blob_sha": blob_sha,
                },
                "excerpt": entry,
            }
        last = {repo: reader.get_head(repo) for repo in repos}
        if last != first:
            return _failure("HOLD_SOURCE_HEAD_DRIFT", detail={
                "stage": "DURING_ACQUISITION", "before": first, "after": last,
                "required_action": "REACQUIRE_CONSISTENT_HEAD_SNAPSHOT",
            })
        pack = {
            "schema": SCHEMA,
            "pack_id": "JANUS_R2_CAPTURE_" +
                       sha256(_canonical(first)).hexdigest()[:16].upper(),
            "capture_kind": CAPTURE_KIND,
            "sources": sources,
        }
        try:
            validate(pack)
        except (ValueError, KeyError) as exc:
            raise ReadFailure("HOLD_UNSUPPORTED_NATIVE_STATE_OR_AUTHORITY") from exc
        baseline = run(pack, "native_baseline")
        divergent = run(pack, "divergent_r1")
        return {
            "schema": SCHEMA_R2,
            "status": "READ_ONLY_QUESTIONS_READY__NOT_RUNTIME_INTEGRATION",
            "acquisition_policy": policy,
            "heads_double_checked": first,
            "whole_blobs_verified": len(sources),
            "origin_path_at_commit_checked_via_github_contents_api": True,
            "same_source_same_budget": (len(baseline["questions"]) == len(divergent["questions"])),
            "source_pack_sha256": sha256(_canonical(pack)).hexdigest(),
            "packet": {
                "schema": "janus.divergent_mind.r2.advisory.v1",
                "questions_by_arm": {
                    "native_baseline": baseline["questions"],
                    "divergent_r1": divergent["questions"],
                },
                "epistemic_status": "QUESTIONS_ONLY__INDEPENDENT_VERIFY_PENDING",
                "runtime_organ_packets_sent": False,
                "direct_eye_to_inaihr_bypass": False,
                "effect_authority": False,
                "scientific_claim_promotion": False,
                "authority_delta": 0,
            },
            "source_writeback": False,
            "authority_delta": 0,
            "scientific_claim_promotion": False,
        }
    except ReadFailure as exc:
        return _failure(exc.kind)
    except (KeyError, TypeError, ValueError) as exc:
        return _failure("HOLD_INVALID_SOURCE_READER_RESPONSE", detail={"category": type(exc).__name__})


def main() -> int:
    parser = argparse.ArgumentParser(description="Opt-in public GitHub read-only organ acquisition")
    parser.add_argument("--policy", choices=("require_frozen", "read_fresh"),
                        default="require_frozen")
    parser.add_argument("--reference", type=Path,
                        default=Path(__file__).resolve().parent /
                        "eval" / "DIVERGENT_MIND_ORGAN_SNAPSHOT-R1.json")
    args = parser.parse_args()
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    result = capture(PublicGitHubReader(), policy=args.policy, reference=reference)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"].startswith("READ_ONLY_QUESTIONS_READY") else 2


if __name__ == "__main__":
    raise SystemExit(main())
