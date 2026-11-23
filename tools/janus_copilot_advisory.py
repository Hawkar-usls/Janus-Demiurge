#!/usr/bin/env python3
"""JANUS advisory Copilot SDK worker; no tools, shell, writes, or deploy."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

MAX_PROMPT = 3000
MAX_ANSWER = 10000


def authorized() -> bool:
    return bool(os.getenv("COPILOT_GITHUB_TOKEN") or os.getenv("GH_TOKEN"))


def package_result(reply: str, model: str) -> dict:
    return {
        "schema": "JANUS_COPILOT_SDK_ADVISORY_V1",
        "status": "ADVISORY_ONLY",
        "evidence": "MODEL_OUTPUT_NOT_INDEPENDENT_EVIDENCE",
        "model": model,
        "reply": str(reply)[:MAX_ANSWER],
        "permissions": {
            "shell": False, "files": False, "network_tools": False,
            "git_push": False, "deploy": False,
        },
        "requires_human_or_policy_gate": True,
        "applied": False,
    }


async def run(prompt: str, model: str, timeout: float) -> dict:
    if not authorized():
        raise RuntimeError("copilot_auth_not_configured")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > MAX_PROMPT:
        raise ValueError("invalid_prompt_length")

    from copilot import CopilotClient
    from copilot.rpc import PermissionDecisionReject

    def deny_all_permissions(request, invocation):
        return PermissionDecisionReject(feedback="JANUS advisory worker: tool use denied")

    async with CopilotClient(mode="empty") as client:
        async with await client.create_session(
            model=model,
            available_tools=[],
            on_permission_request=deny_all_permissions,
            infinite_sessions={"enabled": False},
            memory={"enabled": False},
        ) as session:
            event = await asyncio.wait_for(
                session.send_and_wait(prompt), timeout=max(5, min(timeout, 180))
            )
    if event is None:
        raise RuntimeError("copilot_no_reply")
    content = getattr(getattr(event, "data", None), "content", None)
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("copilot_empty_reply")
    return package_result(content, model)


def main() -> int:
    parser = argparse.ArgumentParser(description="JANUS advisory Copilot SDK bridge")
    parser.add_argument("--model", default="auto")
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--stdin", action="store_true", help="Read prompt from stdin, not argv")
    args = parser.parse_args()
    if not args.stdin:
        print(json.dumps({"ok": False, "error": "stdin_prompt_required"}))
        return 2
    prompt = sys.stdin.read(MAX_PROMPT + 1)
    try:
        result = asyncio.run(run(prompt, args.model, args.timeout))
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False))
        return 0
    except Exception as exc:
        known = {"copilot_auth_not_configured", "invalid_prompt_length",
                 "copilot_no_reply", "copilot_empty_reply"}
        reason = str(exc) if str(exc) in known else "copilot_request_failed"
        print(json.dumps({"ok": False, "error_type": exc.__class__.__name__,
                          "error": reason}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
