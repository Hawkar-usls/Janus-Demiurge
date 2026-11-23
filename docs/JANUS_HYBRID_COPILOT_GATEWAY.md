# JANUS Hybrid AI — GitHub Copilot SDK advisory worker

Status: DRAFT / SCAFFOLD_ONLY / NO_LIVE_COPILOT_RUN.

GitHub Models API was retired July 30, 2026. This worker instead uses the GitHub Copilot SDK, which has its own authentication, subscription/quota, and execution rules. GitHub Actions are ephemeral jobs, not a permanently running model server.

## What it does

- Accepts one short task from standard input.
- Uses a separately authenticated Copilot SDK session with no tools or persistent memory.
- Denies tool permission requests, never writes files, runs shell commands, deploys services or merges PRs.
- Emits a JSON advisory envelope, explicitly marking model text as unverified and not applied.
- Has no NAS access, private memory, or repository secrets built into its source.

## Local execution

Requires Python 3.11+, github-copilot-sdk, its runtime, and an independently authorized Copilot identity. Do not install this SDK into the user's protected NAS containers.

    python -m pip install github-copilot-sdk
    python -m copilot download-runtime

With the correct authenticated SDK environment set:

    echo "Summarize CI blockers without changing anything" | python tools/janus_copilot_advisory.py --stdin --model auto

## Before connecting it to JANUS

1. Establish a separate Copilot identity and verify its permitted usage and actual inference quota. The built-in GitHub Actions GITHUB_TOKEN does not itself prove Copilot entitlement.
2. Build a narrow, authenticated, replay-resistant dispatch path with a bounded queue and no secrets or sensitive prompts in Actions logs.
3. Test permission denial, failure fallback, cost/latency, and independent evaluation of recommendations.
4. Keep all code and NAS changes behind existing JANUS authorization and recovery gates.

No automatic workflow dispatch, installation, model session, code change, pull-request merge, or NAS mutation is enabled by this draft.

Acceptance: SCAFFOLD_ONLY / AUTHENTICATION_UNVERIFIED / NO_LIVE_COPILOT_RUN.
