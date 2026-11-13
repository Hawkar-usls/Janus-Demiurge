#!/usr/bin/env python3
"""ESSENCE v1.0 signed, independent model-admission preparation.

This is a read-only eligibility checker. It NEVER promotes a model, swaps a
checkpoint, edits production state, executes donor code, or invokes an agent.
A candidate is review-eligible only after BOTH genuine future cohorts and
two role-separated signatures from independently provisioned out-of-band
public keys; the repository does not contain trusted promotion keys.

Even cryptographic verification proves key possession, not independent
scientific competence or owner authorization. Final production deployment
requires a separate reviewed PR and existing native checkpoint preflight.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile

PROTOCOL = "janus.essence.preregistered_dual_lane/0.7"
REPORT = "janus.essence.paired_trial_report/0.7"
SCHEMA = "janus.essence.model_admission_review/1.0"
ATTEST = "janus.essence.external_attestation/1.0"
NAMESPACE = "janus-essence-model-review-v1"
LOCKED_PROTOCOL_SHA256 = "ba295aa8d44c0d735624e07dbd9163a20bb03cde28570aa516cd1708c068fef8"
SHA64 = re.compile(r"^[0-9a-f]{64}$")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
KEY = re.compile(r"^ssh-ed25519 [A-Za-z0-9+/]+={0,2}$")
MAX_BYTES = 1_000_000
PERMITTED_ROLES = ("source_custodian", "external_model_reviewer")
TARGET_REPO = "Hawkar-usls/Janus-Demiurge"
PRODUCTION_AUTHORITY = False

def canonical(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode()

def digest(x):
    return hashlib.sha256(canonical(x)).hexdigest()

def load(path):
    p=Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size>MAX_BYTES:
        raise ValueError("ADMISSION_UNSAFE_FILE")
    return json.loads(p.read_text(encoding="utf-8"),
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))

def stamp(s):
    if not isinstance(s,str) or not s.endswith("Z"):
        raise ValueError("UTC_TIMESTAMP_REQUIRED")
    try:t=dt.datetime.fromisoformat(s.replace("Z","+00:00"))
    except ValueError:raise ValueError("INVALID_TIMESTAMP") from None
    if t.tzinfo is None or t.utcoffset()!=dt.timedelta():
        raise ValueError("TIMESTAMP_NOT_UTC")
    return t

def hash64(s):
    return isinstance(s,str) and bool(SHA64.fullmatch(s))

def frozen(protocol):
    if not isinstance(protocol,dict) or protocol.get("schema")!=PROTOCOL:
        raise ValueError("MISSING_OR_BAD_V07_PROTOCOL")
    if digest(protocol)!=LOCKED_PROTOCOL_SHA256:
        raise ValueError("CHANGED_FROZEN_PROTOCOL")
    if (protocol.get("automatic_promotion") is not False
        or protocol.get("research_only") is not True
        or protocol["governance"]["no_production_authority"] is not True):
        raise ValueError("SOURCE_POLICY_CHANGED")
    return True

def evaluate_trial(protocol,report):
    frozen(protocol)
    if not isinstance(report,dict) or report.get("schema")!=REPORT:
        raise ValueError("INVALID_TRIAL_REPORT")
    if report.get("report_sha256")!=digest({
        k:v for k,v in report.items() if k!="report_sha256"}):
        raise ValueError("UNSEALED_TRIAL_REPORT")
    if (report.get("protocol_sha256")!=digest(protocol)
        or report.get("research_gate")!="RESEARCH_METRIC_PASS_REQUIRES_EXTERNAL_AUTHENTICATION"
        or report.get("production_authority") is not False
        or report.get("offspring_activated") is not False
        or report.get("source_claims_not_authenticated") is not True
        or report.get("independent_external_replication") is not False):
        raise ValueError("PREMATURE_OR_FORGED_TRIAL_AUTHORITY")
    arms={x["id"]:x for x in protocol["arms"]}
    arm=arms.get(report.get("candidate_id"))
    if arm is None or report.get("source_kind")!=arm["source_kind"]:
        raise ValueError("UNFROZEN_CANDIDATE")
    if not hash64(report.get("rows_sha256")):
        raise ValueError("MISSING_RAW_SOURCE_FINGERPRINT")
    if not isinstance(report.get("cohorts"),dict) or (
        set(report["cohorts"])!={x["id"] for x in protocol["cohorts"]}):
        raise ValueError("INCOMPLETE_FUTURE_COHORTS")
    thresholds=protocol["thresholds"]
    for c in report["cohorts"].values():
        if (not isinstance(c,dict)
            or type(c.get("n")) is not int
            or c["n"]<thresholds["min_cases_each_cohort"]
            or any(type(c.get(k)) is not int or c[k]<0 for k in
                   ("correct_baseline","correct_candidate","wins_candidate",
                    "wins_baseline","candidate_false_reject_healthy"))
            or c["correct_baseline"]>c["n"] or c["correct_candidate"]>c["n"]
            or c["wins_candidate"]+c["wins_baseline"]>c["n"]
            or c["candidate_false_reject_healthy"]!=0):
            raise ValueError("TRIAL_COUNT_OR_HEALTHY_SAFETY_FAILURE")
        delta=(c["correct_candidate"]-c["correct_baseline"])/c["n"]
        if (type(c.get("absolute_accuracy_gain")) not in (float,int)
            or not math.isfinite(c["absolute_accuracy_gain"])
            or abs(c["absolute_accuracy_gain"]-delta)>0.000002
            or delta<thresholds["min_absolute_accuracy_gain"]):
            raise ValueError("NO_REPLICATED_PAIRED_GAIN")
        p=c.get("mcnemar_one_sided_p")
        if type(p) not in (int,float) or not math.isfinite(p) or p<0:
            raise ValueError("INVALID_STATISTICAL_EVIDENCE")
        # Recalculate the paired exact one-sided McNemar p from integer
        # counts, never trust the candidate's claimed p-value.
        n=c["wins_candidate"]+c["wins_baseline"]
        if not n or c["wins_candidate"]<=c["wins_baseline"]:
            p_exact=1.0
        else:
            p_exact=sum(math.comb(n,k) for k in range(
                c["wins_candidate"],n+1))/(2**n)
        if abs(p-p_exact)>2e-8 or p_exact>thresholds["max_one_sided_mcnemar_p_each_cohort"]:
            raise ValueError("NO_SIGNIFICANT_PAIRED_REPLICATION")
        if c.get("internal_scientific_gate")!="METRIC_PASS_UNAUTHENTICATED":
            raise ValueError("INTERNAL_COHORT_HOLD")
    return arm

def validate_context(context,report):
    if not isinstance(context,dict) or set(context)!={
        "target_repo","baseline_commit_sha1","candidate_commit_sha1",
        "baseline_checkpoint_sha256","candidate_checkpoint_sha256",
        "rollback_checkpoint_sha256","rollback_drill_sha256",
        "canary_receipt_sha256","canary_status","rollback_status",
        "checkpoint_preflight_status","heldout_raw_rows_sha256",
        "evaluation_report_sha256","independent_verifier_organization",
        "request_kind"}:
        raise ValueError("ADMISSION_CONTEXT_SHAPE")
    if (context["target_repo"]!=TARGET_REPO
        or context["request_kind"]!="HUMAN_REVIEW_ONLY"
        or context["canary_status"]!="PASS"
        or context["rollback_status"]!="PASS"
        or context["checkpoint_preflight_status"]!="PASS_NO_DESERIALIZATION"
        or not isinstance(context["independent_verifier_organization"],str)
        or not 5<=len(context["independent_verifier_organization"])<=100
        or context["evaluation_report_sha256"]!=report["report_sha256"]
        or context["heldout_raw_rows_sha256"]!=report["rows_sha256"]
        or context["rollback_checkpoint_sha256"]!=context["baseline_checkpoint_sha256"]):
        raise ValueError("ADMISSION_PREREQUISITE_MISSING")
    if any(not hash64(context[k]) for k in (
        "baseline_checkpoint_sha256","candidate_checkpoint_sha256",
        "rollback_checkpoint_sha256","rollback_drill_sha256",
        "canary_receipt_sha256","heldout_raw_rows_sha256",
        "evaluation_report_sha256")):
        raise ValueError("ADMISSION_SOURCE_HASH_MISSING")
    if any(not isinstance(context[k],str) or not SHA40.fullmatch(context[k]) for k in
           ("baseline_commit_sha1","candidate_commit_sha1")):
        raise ValueError("ADMISSION_COMMIT_UNPINNED")
    if context["candidate_checkpoint_sha256"]==context["baseline_checkpoint_sha256"]:
        raise ValueError("ADMISSION_NO_NEW_MODEL")
    return True

def verify_signature(body,signature,*,pinned_key,identity,role):
    if not isinstance(body,dict) or set(body)!={
        "schema","role","identity","report_sha256","context_sha256",
        "attested_at","scope"}:
        raise ValueError("ATTESTATION_WRONG_SHAPE")
    if (body["schema"]!=ATTEST or body["role"]!=role
        or body["identity"]!=identity or role not in PERMITTED_ROLES
        or body["scope"]!="INDEPENDENT_REVIEW_NO_PRODUCTION_DISPATCH"
        or not hash64(body["report_sha256"])
        or not hash64(body["context_sha256"])):
        raise ValueError("ATTESTATION_AUTHORITY_MISMATCH")
    stamp(body["attested_at"])
    if (not isinstance(identity,str)
        or not re.fullmatch(r"[a-z][a-z0-9_-]{3,60}",identity)
        or not isinstance(pinned_key,str)
        or not KEY.fullmatch(pinned_key)
        or not isinstance(signature,str)
        or not 100<=len(signature)<=2000
        or "-----BEGIN SSH SIGNATURE-----" not in signature
        or "-----END SSH SIGNATURE-----" not in signature):
        raise ValueError("ATTESTATION_PROOF_OR_PIN_MISSING")
    with tempfile.TemporaryDirectory() as temp:
        allowed=Path(temp)/"allowedsigners"
        sigfile=Path(temp)/"proof.sig"
        allowed.write_text(identity+" "+pinned_key+"\n",encoding="utf-8")
        sigfile.write_text(signature,encoding="utf-8")
        try:
            result=subprocess.run(
                ["ssh-keygen","-Y","verify","-f",str(allowed),
                 "-I",identity,"-n",NAMESPACE,"-s",str(sigfile)],
                input=canonical(body),capture_output=True,check=False,timeout=10)
        except (OSError,subprocess.TimeoutExpired):
            raise ValueError("ATTESTATION_VERIFIER_UNAVAILABLE") from None
    if result.returncode:
        raise ValueError("ATTESTATION_INVALID_CRYPTOGRAPHY")
    return hashlib.sha256(pinned_key.encode()).hexdigest()

def review(protocol,report,context=None,attestations=None,pins=None):
    arm=evaluate_trial(protocol,report)
    if context is None:
        return {
            "schema":SCHEMA,"candidate_id":arm["id"],
            "review_gate":"HOLD_EXTERNAL_ATTESTATIONS_AND_SAFETY_PROOFS",
            "independently_verified":False,"production_authority":False,
            "checkpoint_swapped":False,"owner_approval_obtained":False,
        }
    validate_context(context,report)
    if attestations is None or pins is None:
        return {
            "schema":SCHEMA,"candidate_id":arm["id"],
            "review_gate":"HOLD_OUT_OF_BAND_TRUST_PINS_REQUIRED",
            "independently_verified":False,"production_authority":False,
            "checkpoint_swapped":False,"owner_approval_obtained":False,
        }
    if (not isinstance(attestations,dict) or set(attestations)!=set(PERMITTED_ROLES)
        or not isinstance(pins,dict) or set(pins)!=set(PERMITTED_ROLES)):
        raise ValueError("MISSING_REQUIRED_TWO_INDEPENDENT_ROLES")
    seen_keys=set();seen_ident=set()
    for role in PERMITTED_ROLES:
        proof=attestations[role]
        pin=pins[role]
        if (not isinstance(proof,dict) or set(proof)!={"body","signature"}
            or not isinstance(pin,dict) or set(pin)!={"identity","public_key"}):
            raise ValueError("INCOMPLETE_PINNED_EXTERNAL_REVIEWER")
        body=proof["body"]
        if (body.get("report_sha256")!=report["report_sha256"]
            or body.get("context_sha256")!=digest(context)):
            raise ValueError("SIGNATURE_BINDING_DOES_NOT_MATCH")
        pubsha=verify_signature(body,proof["signature"],
           pinned_key=pin["public_key"],identity=pin["identity"],role=role)
        if pubsha in seen_keys or pin["identity"] in seen_ident:
            raise ValueError("NOT_TWO_DISTINCT_TRUSTED_IDENTITIES")
        seen_keys.add(pubsha);seen_ident.add(pin["identity"])
    output={
        "schema":SCHEMA,"candidate_id":arm["id"],
        "review_gate":"CRYPTO_REVIEW_COMPLETE_OWNER_APPROVAL_STILL_REQUIRED",
        "independently_verified":False,
        "cryptographically_distinct_signers":2,
        "scientific_independence_needs_human_confirmation":True,
        "production_authority":False,"checkpoint_swapped":False,
        "owner_approval_obtained":False,
    }
    return output

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--protocol",default="research/essence/v10/locked_v07_protocol.json")
    p.add_argument("--trial",required=True)
    p.add_argument("--context")
    p.add_argument("--attestations")
    p.add_argument("--trust-pins")
    p.add_argument("--out",required=True)
    a=p.parse_args()
    result=review(load(a.protocol),load(a.trial),
        load(a.context) if a.context else None,
        load(a.attestations) if a.attestations else None,
        load(a.trust_pins) if a.trust_pins else None)
    o=Path(a.out)
    o.parent.mkdir(parents=True,exist_ok=True)
    with o.open("x",encoding="utf-8") as f:
        json.dump(result,f,sort_keys=True,indent=2);f.write("\n")
    print(json.dumps(result,sort_keys=True))
if __name__=="__main__":
    main()
