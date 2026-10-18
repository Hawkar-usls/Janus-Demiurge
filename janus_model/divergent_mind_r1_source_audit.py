"""Offline whole-file-to-excerpt provenance audit for JANUS R1.

Supply six *unmodified raw GitHub file bytes*, placed as <organ_key>.json
in a caller-controlled directory. The Git blob SHA-1 is checked against
the pinned source metadata before matching the selected native fields.

This proves byte identity with a Git blob, not that a commit/tree contains
that path; commit/path membership must be checked against GitHub separately.
No network or source writes occur in this process.
"""
from __future__ import annotations

import argparse
from hashlib import sha1
import json
from pathlib import Path

from janus_model.divergent_mind_r1 import FIELD_NAMES, validate


def git_blob_sha1(raw: bytes) -> str:
    return sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def _picked_fields(full: dict, names: set[str]) -> dict:
    return {name: full[name] for name in names}


def assert_source_excerpt_matches(key: str, full: dict, excerpt: dict) -> None:
    """Compare each selected real native field, not a synthetic score."""
    if not isinstance(full, dict):
        raise ValueError("full native JSON must be an object")
    if key.startswith("hrain_"):
        expected = _picked_fields(full, set(excerpt))
    elif key == "inaihr_state":
        expected = _picked_fields(full, {"schema", "status", "generated_at", "candidate_count"})
        expected["registry"] = _picked_fields(full["registry"], set(excerpt["registry"]))
        expected["attention"] = _picked_fields(full["attention"], set(excerpt["attention"]))
        selected = full["candidates"][-len(excerpt["recent_candidates"]):]
        expected["recent_candidates"] = []
        for candidate in selected:
            expected["recent_candidates"].append({
                "id": candidate["id"],
                "status": candidate["status"],
                "attention_score": candidate["attention_score"],
                "focus_key": candidate["focus_key"],
                "source_ids": candidate["meaning"]["lineage"]["source_ids"],
                "prior_candidate_id": candidate["meaning"]["lineage"]["prior_candidate_id"],
                "independent_replication_established":
                    candidate["meaning"]["evidence"]["independent_replication_established"],
                "authority": _picked_fields(candidate["authority"], set(excerpt["recent_candidates"][0]["authority"])),
            })
    elif key == "eye_next_tests":
        expected = _picked_fields(full, {"schema", "warning"})
        for group in ("available_ranked", "unavailable_counterfactual_value_ranked"):
            expected[group] = [_picked_fields(row, {"test_id", "available", "gain_per_cost"})
                               for row in full[group]]
    elif key == "eye_independence":
        expected = {
            "schema": full["schema"],
            "unknown_independence_conflicts": full["unknown_independence_conflicts"],
            "pair_count": len(full["pairs"]),
        }
        by_pair = {(x["a"], x["b"]): x for x in full["pairs"]}
        expected["pairs_sample"] = [
            _picked_fields(by_pair[(x["a"], x["b"])], set(x))
            for x in excerpt["pairs_sample"]
        ]
    else:
        raise ValueError("unrecognized source key")
    if expected != excerpt:
        raise ValueError(f"native source content differs from captured excerpt: {key}")


def audit(pack: dict, directory: Path) -> dict:
    validate(pack)
    outputs = []
    for key in FIELD_NAMES:
        origin = pack["sources"][key]["origin"]
        source_file = directory / (key + ".json")
        if source_file.is_symlink() or not source_file.is_file():
            raise ValueError("source audit requires ordinary regular files only")
        raw = source_file.read_bytes()
        if len(raw) > 2_000_000:
            raise ValueError("source too large for bounded verifier")
        if git_blob_sha1(raw) != origin["blob_sha"]:
            raise ValueError(f"Git source blob mismatch: {key}")
        try:
            full = json.loads(raw)
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError(f"invalid original JSON for {key}") from exc
        assert_source_excerpt_matches(key, full, pack["sources"][key]["excerpt"])
        outputs.append({"organ_file": key, "blob_sha": origin["blob_sha"],
                        "status": "BYTE_IDENTITY_AND_EXCERPT_PASS"})
    return {
        "schema": "janus.divergent_mind.r1.source_audit.v1",
        "status": "ALL_EXCERPTS_MATCH_WHOLE_GIT_BLOBS",
        "path_at_commit_membership_checked": False,
        "source_writeback": False,
        "entries": outputs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline R1 full Git blob excerpt verifier")
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--source-dir", required=True, type=Path)
    args = parser.parse_args()
    result = audit(json.loads(args.pack.read_text(encoding="utf-8")), args.source_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
