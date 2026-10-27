# HRAiN canonical v78 server: local-only authority (2026-10-27)

The historical `server.py` bound to `0.0.0.0:1138` and previously accepted unauthenticated graph data and device commands. Canonical defaults now bind only to `127.0.0.1:1138`; API and WebSocket calls require a *locally supplied* `JANUS_HRAIN_LOCAL_API_TOKEN` (24–256 characters) in `X-JANUS-Local-Token`. The server must never commit, print or transmit this token into public artifacts.

- Every request requires loopback peer and exact local Host; cross-origin requests are denied, including GET paths that consume device commands.
- The local root page and health request remain readable on loopback without a token; this does **not** enable sensitive API access.
- Legacy full-graph POST `/api/hrain/save` is blocked (409) even with valid authentication because frontend projections omit provenance, weighted relations and historical data.
- Existing HRAiN frontend/API integrations need explicit local token transport before consuming `/api/*` or `/ws`; do not introduce an unauthenticated bypass or write the token into static public HTML.
- The owner-local v89 server already used loopback + a similar local API token middleware; this PR aligns the repository's historical v78 server, not a claim of remote public deployment.
- Future multi-device or cloud services must use a separate authenticated proxy/authority protocol and audit trail. No unrestricted port-forwarding and no automatic production restart.
