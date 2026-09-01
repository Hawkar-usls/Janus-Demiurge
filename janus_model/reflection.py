from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ALLOWED_ORGAN_CONTEXT_STATUSES = {
    "READ_ONLY_ORGAN_CONTEXT",
    "READ_ONLY_MODULAR_ORGAN_CONTEXT",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_bytes(obj: dict) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _validate_organ_context(organ_context: dict) -> None:
    status = organ_context.get("status")
    if status not in ALLOWED_ORGAN_CONTEXT_STATUSES:
        raise RuntimeError("REFLECTION_ORGAN_CONTEXT_NOT_READ_ONLY")
    firewalls = organ_context.get("firewalls") or {}
    if firewalls.get("read_only") is not True:
        raise RuntimeError("REFLECTION_ORGAN_CONTEXT_READ_ONLY_FIREWALL_FAIL")
    if firewalls.get("terminal_authority") != "VERIFY":
        raise RuntimeError("REFLECTION_ORGAN_CONTEXT_TERMINAL_AUTHORITY_FAIL")
    if status == "READ_ONLY_MODULAR_ORGAN_CONTEXT":
        module_count = organ_context.get("module_count")
        if not isinstance(module_count, int) or module_count < 2:
            raise RuntimeError("REFLECTION_MODULAR_MODULE_COUNT_INVALID")
        if firewalls.get("module_observation_grants_mutation") is not False:
            raise RuntimeError("REFLECTION_MODULE_OBSERVATION_AUTHORITY_FAIL")
        if firewalls.get("raw_self_reflection_is_training_source") is not False:
            raise RuntimeError("REFLECTION_SELF_TRAINING_FIREWALL_FAIL")
        self_memory = organ_context.get("self_memory") or {}
        if self_memory.get("status") != "BOUND_READ_ONLY_SELF_MEMORY":
            raise RuntimeError("REFLECTION_SELF_MEMORY_NOT_BOUND")
        if self_memory.get("raw_reflections_are_training_source") is not False:
            raise RuntimeError("REFLECTION_SELF_MEMORY_SOURCE_FIREWALL_FAIL")
        if not self_memory.get("digest_sha256"):
            raise RuntimeError("REFLECTION_SELF_MEMORY_DIGEST_MISSING")


def build_reflection(
    checkpoint: Path,
    state_path: Path,
    organ_context_path: Path,
    inference_path: Path,
    prompt: str,
    run_id: str,
) -> dict:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    organ_context = json.loads(organ_context_path.read_text(encoding="utf-8"))
    inference_text = inference_path.read_text(encoding="utf-8", errors="replace")
    checkpoint_sha = sha256_file(checkpoint)
    inference_sha = sha256_file(inference_path)
    if checkpoint_sha != state.get("checkpoint_sha256"):
        raise RuntimeError("REFLECTION_CHECKPOINT_STATE_MISMATCH")
    _validate_organ_context(organ_context)

    status = organ_context.get("status")
    modular = status == "READ_ONLY_MODULAR_ORGAN_CONTEXT"
    self_memory = organ_context.get("self_memory") or {}
    identity = {
        "checkpoint_sha256": checkpoint_sha,
        "source_digest": state.get("last_source_digest"),
        "organ_context_sha256": organ_context.get("context_sha256"),
        "self_memory_digest": self_memory.get("digest_sha256") if modular else None,
        "module_registry_sha256": organ_context.get("module_registry_sha256") if modular else None,
        "inference_sha256": inference_sha,
        "prompt": prompt,
        "run_id": str(run_id),
    }
    reflection_id = hashlib.sha256(canonical_bytes(identity)).hexdigest()[:24]

    provenance = {
        "source_repository": "Hawkar-usls/Janus-Demiurge",
        "workflow_run_id": str(run_id),
        "checkpoint_sha256": checkpoint_sha,
        "meta_registry_source_commit": state.get("last_source_commit"),
        "meta_registry_source_digest": state.get("last_source_digest"),
        "organ_context_sha256": organ_context.get("context_sha256"),
        "hrain_commit": organ_context["organs"]["HRAiN"]["target_commit"],
        "inaihr_commit": organ_context["organs"]["iNaiHR"]["target_commit"],
        "inference_sha256": inference_sha,
    }
    if modular:
        provenance.update({
            "organ_context_schema": organ_context.get("schema"),
            "module_count": organ_context.get("module_count"),
            "module_registry_sha256": organ_context.get("module_registry_sha256"),
            "self_memory_digest_sha256": self_memory.get("digest_sha256"),
            "self_memory_file_count": self_memory.get("file_count"),
        })

    return {
        "schema": "janus.model.reflection_proposal.v1",
        "reflection_id": f"jnr-{reflection_id}",
        "status": "UNVERIFIED_MODEL_REFLECTION",
        "authority": {
            "truth": False,
            "evidence": False,
            "execution": False,
            "repository_mutation": False,
            "eligible_for_training": False,
            "eligible_for_truth_promotion": False,
            "independent_verifier_required": True,
        },
        "provenance": provenance,
        "modular_context": {
            "enabled": modular,
            "module_count": organ_context.get("module_count") if modular else 2,
            "self_memory_bound": modular,
            "self_memory_digest_sha256": self_memory.get("digest_sha256") if modular else None,
            "module_observation_grants_mutation": False,
            "raw_self_reflection_is_training_source": False,
        },
        "bicameral_context": {
            "formula": organ_context.get("canonical_formula"),
            "HRAiN": "STRUCTURAL_CONTEXT_GROUNDING_MEDIATOR",
            "iNaiHR": "ASSOCIATIVE_CONTEXT",
            "terminal_authority": "VERIFY",
            "agreement_is_truth": False,
        },
        "reflection": {
            "prompt": prompt,
            "native_model_output": inference_text[:8000],
        },
        "promotion_contract": {
            "current_lane": "PROPOSAL_ONLY",
            "required_next_lane": "INDEPENDENT_VERIFY_OR_HUMAN_REVIEW",
            "raw_model_output_must_not_reenter_training": True,
            "promotion_target_if_verified": "VERIFIED_DERIVED_MEMORY",
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--organ-context", required=True)
    ap.add_argument("--inference", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--out-dir", default="janus_model/outbox")
    args = ap.parse_args()
    reflection = build_reflection(
        Path(args.checkpoint),
        Path(args.state),
        Path(args.organ_context),
        Path(args.inference),
        args.prompt,
        args.run_id,
    )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"reflection-{reflection['reflection_id']}.json"
    out.write_text(json.dumps(reflection, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"status": reflection["status"], "reflection_id": reflection["reflection_id"], "path": out.as_posix()}, indent=2))


if __name__ == "__main__":
    main()
