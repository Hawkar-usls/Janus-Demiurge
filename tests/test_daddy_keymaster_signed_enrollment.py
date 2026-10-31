"""Adversarial candidate enrollment tests: real SSH Ed25519 signatures."""
from __future__ import annotations
import hashlib
from pathlib import Path
import secrets
import subprocess
import tempfile
import unittest

from daddy_keymaster.owner_node.signed_enrollment import (
    challenge, make_attestation, verify_attestation, digest,
)

SRC="b"*40
NOW="2026-10-31T16:30:10Z"
CHECK="2026-10-31T16:30:20Z"
EXPIRED="2026-10-31T16:36:00Z"
NODE="owner-candidate-synthetic-01"
CANARY=hashlib.sha256(b"public-synthetic-test").hexdigest()


class EnrollmentTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.priv=self.keypair("first")
        self.pub=(self.root/"first.pub").read_text().strip()
        self.c=challenge(SRC,secrets.token_hex(32),"2026-10-31T16:30:00Z",180)

    def keypair(self, name):
        p=self.root/name
        x=subprocess.run(["ssh-keygen","-q","-t","ed25519","-N","","-f",str(p)],
                         capture_output=True,check=False,timeout=15)
        if x.returncode:
            raise RuntimeError("OPENSSH_KEYGEN_UNAVAILABLE")
        return p

    def token(self):
        return make_attestation(self.c,NODE,CANARY,NOW,self.priv)

    def verify(self, body, sig, **kwargs):
        return verify_attestation(body,sig,kwargs.get("challenge",self.c),
                                  kwargs.get("public_key",self.pub),
                                  kwargs.get("node_id",NODE),
                                  kwargs.get("used_nonces",set()),
                                  kwargs.get("verified_at",CHECK))

    def test_correct_source_pinned_signature_is_candidate_only(self):
        body,signature=self.token()
        proof=self.verify(body,signature)
        self.assertEqual(proof["status"],"CRYPTOGRAPHICALLY_VERIFIED_CANDIDATE_ONLY")
        self.assertFalse(proof["remote_dispatch_enabled"])
        self.assertFalse(proof["permanent_availability_attested"])
        self.assertEqual(proof["max_concurrent"],1)
        self.assertNotIn("PRIVATE KEY",str(proof))

    def test_tamper_capabilities_denied_even_with_old_valid_signature(self):
        body,sig=self.token()
        body["allowed_kinds"]=["pure_module_eval","run_shell"]
        with self.assertRaises(ValueError):
            self.verify(body,sig)
        body,sig=self.token()
        body["canary_receipt_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"ENROLL_SIGNATURE_NOT_AUTHENTIC"):
            self.verify(body,sig)

    def test_wrong_pinned_public_key_denied(self):
        body,sig=self.token()
        other=self.keypair("attacker")
        with self.assertRaisesRegex(ValueError,"ENROLL_SIGNATURE_NOT_AUTHENTIC"):
            self.verify(body,sig,public_key=(self.root/"attacker.pub").read_text().strip())

    def test_expired_challenge_denied(self):
        body,sig=self.token()
        with self.assertRaisesRegex(ValueError,"ENROLL_EXPIRED"):
            self.verify(body,sig,verified_at=EXPIRED)

    def test_nonce_replay_denied(self):
        body,sig=self.token()
        with self.assertRaisesRegex(ValueError,"ENROLL_REPLAY_NONCE"):
            self.verify(body,sig,used_nonces={self.c["nonce"]})

    def test_wrong_challenge_denied(self):
        body,sig=self.token()
        other=challenge(SRC,secrets.token_hex(32),"2026-10-31T16:30:00Z")
        with self.assertRaisesRegex(ValueError,"ENROLL_CAPABILITY_OR_SOURCE_ESCALATION"):
            self.verify(body,sig,challenge=other)

    def test_forged_node_id_denied(self):
        body,sig=self.token()
        with self.assertRaises(ValueError):
            self.verify(body,sig,node_id="owner-candidate-other")
        with self.assertRaisesRegex(ValueError,"ENROLL_SIGNATURE_NOT_AUTHENTIC"):
            forged={**body,"node_id":"owner-candidate-other"}
            self.verify(forged,sig,node_id="owner-candidate-other")

    def test_future_attestation_denied(self):
        body,sig=make_attestation(self.c,NODE,CANARY,"2026-10-31T16:30:40Z",self.priv)
        with self.assertRaisesRegex(ValueError,"ENROLL_ATTESTATION_FROM_FUTURE"):
            self.verify(body,sig)

    def test_no_unbounded_ttl(self):
        with self.assertRaisesRegex(ValueError,"ENROLL_TTL_OUT_OF_BOUNDS"):
            challenge(SRC,secrets.token_hex(32),"2026-10-31T16:30:00Z",30000)

    def test_unknown_attestation_field_rejected(self):
        body,sig=self.token()
        body["ssh_command"]="rm -rf"
        with self.assertRaisesRegex(ValueError,"ENROLL_UNEXPECTED_FIELDS"):
            self.verify(body,sig)

    def test_empty_invalid_public_key_refused(self):
        body,sig=self.token()
        with self.assertRaises(ValueError):
            self.verify(body,sig,public_key="")

if __name__=="__main__":
    unittest.main()
