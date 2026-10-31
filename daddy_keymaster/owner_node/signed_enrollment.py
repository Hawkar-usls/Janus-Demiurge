"""JANUS DADDY_KEYMASTER owner-node signed enrollment R5 (candidate stage).

A bounded SSH Ed25519 signature proves key possession for an independently
provided challenge. It DOES NOT authorize execution, accept a new provider,
expose credentials, write registry state, or establish 24/7 uptime.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

SCHEMA_CHALLENGE = "janus.daddy_keymaster.owner_challenge.v1"
SCHEMA_ATTEST = "janus.daddy_keymaster.owner_attestation.v1"
NAMESPACE = "janus-daddy-keymaster-owner-candidate-v1"
ISSUER = "JANUS_OWNER_ENROLLMENT_LAB"
KIND = "pure_module_eval"
MAX_TTL_SECONDS = 300
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SHA1 = re.compile(r"^[0-9a-f]{40}$")
NODE_ID = re.compile(r"^owner-candidate-[a-z0-9-]{6,40}$")
NONCE = re.compile(r"^[0-9a-f]{64}$")


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),
                      ensure_ascii=False,allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def exactly(obj, fields):
    if not isinstance(obj, dict) or set(obj) != set(fields):
        raise ValueError("ENROLL_UNEXPECTED_FIELDS")


def timestamp(s):
    if not isinstance(s, str) or not s.endswith("Z"):
        raise ValueError("ENROLL_UTC_REQUIRED")
    try:
        t=datetime.fromisoformat(s[:-1]+"+00:00")
    except ValueError as exc:
        raise ValueError("ENROLL_BAD_TIME") from exc
    if t.utcoffset()!=timedelta():
        raise ValueError("ENROLL_NOT_UTC")
    return t


def utc(d):
    return d.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")


def challenge(source_sha, nonce, issued_utc, duration=180):
    if not isinstance(source_sha,str) or not SHA1.fullmatch(source_sha):
        raise ValueError("ENROLL_SOURCE_PIN_REQUIRED")
    if not isinstance(nonce,str) or not NONCE.fullmatch(nonce):
        raise ValueError("ENROLL_RANDOM_NONCE_REQUIRED")
    if type(duration) is not int or not 1 <= duration <= MAX_TTL_SECONDS:
        raise ValueError("ENROLL_TTL_OUT_OF_BOUNDS")
    start=timestamp(issued_utc)
    return {
        "schema":SCHEMA_CHALLENGE,
        "issuer":ISSUER,
        "purpose":"CANDIDATE_PROOF_ONLY_NO_REMOTE_EXECUTION",
        "nonce":nonce,
        "source_sha":source_sha,
        "allowed_kind":KIND,
        "max_concurrent":1,
        "issued_at":issued_utc,
        "expires_at":utc(start+timedelta(seconds=duration)),
    }


def validate_challenge(c, at):
    exactly(c,("schema","issuer","purpose","nonce","source_sha",
               "allowed_kind","max_concurrent","issued_at","expires_at"))
    if (c["schema"]!=SCHEMA_CHALLENGE or c["issuer"]!=ISSUER or
        c["purpose"]!="CANDIDATE_PROOF_ONLY_NO_REMOTE_EXECUTION" or
        c["allowed_kind"]!=KIND or type(c["max_concurrent"]) is not int
        or c["max_concurrent"]!=1 or
        not isinstance(c["nonce"],str) or not NONCE.fullmatch(c["nonce"]) or
        not isinstance(c["source_sha"],str) or not SHA1.fullmatch(c["source_sha"])):
        raise ValueError("ENROLL_BAD_CHALLENGE_AUTHORITY")
    issued,expires=timestamp(c["issued_at"]),timestamp(c["expires_at"])
    if not timedelta(0)<expires-issued<=timedelta(seconds=MAX_TTL_SECONDS):
        raise ValueError("ENROLL_BAD_CHALLENGE_TTL")
    at_dt=timestamp(at)
    if at_dt<issued or at_dt>=expires:
        raise ValueError("ENROLL_EXPIRED_OR_PREMATURE")
    return c


def _pubkey(s):
    if not isinstance(s,str) or len(s)>400 or "\n" in s or "\r" in s:
        raise ValueError("ENROLL_BAD_PUBLIC_KEY")
    bits=s.strip().split()
    if (len(bits) not in (2,3) or bits[0]!="ssh-ed25519" or
        not re.fullmatch(r"[A-Za-z0-9+/]+={0,2}",bits[1])):
        raise ValueError("ENROLL_ED25519_PUBLIC_KEY_REQUIRED")
    return bits[0]+" "+bits[1]


def _gitless_sign(private_path, payload):
    result=subprocess.run(
        ["ssh-keygen","-Y","sign","-f",str(private_path),"-n",NAMESPACE],
        input=payload,capture_output=True,check=False,timeout=15,
    )
    if result.returncode:
        raise ValueError("ENROLL_SIGNING_KEY_UNAVAILABLE")
    raw=result.stdout.decode("utf-8")
    if ("-----BEGIN SSH SIGNATURE-----" not in raw or
        "-----END SSH SIGNATURE-----" not in raw or len(raw)>1500):
        raise ValueError("ENROLL_BAD_SIGNATURE_ENCODING")
    return raw


def make_attestation(c, node_id, source_canary_sha256, observed_utc,
                     private_key_path):
    validate_challenge(c, observed_utc)
    if not isinstance(node_id,str) or not NODE_ID.fullmatch(node_id):
        raise ValueError("ENROLL_NODE_ID_INVALID")
    if (not isinstance(source_canary_sha256,str) or
        not SHA256.fullmatch(source_canary_sha256)):
        raise ValueError("ENROLL_CANARY_PROOF_REQUIRED")
    body={
        "schema":SCHEMA_ATTEST,
        "node_id":node_id,
        "challenge_sha256":digest(c),
        "source_sha":c["source_sha"],
        "canary_receipt_sha256":source_canary_sha256,
        "observed_at":observed_utc,
        "allowed_kinds":[KIND],
        "max_concurrent":1,
        "status":"CANDIDATE_ONLY_NO_REMOTE_DISPATCH",
        "authority_delta":0,
        "claimed_uptime":"NOT_ATTESTED",
    }
    return body, _gitless_sign(private_key_path,canonical(body))


def verify_attestation(body, signature, challenge_obj, pinned_public_key,
                       expected_node_id, used_nonces, verified_at_utc):
    if not isinstance(used_nonces,(set,frozenset)):
        raise ValueError("ENROLL_REPLAY_LEDGER_REQUIRED")
    validate_challenge(challenge_obj,verified_at_utc)
    if challenge_obj["nonce"] in used_nonces:
        raise ValueError("ENROLL_REPLAY_NONCE")
    exactly(body,("schema","node_id","challenge_sha256","source_sha",
                  "canary_receipt_sha256","observed_at","allowed_kinds",
                  "max_concurrent","status","authority_delta","claimed_uptime"))
    if (body["schema"]!=SCHEMA_ATTEST or body["node_id"]!=expected_node_id or
        not NODE_ID.fullmatch(body["node_id"]) or
        body["challenge_sha256"]!=digest(challenge_obj) or
        body["source_sha"]!=challenge_obj["source_sha"] or
        not isinstance(body["canary_receipt_sha256"],str) or
        not SHA256.fullmatch(body["canary_receipt_sha256"]) or
        body["allowed_kinds"]!=[KIND] or
        type(body["max_concurrent"]) is not int or body["max_concurrent"]!=1 or
        body["status"]!="CANDIDATE_ONLY_NO_REMOTE_DISPATCH" or
        type(body["authority_delta"]) is not int or body["authority_delta"]!=0 or
        body["claimed_uptime"]!="NOT_ATTESTED"):
        raise ValueError("ENROLL_CAPABILITY_OR_SOURCE_ESCALATION")
    validate_challenge(challenge_obj,body["observed_at"])
    if timestamp(body["observed_at"])>timestamp(verified_at_utc):
        raise ValueError("ENROLL_ATTESTATION_FROM_FUTURE")
    if (not isinstance(signature,str) or len(signature)>1500 or
        "-----BEGIN SSH SIGNATURE-----" not in signature or
        "-----END SSH SIGNATURE-----" not in signature):
        raise ValueError("ENROLL_SIGNATURE_REQUIRED")
    # Critical: the verifying public key is an OUT-OF-BAND pinned value, NOT
    # a key dynamically discovered inside a candidate's supplied payload.
    key=_pubkey(pinned_public_key)
    with tempfile.TemporaryDirectory() as d:
        allowed=Path(d)/"allowed_signers"
        sig=Path(d)/"attestation.sig"
        allowed.write_text(body["node_id"]+" "+key+"\n",encoding="utf-8")
        sig.write_text(signature,encoding="utf-8")
        result=subprocess.run(
            ["ssh-keygen","-Y","verify","-f",str(allowed),
             "-I",body["node_id"],"-n",NAMESPACE,"-s",str(sig)],
            input=canonical(body),capture_output=True,check=False,timeout=15,
        )
    if result.returncode:
        raise ValueError("ENROLL_SIGNATURE_NOT_AUTHENTIC")
    # Caller persists nonce only after independently approving/admitting this
    # proof. Never mutate a shared replay ledger in a read-only witness.
    return {
        "status":"CRYPTOGRAPHICALLY_VERIFIED_CANDIDATE_ONLY",
        "node_id":body["node_id"],
        "challenge_sha256":digest(challenge_obj),
        "public_key_sha256":hashlib.sha256(key.encode()).hexdigest(),
        "canary_receipt_sha256":body["canary_receipt_sha256"],
        "candidate_allowed_kinds":[KIND],
        "max_concurrent":1,
        "remote_dispatch_enabled":False,
        "permanent_availability_attested":False,
        "authority_delta":0,
    }
