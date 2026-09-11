from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from janus_model.model import ByteTokenizer
from janus_model.train_registry import load_checkpoint, sha256_file

ALLOWED_ORGAN_CONTEXT_STATUSES = {"READ_ONLY_ORGAN_CONTEXT", "READ_ONLY_MODULAR_ORGAN_CONTEXT"}
PROMPT_PREFIX = "Q:"
CONTEXT_PREFIX = "C:"
ASSISTANT_SUFFIX = "\nJANUS:"


def _utf8_tail(text: str, max_bytes: int) -> str:
    if max_bytes <= 0:
        return ""
    raw = text.encode("utf-8", errors="replace")
    if len(raw) <= max_bytes:
        return text
    tail = raw[-max_bytes:]
    while tail and (tail[0] & 0xC0) == 0x80:
        tail = tail[1:]
    return tail.decode("utf-8", errors="ignore")


def _derive_compact_context(obj: dict) -> str:
    compact = obj.get("native_prompt_compact")
    if isinstance(compact, str) and compact.strip():
        return compact.strip()

    organs = obj.get("organs") or {}
    hrain = ((organs.get("HRAiN") or {}).get("target_commit") or "NONE")[:8]
    inaihr = ((organs.get("iNaiHR") or {}).get("target_commit") or "NONE")[:8]
    trump = obj.get("trump_research") or {}
    intake = trump.get("native_frontier_intake") or {}
    intake_commit = (intake.get("selected_commit") or "NONE")[:8]
    p_vs_np = trump.get("P_VS_NP") or "OPEN"
    modules = int(obj.get("module_count") or 0)
    return f"M{modules}|H{hrain}|I{inaihr}|T{p_vs_np}|F{intake_commit}|V1"


def _load_read_only_organ_context(organ_context_path: str) -> dict:
    path = Path(organ_context_path)
    if not path.exists():
        raise SystemExit("JANUS_ORGAN_CONTEXT_MISSING")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("status") not in ALLOWED_ORGAN_CONTEXT_STATUSES:
        raise SystemExit("JANUS_ORGAN_CONTEXT_NOT_READ_ONLY")
    firewalls = obj.get("firewalls") or {}
    if firewalls.get("read_only") is not True or firewalls.get("terminal_authority") != "VERIFY":
        raise SystemExit("JANUS_ORGAN_CONTEXT_FIREWALL_FAIL")
    if obj.get("status") == "READ_ONLY_MODULAR_ORGAN_CONTEXT":
        if int(obj.get("module_count") or 0) < 2:
            raise SystemExit("JANUS_MODULAR_ORGAN_COUNT_INVALID")
        if firewalls.get("module_observation_grants_mutation") is not False:
            raise SystemExit("JANUS_MODULE_OBSERVATION_AUTHORITY_FAIL")
        if firewalls.get("raw_self_reflection_is_training_source") is not False:
            raise SystemExit("JANUS_SELF_MEMORY_TRAINING_FIREWALL_FAIL")
    return obj


def _pack_prompt(prompt: str, compact_context: str, context_length: int) -> str:
    """Pack user intent + verified context so neither is silently evicted.

    The native model is byte-tokenized, and BOS consumes one token. We reserve
    the compact context and the JANUS response marker first, then retain as much
    of the *tail* of the user prompt as the model can actually attend to. This
    makes truncation explicit and deterministic instead of relying on the model's
    hidden last-N-token crop.
    """
    if context_length < 32:
        raise SystemExit("JANUS_CONTEXT_LENGTH_TOO_SMALL_FOR_SAFE_PACKING")
    text_budget = context_length - 1  # BOS
    fixed = f"\n{CONTEXT_PREFIX}{compact_context}{ASSISTANT_SUFFIX}"
    fixed_bytes = len(fixed.encode("utf-8"))
    prompt_prefix_bytes = len(PROMPT_PREFIX.encode("utf-8"))
    prompt_budget = text_budget - fixed_bytes - prompt_prefix_bytes
    if prompt_budget < 8:
        raise SystemExit("JANUS_COMPACT_CONTEXT_EXCEEDS_MODEL_BUDGET")
    prompt_tail = _utf8_tail(prompt, prompt_budget)
    packed = f"{PROMPT_PREFIX}{prompt_tail}{fixed}"
    token_count = len(ByteTokenizer.encode(packed, bos=True))
    if token_count > context_length:
        raise SystemExit("JANUS_PROMPT_PACKING_OVERFLOW")
    return packed


def _augment_prompt(prompt: str, organ_context_path: str | None, context_length: int | None = None) -> str:
    if not organ_context_path:
        if context_length is None:
            return prompt
        prompt_budget = context_length - 1
        packed = _utf8_tail(prompt, prompt_budget)
        if len(ByteTokenizer.encode(packed, bos=True)) > context_length:
            raise SystemExit("JANUS_PROMPT_PACKING_OVERFLOW")
        return packed

    obj = _load_read_only_organ_context(organ_context_path)
    if context_length is not None:
        return _pack_prompt(prompt, _derive_compact_context(obj), context_length)

    # Compatibility path for older callers/tests that explicitly request the
    # unbounded descriptive suffix. Runtime inference always passes a budget.
    suffix = obj.get("native_prompt_suffix")
    if not isinstance(suffix, str) or not suffix:
        suffix = _derive_compact_context(obj)
    return f"{prompt}\n{suffix}\nJANUS:"


def main():
    ap = argparse.ArgumentParser(prog="janus")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--checkpoint", default="janus_model/checkpoints/promoted.pt")
    run.add_argument("--prompt", required=True)
    run.add_argument("--organ-context")
    run.add_argument("--max-new-tokens", type=int, default=160)
    run.add_argument("--temperature", type=float, default=0.75)
    ins = sub.add_parser("inspect")
    ins.add_argument("--checkpoint", default="janus_model/checkpoints/promoted.pt")
    a = ap.parse_args()
    path = Path(a.checkpoint)
    if not path.exists():
        raise SystemExit("JANUS_CHECKPOINT_MISSING")
    model, obj = load_checkpoint(path)
    if a.cmd == "inspect":
        print(
            json.dumps(
                {
                    "checkpoint_sha256": sha256_file(path),
                    "config": obj["config"],
                    "meta": obj.get("meta", {}),
                    "external_llm": False,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return
    prompt = _augment_prompt(a.prompt, a.organ_context, model.config.context_length)
    ids = ByteTokenizer.encode(prompt, bos=True)
    if len(ids) > model.config.context_length:
        raise SystemExit("JANUS_RUNTIME_PROMPT_EXCEEDS_CONTEXT")
    x = torch.tensor([ids], dtype=torch.long)
    torch.manual_seed(20260901)
    out = model.generate(
        x,
        max_new_tokens=a.max_new_tokens,
        temperature=a.temperature,
        top_k=40,
    )[0].tolist()
    print(ByteTokenizer.decode(out))


if __name__ == "__main__":
    main()
