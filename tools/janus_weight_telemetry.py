from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import torch


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tensor_stats(name: str, tensor: torch.Tensor) -> dict:
    x = tensor.detach().cpu()
    xf = x.to(torch.float64)
    numel = int(x.numel())
    if numel:
        mean = float(xf.mean().item())
        std = float(xf.std(unbiased=False).item())
        minimum = float(xf.min().item())
        maximum = float(xf.max().item())
        l2 = float(torch.linalg.vector_norm(xf).item())
    else:
        mean = std = minimum = maximum = l2 = 0.0
    values = [mean, std, minimum, maximum, l2]
    if not all(math.isfinite(v) for v in values):
        raise SystemExit(f"NONFINITE_TENSOR_TELEMETRY:{name}")
    return {
        "name": name,
        "shape": list(x.shape),
        "dtype": str(x.dtype).replace("torch.", ""),
        "numel": numel,
        "mean": mean,
        "std": std,
        "min": minimum,
        "max": maximum,
        "l2": l2,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--decision-dir", required=True)
    ap.add_argument("--telemetry-out", required=True)
    ap.add_argument("--decision-out", required=True)
    args = ap.parse_args()

    checkpoint = Path(args.checkpoint)
    state_path = Path(args.state)
    decision_dir = Path(args.decision_dir)
    telemetry_out = Path(args.telemetry_out)
    decision_out = Path(args.decision_out)

    state = json.loads(state_path.read_text(encoding="utf-8"))
    checkpoint_sha = sha256_file(checkpoint)
    if state.get("checkpoint_sha256") != checkpoint_sha:
        raise SystemExit("AUTHORITATIVE_STATE_CHECKPOINT_SHA_MISMATCH")

    obj = torch.load(checkpoint, map_location="cpu", weights_only=False)
    model_state = obj.get("model_state")
    if not isinstance(model_state, dict) or not model_state:
        raise SystemExit("CHECKPOINT_MODEL_STATE_MISSING")

    tensors = [tensor_stats(name, tensor) for name, tensor in sorted(model_state.items())]
    parameter_count = sum(row["numel"] for row in tensors)
    squared_l2 = sum(row["l2"] ** 2 for row in tensors)
    telemetry = {
        "schema": "janus.native_weight_telemetry.v1",
        "status": "CHECKPOINT_BOUND_TENSOR_TELEMETRY",
        "checkpoint_sha256": checkpoint_sha,
        "model_status": state.get("status"),
        "attempt_count": state.get("attempt_count"),
        "promotion_count": state.get("promotion_count"),
        "rejection_count": state.get("rejection_count"),
        "parameter_count": parameter_count,
        "tensor_count": len(tensors),
        "global_l2": math.sqrt(squared_l2),
        "config": obj.get("config") or state.get("config"),
        "checkpoint_meta": obj.get("meta") or {},
        "tensors": tensors,
        "authority": {
            "telemetry_is_weight_identity": False,
            "checkpoint_sha256_is_weight_identity": True,
            "telemetry_grants_mutation_authority": False,
        },
    }
    telemetry_out.parent.mkdir(parents=True, exist_ok=True)
    telemetry_out.write_text(json.dumps(telemetry, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    matches = []
    if decision_dir.exists():
        for path in sorted(decision_dir.glob("decision-*.json")):
            try:
                decision = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if decision.get("checkpoint_sha256") == checkpoint_sha:
                matches.append((path, decision))
    if len(matches) > 1:
        raise SystemExit("MULTIPLE_NATIVE_DECISIONS_FOR_CURRENT_CHECKPOINT")
    if matches:
        decision_out.parent.mkdir(parents=True, exist_ok=True)
        decision_out.write_text(json.dumps(matches[0][1], ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        decision_status = matches[0][1].get("status")
    else:
        decision_status = "NO_MATCHING_DECISION"

    print(json.dumps({
        "checkpoint_sha256": checkpoint_sha,
        "parameter_count": parameter_count,
        "tensor_count": len(tensors),
        "decision_status": decision_status,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
