#!/usr/bin/env python3
"""JANUS Demiurge river confluence: read-only SHA-bound source and witness intake.

This does not execute external code, grant authority, infer model quality, or
solve P vs NP. Live GitHub metadata is an observation, not scientific proof.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

OWNER = "Hawkar-usls"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
MAX_DOC_BYTES = 131072
SCHEMA = "janus.demiurge.river_confluence.v1"
BRAIN = {
    "Demi_Head": ("docs/ARCHITECTURE.md", None, "BICAMERAL_GUARDIAN_COMPARATOR"),
    "AIFC": ("conformance/AIFC-ADMISSION-AUTHORITY-ORDER-v1.json",
             "AIFC/admission-authority-order/v1", "EVIDENCE_ADMISSION_VERIFIER"),
    "Janus": ("docs/JANUS_MCP_GATEWAY.md", None, "ORGANISM_MCP_GATEWAY"),
    "janus-io-public": ("docs/proof-of-observation-origin-record.json",
                         "JANUS/proof-of-observation-origin-record/v1",
                         "I0_OBSERVATION_PROVENANCE"),
    "janus-distributed-ai-swarm": ("docs/architecture.md", None,
                                   "DISTRIBUTED_FACE_TRANSPORT"),
}
RESEARCH = {
    "Janus-Fundamentum": (".janus/JANUS_CROSS_ORGAN_SOURCE_LINK.json",
                           "janus.organ.cross_organ_source_link.v1"),
    "TOPA": ("data/TOPA-MATHEMATICAL-RESEARCH-MODE-2026-08-24-v1.2.json", None),
    "janus-lapis": ("data/beetle/directions.json",
                    "janus.universal_beetle.directions.v1"),
}
SWARM_WORKFLOW = "validate-brain-five-face-bus.yml"


class Hold(ValueError):
    pass


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def issha(s: object) -> bool:
    return isinstance(s, str) and SHA40.fullmatch(s) is not None


class GitHubPublic:
    def _read(self, url: str, *, cap: int = 1024 * 1024) -> bytes:
        headers = {"User-Agent": "JANUS-Demiurge-River-Confluence/1",
                   "Accept": "application/vnd.github+json"}
        token = os.environ.get("GITHUB_TOKEN")
        if token and url.startswith("https://api.github.com/"):
            headers["Authorization"] = "Bearer " + token
        req = Request(url, headers=headers)
        try:
            with urlopen(req, timeout=25) as stream:
                raw = stream.read(cap + 1)
        except (HTTPError, URLError, TimeoutError) as exc:
            raise Hold("PUBLIC_GITHUB_SOURCE_UNAVAILABLE") from exc
        if not raw or len(raw) > cap:
            raise Hold("PUBLIC_GITHUB_PAYLOAD_SIZE")
        return raw

    def json(self, url: str) -> dict:
        try:
            value = json.loads(self._read(url))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise Hold("PUBLIC_GITHUB_INVALID_JSON") from exc
        if not isinstance(value, dict):
            raise Hold("PUBLIC_GITHUB_OBJECT_REQUIRED")
        return value

    def head(self, repo: str) -> str:
        result = self.json(f"https://api.github.com/repos/{OWNER}/{repo}/commits/main")
        commit = result.get("sha")
        if not issha(commit):
            raise Hold(f"INVALID_SHA:{repo}")
        return commit

    def doc(self, repo: str, commit: str, path: str) -> bytes:
        if not issha(commit):
            raise Hold("EXACT_COMMIT_REQUIRED")
        if ".." in path.split("/") or path.startswith("/") or not re.fullmatch(r"[A-Za-z0-9_./-]+", path):
            raise Hold("SOURCE_PATH_REJECTED")
        return self._read(f"https://raw.githubusercontent.com/{OWNER}/{repo}/{commit}/{path}",
                          cap=MAX_DOC_BYTES)


def source(github: GitHubPublic, repo: str, path: str, expected: str | None) -> tuple[dict, dict | None]:
    commit = github.head(repo)
    raw = github.doc(repo, commit, path)
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Hold("SOURCE_NOT_UTF8") from exc
    value = None
    if path.endswith(".json"):
        try:
            value = json.loads(decoded)
        except json.JSONDecodeError as exc:
            raise Hold(f"SOURCE_JSON_INVALID:{repo}") from exc
        if not isinstance(value, dict):
            raise Hold("SOURCE_JSON_OBJECT_REQUIRED")
        if expected and value.get("schema") != expected:
            raise Hold(f"SOURCE_SCHEMA_MISMATCH:{repo}")
    elif not decoded.strip():
        raise Hold("EMPTY_SOURCE_DOCUMENT")
    return {
        "repo": OWNER + "/" + repo,
        "source_commit": commit,
        "path": path,
        "sha256": sha256(raw),
        "size_bytes": len(raw),
        "interpretation": "EXACT_PUBLIC_SOURCE_BYTES_NOT_SCIENTIFIC_TRUTH",
    }, value


def check_brain_manifest(github: GitHubPublic, swarm_commit: str) -> None:
    raw = github.doc("janus-distributed-ai-swarm", swarm_commit,
                     "configs/brain_five_faces_v1.json")
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise Hold("BRAIN_MANIFEST_JSON_INVALID") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != "janus.brain.five_face_cohort.v1" \
            or manifest.get("model_calls_enabled") is not False \
            or manifest.get("default_write_permission") is not False \
            or manifest.get("paid_provider_calls_enabled") is not False:
        raise Hold("BRAIN_MANIFEST_POLICY_REJECTED")
    faces = manifest.get("faces")
    if not isinstance(faces, list) or len(faces) != 5:
        raise Hold("BRAIN_FACE_COUNT_REJECTED")
    found = set()
    for face in faces:
        if not isinstance(face, dict) or not isinstance(face.get("repository"), str):
            raise Hold("BRAIN_FACE_SHAPE_REJECTED")
        prefix = OWNER + "/"
        if not face["repository"].startswith(prefix):
            raise Hold("BRAIN_FACE_OWNER_REJECTED")
        name = face["repository"][len(prefix):]
        if name not in BRAIN or name in found or face.get("ref") != "main":
            raise Hold("BRAIN_FACE_IDENTITY_REJECTED")
        path, schema, role = BRAIN[name]
        if face.get("anchor_path") != path or face.get("expected_schema") != schema \
                or face.get("role") != role:
            raise Hold("BRAIN_FACE_CONTRACT_DRIFT")
        found.add(name)
    if found != set(BRAIN):
        raise Hold("BRAIN_MISSING_FACES")


def witness_metadata(github: GitHubPublic, swarm_sha: str) -> dict:
    url = (f"https://api.github.com/repos/{OWNER}/janus-distributed-ai-swarm"
           f"/actions/workflows/{SWARM_WORKFLOW}/runs?branch=main&per_page=12")
    runs = github.json(url).get("workflow_runs")
    if not isinstance(runs, list):
        raise Hold("BRAIN_WORKFLOW_RUN_LIST_UNAVAILABLE")
    candidates = [r for r in runs if isinstance(r, dict) and
                  r.get("status") == "completed" and r.get("conclusion") == "success"
                  and r.get("head_branch") == "main" and r.get("head_sha") == swarm_sha
                  and r.get("event") in ("push", "schedule", "workflow_dispatch")]
    if not candidates:
        return {"status": "HOLD_NO_SUCCESSFUL_RUN_AT_CURRENT_SWARM_HEAD",
                "artifact_payloads_replayed": False}
    chosen = candidates[0]
    run_id = chosen.get("id")
    if type(run_id) is not int or run_id < 1:
        raise Hold("BRAIN_WORKFLOW_RUN_ID_INVALID")
    base = f"https://api.github.com/repos/{OWNER}/janus-distributed-ai-swarm/actions/runs/{run_id}"
    jobs = github.json(base + "/jobs?per_page=100").get("jobs")
    arts = github.json(base + "/artifacts?per_page=100").get("artifacts")
    if not isinstance(jobs, list) or not isinstance(arts, list):
        raise Hold("BRAIN_RUN_EVIDENCE_UNAVAILABLE")
    good = [j.get("name", "") for j in jobs if isinstance(j, dict) and j.get("conclusion") == "success"]
    counts = {
        "observe": sum(isinstance(n, str) and n.startswith("brain-observe (") for n in good),
        "receive": sum(isinstance(n, str) and n.startswith("brain-receive (") for n in good),
        "route": good.count("brain-route"),
        "witness": good.count("brain-independent-witness"),
        "plan": good.count("plan"),
    }
    artifacts = {a.get("name") for a in arts if isinstance(a, dict) and a.get("expired") is False}
    expected = {"brain-five-mailboxes", "janus-five-brain-delivery-witness"}
    if counts != {"observe": 5, "receive": 5, "route": 1, "witness": 1, "plan": 1} \
            or not expected.issubset(artifacts) \
            or sum(isinstance(n, str) and n.startswith("brain-msg-") for n in artifacts) != 5 \
            or sum(isinstance(n, str) and n.startswith("brain-ack-") for n in artifacts) != 5:
        return {"status": "HOLD_BRAIN_WITNESS_METADATA_INCOMPLETE",
                "workflow_run_id": run_id, "job_counts": counts,
                "artifact_payloads_replayed": False}
    return {
        "status": "RUN_AND_ARTIFACT_METADATA_VERIFIED",
        "workflow_run_id": run_id,
        "workflow_run_url": f"https://github.com/{OWNER}/janus-distributed-ai-swarm/actions/runs/{run_id}",
        "swarm_run_source_commit": swarm_sha,
        "job_counts": counts,
        "artifact_count": len(artifacts),
        "artifact_payloads_replayed": False,
        "cross_run_message_sha_alignment_proven": False,
    }


def confluence(github: GitHubPublic, policy: dict) -> dict:
    if policy.get("schema") != "janus.research_organ_fabric.v1":
        raise Hold("DEMIURGE_RESEARCH_FABRIC_SCHEMA")
    limits = policy.get("promotion_barrier", {})
    if not isinstance(limits, dict) or limits.get("p_vs_np_auto_promotion") is not False \
            or limits.get("fundamentum_mutation") is not False \
            or limits.get("autonomous_merge") is not False:
        raise Hold("DEMIURGE_RESEARCH_PROMOTION_BARRIER")
    brain_sources = []
    for name, (path, expected, _role) in BRAIN.items():
        item, _ = source(github, name, path, expected)
        brain_sources.append(item)
    swarm = next(s for s in brain_sources if s["repo"].endswith("/janus-distributed-ai-swarm"))
    check_brain_manifest(github, swarm["source_commit"])
    research_sources, research_details = [], {}
    for name, (path, expected) in RESEARCH.items():
        item, detail = source(github, name, path, expected)
        research_sources.append(item)
        research_details[name] = detail
    f = research_details["Janus-Fundamentum"]
    t = research_details["TOPA"]
    b = research_details["janus-lapis"]
    if f.get("blocked_claim") != "P_VS_NP_OPEN" \
            or t.get("current_split", {}).get("p_vs_np") != "OPEN" \
            or b.get("schema") != "janus.universal_beetle.directions.v1":
        raise Hold("SCIENCE_FRONTIER_CLAIM_BOUNDARY_INVALID")
    witness = witness_metadata(github, swarm["source_commit"])
    return {
        "schema": SCHEMA,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "READ_ONLY_INTAKE_OK" if witness["status"] == "RUN_AND_ARTIFACT_METADATA_VERIFIED"
                  else "HOLD_UNVERIFIED_UPSTREAM_WITNESS",
        "brain_flow": {
            "destination": OWNER + "/Janus-Demiurge",
            "source_count": 5,
            "sources": brain_sources,
            "upstream_witness": witness,
            "semantic_interpretation": "DOCUMENT_AND_WORKFLOW_METADATA_NOT_NEURAL_MODEL_OUTPUT",
        },
        "science_flow": {
            "source_count": 3,
            "sources": research_sources,
            "fundamentum": "FORMAL_RESEARCH_SOURCE_ONLY",
            "topa": "ADVERSARIAL_FALSIFICATION_REQUIRED",
            "beetle": "DISCOVERY_CANDIDATES_NOT_PROOF",
            "p_vs_np": "OPEN",
            "universal_polynomial_algorithm_proved": False,
            "scientific_claim_promotion": False,
            "research_cycle_owner": "EXISTING_JANUS_PNP_AUTORESEARCH_NO_DUPLICATE_TRIGGER",
        },
        "authority": {
            "remote_repository_write": False,
            "new_model_calls": False,
            "paid_provider_calls": False,
            "external_workflow_dispatch": False,
            "automatic_merge": False,
            "p_vs_np_promotion": False,
            "beetle_discovery_is_proof": False,
        },
        "claim_ceiling": "Source hashes, existing job status and artifact names are metadata. "
                         "Artifact payloads and independent scientific claims are NOT verified.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="janus_model/policy/JANUS_RESEARCH_ORGAN_FABRIC.json")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        policy = json.loads(Path(args.policy).read_text(encoding="utf-8"))
        report = confluence(GitHubPublic(), policy)
    except (Hold, ValueError, OSError, TypeError, KeyError) as exc:
        report = {"schema": SCHEMA, "status": "HOLD_INTAKE_ERROR",
                  "error_type": type(exc).__name__, "error": str(exc),
                  "p_vs_np": "OPEN", "authority_delta": 0}
        exit_code = 2
    else:
        exit_code = 0
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    print(json.dumps({"status": report["status"], "out": str(path),
                      "p_vs_np": "OPEN"}, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
