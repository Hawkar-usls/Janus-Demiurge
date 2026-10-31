# JANUS DADDY_KEYMASTER R5 — signed owner-node enrollment (candidate only)

This is the **credential-free candidate attestation protocol**, not an
automatic remote execution driver or an assertion of server uptime.

## Admission sequence

1. A trusted coordinator creates a random 256-bit nonce and exact 40-hex
   source commit pin, an issue time and expiry no later than 300 seconds.
   The coordinator retains the challenge and a consumed-nonce ledger.
2. The owner-connected candidate signs a strictly typed JSON envelope with
   its locally protected OpenSSH Ed25519 private key using the namespace
   janus-daddy-keymaster-owner-candidate-v1. Never transfer the private key.
3. The independent verifier already knows the candidate's approved public key
   **out of band**; it must never trust a key supplied within the envelope.
   It verifies the SSH signature, source pin, nonce, TTL, node identity,
   max concurrency 1, one allowed kind (pure_module_eval), the digest of an
   existing local canary receipt and a fixed CANDIDATE_ONLY status.
4. A valid proof returns CRYPTOGRAPHICALLY_VERIFIED_CANDIDATE_ONLY with
   remote_dispatch_enabled=false, permanent_availability_attested=false,
   authority_delta=0. This never mutates OWNER_REGISTRY.json, grants a
   GitHub token, or starts a job. Replaying an already consumed nonce fails.

## Security and truth boundaries

- An ephemeral challenge used in unit tests is synthetic and not a signed
  production challenge from a separate trust authority. The caller must
  obtain it through its already authenticated coordinator channel.
- The signer proves control of the pinned private key **at one instant**.
  This does not prove 24/7 availability, uninterrupted power, owner
  consent for a specific workload, CPU budget enforcement, that the canary
  receipt is truthful, or a tested remote lease recovery. None should be
  inferred from a green cryptographic test.
- Revocation requires a trusted registry or coordinator refusing a given
  public key; no production key distribution or revocation infrastructure
  is enabled by this module.
- Public key enrollment is distinct from provider admission. It should be
  explicitly reviewed, revocable and scoped to a host controlled by owner.
- There are no SSH inbound ports, credential reuse, public scans, generic
  shell execution, GitHub Actions self-requeue, paid providers or champion
  model writes. OWNER_REGISTRY remains empty.

## Local test

    python -m unittest discover -s tests -p test_daddy_keymaster_signed_enrollment.py -v

Tests create ephemeral keypairs within temporary directories, sign exact
challenge envelopes, and reject wrong public keys, expired/replayed nonces,
tampered canary receipt digests, foreign worker identities, privilege
escalation, future timestamps, and extra arbitrary fields.

## What is still needed for live owner-node admission

An always-reachable owner-approved endpoint or narrowly scoped outbound
coordinator, authenticated challenge issuance, durable consumed-nonce ledger,
revocation, CPU/memory/thermal/power quotas, heartbeat continuity measured
over a reasonable window, outbound-only worker lease handling, independent
receipt Witness and crash-reconciliation. Only after separate owner approval
could a provider adapter become authorized. Native Demiurge R2 #385 and
secure loader #301 remain separate HOLD gates.

Private keys, hostnames, local IPs and personal disk paths must **never**
be committed to GitHub or Meta Registry.
