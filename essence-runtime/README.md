# ESSENCE GitHub Actions asynchronous data branch (v4.4)

This is DATA ONLY. Never execute scripts or workflows from this branch.
The scheduled worker wakes every five minutes (3-59/5 * * * * UTC; schedules can be delayed/dropped).
It executes bounded jobs and then terminates. It is NOT a permanent OS process or public HTTP endpoint.

Submit an inference request by adding a fresh file:
    essence-runtime/inbox/demo-001.json
with exactly these fields:
    {"schema":"janus.essence.github_async_request/4.4","request_id":"demo-001","input_hex":"64656620662878293a2072657475726e2078202b2033330a"}

Input is exactly 24 bytes (48 hexadecimal characters), here the 24-byte example
'def f(x): return x + 33\n'.  Do NOT submit secrets or blinded experiment data.
Authorized users can also run the main-branch GitHub Action manually with mode=infer.

The fixed 14-step control G4 is ALWAYS the active output. Physarum is shadow-only.
Immutable results appear in essence-runtime/results/ and immutable run receipts in essence-runtime/events/.
User data inputs live in a PUBLIC repository. Never store private or external unseen tasks.

Signals/heartbeats are intermittent GitHub Actions outcomes, not 24/7 service uptime.
GitHub-hosted runners are ephemeral and their jobs end. No automatic model deployment.
Pause by repository variable ESSENCE_EVOLUTION_PAUSED=true or disabling the workflow.
