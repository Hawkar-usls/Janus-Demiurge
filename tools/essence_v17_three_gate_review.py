#!/usr/bin/env python3
"""ESSENCE v1.7: fail-closed human-review eligibility for a REAL JANUS model change.

No credentials, trust roots, blinded datasets, real service canary or deployment
connection are bundled here. Only separately supplied, cryptographically signed
evidence from out-of-band actors can reach review eligibility. Even then this
tool NEVER modifies weights, deploys code, or authorizes production changes.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import random
import re
import statistics
import subprocess
import tempfile

SCHEMA="janus.essence.real_model_three_gate_review/1.7"
ATTEST_SCHEMA="janus.essence.real_model_role_attestation/1.7"
OUTPUT_SCHEMA="janus.essence.real_model_admission_verdict/1.7"
NAMESPACE="janus-essence-v17-external-review"
TARGET_REPO="Hawkar-usls/Janus-Demiurge"
CANDIDATE="native_dynamic_int8_ffn_mask7"
ORIGINAL_SHA="fc767adb812ac3bea54c44cbccfa9680941f95e2c8a77120559b41da044d9463"
SELECTED_SOURCE_COMMIT="edc4f104c4da43411d3987616c8de2d1cbd3a99d"
FROZEN_MODEL_BLOB="88cad884b437dd0ab655d913b1c83d6a6d669735"
SELECTED_LAYERS=("blocks.layers.0.linear1","blocks.layers.0.linear2","blocks.layers.1.linear1")
ROLES=("holdout_custodian","external_evaluator","target_hardware_operator","deployment_operator")
HEX64=re.compile(r"[0-9a-f]{64}\Z")
SHA1=re.compile(r"[0-9a-f]{40}\Z")
IDENTITY=re.compile(r"[a-z][a-z0-9_-]{3,60}\Z")
PUBKEY=re.compile(r"ssh-ed25519 [A-Za-z0-9+/]+={0,2}\Z")
MAX_FILE=250_000
MIN_DOCUMENTS=100
MIN_TOP1=.97
MAX_RELATIVE_LOSS=.005
MAX_SLOWDOWN=.05
MAX_RSS_INCREASE=.05
MIN_STORAGE_SAVING=.25

def canonical(data):
    return json.dumps(data,sort_keys=True,ensure_ascii=False,
                      separators=(",",":"),allow_nan=False).encode("utf-8")

def sha(data):
    return hashlib.sha256(canonical(data)).hexdigest()

def load(path):
    p=Path(path)
    if p.is_symlink() or not p.is_file() or not 2<=p.stat().st_size<=MAX_FILE:
        raise ValueError("UNSAFE_EVIDENCE_INPUT")
    return json.loads(p.read_text(encoding="utf-8"),
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))

def hex64(s):
    return isinstance(s,str) and HEX64.fullmatch(s) is not None

def finite_pos(v):
    return type(v) in (int,float) and math.isfinite(v) and v>0

def fixed_candidate(obj):
    if not isinstance(obj,dict) or set(obj)!={"repository","candidate_id",
           "selected_model_commit","source_checkpoint_sha256",
           "source_checkpoint_git_blob","quantized_layer_names","production_change_requested"}:
        raise ValueError("BAD_CANDIDATE_CONTRACT")
    if (obj["repository"]!=TARGET_REPO or obj["candidate_id"]!=CANDIDATE
        or obj["selected_model_commit"]!=SELECTED_SOURCE_COMMIT
        or obj["source_checkpoint_sha256"]!=ORIGINAL_SHA
        or obj["source_checkpoint_git_blob"]!=FROZEN_MODEL_BLOB
        or obj["quantized_layer_names"]!=list(SELECTED_LAYERS)
        or obj["production_change_requested"] is not False):
        raise ValueError("UNPINNED_OR_PRODUCTION_CANDIDATE")
    return True

def holdout_results(data):
    """Document-cluster bootstrap; not a substitute for independent custody."""
    if (not isinstance(data,dict) or data.get("source_class")!="INDEPENDENT_UNSEEN_PRIVATE_CUSTODIAN"
        or data.get("certified_not_used_for_training") is not True
        or data.get("certified_not_seen_during_candidate_selection") is not True
        or not hex64(data.get("raw_holdout_sha256"))
        or not hex64(data.get("scoring_code_sha256"))
        or not isinstance(data.get("cohorts"),list) or len(data["cohorts"])!=2):
        raise ValueError("UNAUTHENTICATED_BLIND_HOLDOUT_DESCRIPTOR")
    out=[];all_ids=set()
    for cohort in data["cohorts"]:
        name=cohort.get("name") if isinstance(cohort,dict) else None
        docs=cohort.get("documents") if isinstance(cohort,dict) else None
        if not isinstance(name,str) or not re.fullmatch(r"[a-z][a-z_0-9]{3,40}",name):
            raise ValueError("BAD_COHORT_NAME")
        if not isinstance(docs,list) or len(docs)<MIN_DOCUMENTS or len(docs)>5000:
            raise ValueError("INSUFFICIENT_INDEPENDENT_DOCUMENTS")
        rates=[];weights=[];base_ce=[];cand_ce=[]
        for d in docs:
            if not isinstance(d,dict) or set(d)!={"document_sha256","n_tokens",
                                                    "argmax_matches","baseline_ce","candidate_ce"}:
                raise ValueError("MALFORMED_DOCUMENT_RECORD")
            ident=d["document_sha256"];n=d["n_tokens"];k=d["argmax_matches"]
            if (not hex64(ident) or ident in all_ids or type(n) is not int
                or not 8<=n<=4096 or type(k) is not int or not 0<=k<=n
                or not finite_pos(d["baseline_ce"]) or not finite_pos(d["candidate_ce"])):
                raise ValueError("DUPLICATE_OR_INVALID_BLIND_DOCUMENT")
            all_ids.add(ident)
            rates.append(k/n);weights.append(n)
            base_ce.append(float(d["baseline_ce"]));cand_ce.append(float(d["candidate_ce"]))
        # Resample whole documents, not individual correlated tokens, and
        # calculate *token-weighted* Top-1 in each document-cluster bootstrap.
        seed=int(hashlib.sha256((name+data["raw_holdout_sha256"]).encode()).hexdigest()[:16],16)
        rnd=random.Random(seed)
        size=len(docs)
        draws=[]
        for _ in range(1000):
            sample=[rnd.randrange(size) for _ in range(size)]
            total=sum(weights[j] for j in sample)
            matches=sum(round(rates[j]*weights[j]) for j in sample)
            draws.append(matches/total)
        draws.sort()
        low=draws[24]  # two-sided ~95% conservative lower percentile
        empirical=sum(round(r*w) for r,w in zip(rates,weights))/sum(weights)
        b=sum(base_ce)/size
        c=sum(cand_ce)/size
        regression=c/b-1
        if low<MIN_TOP1 or regression>MAX_RELATIVE_LOSS:
            raise ValueError("INDEPENDENT_HOLDOUT_QUALITY_HOLD")
        out.append({"cohort":name,"documents":size,"total_tokens":sum(weights),
                    "empirical_top1":round(empirical,8),
                    "document_cluster_bootstrap_lower":round(low,8),
                    "relative_mean_ce_change":round(regression,8)})
    if len({r["cohort"] for r in out})!=2:
        raise ValueError("DUPLICATE_HOLDOUT_COHORT")
    return out

def hardware_results(data):
    if (not isinstance(data,dict) or data.get("source_class")!="REAL_TARGET_HARDWARE"
        or data.get("actual_native_int8_operator_count")!=3
        or data.get("independent_process_per_run") is not True
        or data.get("hardware_matched_to_target_service") is not True
        or data.get("allocator_confounded") is not False
        or not hex64(data.get("hardware_profile_sha256"))
        or not hex64(data.get("candidate_artifact_sha256"))
        or not isinstance(data.get("target_id"),str) or not 8<=len(data["target_id"])<=100):
        raise ValueError("TARGET_HARDWARE_PROOF_MISSING")
    runs=data.get("runs")
    if not isinstance(runs,list) or len(runs)<5 or len(runs)>100:
        raise ValueError("NOT_ENOUGH_TARGET_HARDWARE_REPETITIONS")
    baseline=[];candidate=[];b_rss=[];c_rss=[]
    devices=set()
    for r in runs:
        if (not isinstance(r,dict) or
            set(r)!={"device_id","baseline_p95_ms","candidate_p95_ms",
                     "baseline_rss_bytes","candidate_rss_bytes","baseline_median_ms",
                     "candidate_median_ms","run_receipt_sha256"} or
            not hex64(r["run_receipt_sha256"]) or
            r["device_id"]!=data["target_id"] or
            any(not finite_pos(r[k]) for k in
                ("baseline_p95_ms","candidate_p95_ms","baseline_rss_bytes",
                 "candidate_rss_bytes","baseline_median_ms","candidate_median_ms")) or
            r["baseline_p95_ms"]<r["baseline_median_ms"] or
            r["candidate_p95_ms"]<r["candidate_median_ms"]):
            raise ValueError("BAD_HARDWARE_RUN")
        if (r["candidate_median_ms"]>r["baseline_median_ms"]*(1+MAX_SLOWDOWN)
            or r["candidate_p95_ms"]>r["baseline_p95_ms"]*1.10
            or r["candidate_rss_bytes"]>r["baseline_rss_bytes"]*(1+MAX_RSS_INCREASE)):
            raise ValueError("TARGET_HARDWARE_PER_RUN_REGRESSION")
        baseline.append(r["baseline_median_ms"]);candidate.append(r["candidate_median_ms"])
        b_rss.append(r["baseline_rss_bytes"]);c_rss.append(r["candidate_rss_bytes"])
        devices.add(r["run_receipt_sha256"])
    if len(devices)!=len(runs):
        raise ValueError("REPEATED_HARDWARE_RECEIPTS")
    bsize=data.get("baseline_serialized_bytes");csize=data.get("candidate_serialized_bytes")
    if (type(bsize) is not int or type(csize) is not int or bsize<=0 or csize<=0
        or csize>bsize*(1-MIN_STORAGE_SAVING)):
        raise ValueError("TARGET_STORAGE_BENEFIT_MISSING")
    return {"target_id":data["target_id"],"paired_runs":len(runs),
            "median_baseline_ms":round(statistics.median(baseline),5),
            "median_candidate_ms":round(statistics.median(candidate),5),
            "max_candidate_rss_bytes":max(c_rss),
            "minimum_storage_saving_fraction":round(1-csize/bsize,7),
            "hardware_profile_sha256":data["hardware_profile_sha256"]}

def rollback_results(data,hardware):
    required={"source_class","target_id","service_id","service_revision_before",
       "service_revision_canary","service_revision_after","baseline_checkpoint_sha256",
       "candidate_artifact_sha256","active_checkpoint_sha256_after",
       "monitoring_source_sha256","deployment_proof_sha256","rollback_proof_sha256",
       "real_canary_requests","real_rollback_triggered","healthy_after_revert",
       "healthcheck_baseline_response_sha256","healthcheck_postrollback_response_sha256",
       "candidate_was_live_for_canary","rollback_was_on_actual_service"}
    if not isinstance(data,dict) or set(data)!=required:
        raise ValueError("REAL_SERVICE_PROOF_FIELDS_MISSING")
    if (data["source_class"]!="REAL_DEPLOYED_MODEL_SERVICE"
        or data["target_id"]!=hardware["target_id"]
        or not isinstance(data["service_id"],str) or len(data["service_id"])<8
        or data["baseline_checkpoint_sha256"]!=ORIGINAL_SHA
        or data["active_checkpoint_sha256_after"]!=ORIGINAL_SHA
        or data["candidate_artifact_sha256"]!=hardware["candidate_artifact_sha256"]
            if "candidate_artifact_sha256" in hardware else False):
        raise ValueError("INCONSISTENT_REAL_SERVICE_IDENTITY")
    if (any(not hex64(data[k]) for k in
             ("candidate_artifact_sha256","monitoring_source_sha256","deployment_proof_sha256",
              "rollback_proof_sha256","healthcheck_baseline_response_sha256",
              "healthcheck_postrollback_response_sha256"))
        or data["healthcheck_baseline_response_sha256"]!=data["healthcheck_postrollback_response_sha256"]
        or type(data["real_canary_requests"]) is not int or data["real_canary_requests"]<100
        or any(data[k] is not True for k in
               ("real_rollback_triggered","healthy_after_revert","candidate_was_live_for_canary",
                "rollback_was_on_actual_service"))
        or len({data["service_revision_before"],data["service_revision_canary"],
                data["service_revision_after"]})!=3):
        raise ValueError("UNPROVEN_LIVE_CANARY_OR_ROLLBACK")
    return {"service_id":data["service_id"],"canary_requests":data["real_canary_requests"],
            "rollback_proof_sha256":data["rollback_proof_sha256"],
            "rollback_checkpoint_restored":True}

def verify_signatures(evidence,trust):
    if not isinstance(evidence,dict) or set(evidence.get("attestations",{}))!=set(ROLES):
        raise ValueError("FOUR_EXTERNAL_ATTESTATIONS_REQUIRED")
    if not isinstance(trust,dict) or set(trust)!=set(ROLES):
        raise ValueError("FOUR_OWNER_PINNED_TRUST_ROOTS_REQUIRED")
    key_fingerprints=set();identities=set();orgs={}
    part={"holdout_custodian":"holdout","external_evaluator":"holdout",
          "target_hardware_operator":"hardware","deployment_operator":"rollback"}
    for role in ROLES:
        pin=trust[role];entry=evidence["attestations"][role]
        if (not isinstance(pin,dict) or set(pin)!={"identity","public_key","organization"}
            or not isinstance(entry,dict) or set(entry)!={"body","signature"}):
            raise ValueError("INVALID_SIGNER_PIN_OR_ATTESTATION")
        identity=pin["identity"];key=pin["public_key"];organization=pin["organization"]
        if (not isinstance(identity,str) or IDENTITY.fullmatch(identity) is None
            or not isinstance(key,str) or PUBKEY.fullmatch(key) is None
            or not isinstance(organization,str) or not 5<=len(organization)<=100):
            raise ValueError("SIGNER_PIN_INVALID")
        body=entry["body"];sig=entry["signature"]
        if (not isinstance(body,dict) or set(body)!={"schema","role","candidate_id",
               "payload_sha256","signed_at_utc","scope"} or
            body["schema"]!=ATTEST_SCHEMA or body["role"]!=role
            or body["candidate_id"]!=CANDIDATE or
            body["payload_sha256"]!=sha(evidence[part[role]])
            or body["scope"]!="INDEPENDENT_REVIEW_NO_MODEL_DISPATCH"):
            raise ValueError("ATTESTATION_PAYLOAD_BINDING_INVALID")
        stamp=body["signed_at_utc"]
        if not isinstance(stamp,str) or not stamp.endswith("Z"):
            raise ValueError("INVALID_ATTESTATION_TIMESTAMP")
        try:dt.datetime.fromisoformat(stamp.replace("Z","+00:00"))
        except ValueError:raise ValueError("INVALID_ATTESTATION_TIMESTAMP") from None
        if not isinstance(sig,str) or not 100<=len(sig)<=2000 or "BEGIN SSH SIGNATURE" not in sig:
            raise ValueError("REAL_CRYPTOGRAPHIC_SIGNATURE_REQUIRED")
        # The trust file is out-of-band owner provisioned, NOT a candidate repo file.
        with tempfile.TemporaryDirectory() as td:
            allowed=Path(td)/"trusted";signature=Path(td)/"attestation.sig"
            allowed.write_text(identity+" "+key+"\n",encoding="utf8")
            signature.write_text(sig,encoding="utf8")
            try:
                verify=subprocess.run(["ssh-keygen","-Y","verify","-f",str(allowed),
                                       "-I",identity,"-n",NAMESPACE,"-s",str(signature)],
                                      input=canonical(body),capture_output=True,
                                      check=False,timeout=8)
            except (OSError,subprocess.TimeoutExpired):
                raise ValueError("EXTERNAL_CRYPTO_VERIFIER_MISSING") from None
            if verify.returncode:
                raise ValueError("INVALID_OUT_OF_BAND_SIGNATURE")
        fingerprint=hashlib.sha256(key.encode()).hexdigest()
        if fingerprint in key_fingerprints or identity in identities:
            raise ValueError("SIGNING_KEYS_NOT_INDEPENDENT")
        key_fingerprints.add(fingerprint);identities.add(identity)
        orgs[role]=organization
    if orgs["holdout_custodian"]==orgs["external_evaluator"]:
        raise ValueError("HOLDOUT_REVIEWER_AND_CUSTODIAN_NOT_SEPARATE_ORGS")
    return {"cryptographic_attesters":4,
            "external_organizations":len(set(orgs.values())),
            "trust_roots":"OUT_OF_BAND_OWNER_PINNED_NOT_SOURCE_CONTROL"}

def review(evidence=None,trust=None):
    hold={"schema":OUTPUT_SCHEMA,"candidate_id":CANDIDATE,"review_gate":
         "HOLD_INDEPENDENT_BLIND_TARGET_HARDWARE_AND_REAL_SERVICE_ROLLBACK",
          "production_authority":False,"automatic_promotion":False,
          "live_weights_modified":False,"owner_approved":False}
    if evidence is None or trust is None:
        hold["reason"]="REAL_OUT_OF_BAND_SIGNED_PROOFS_AND_OWNER_TRUST_PINS_NOT_PROVIDED"
        return hold
    if not isinstance(evidence,dict) or set(evidence)!={"schema","candidate",
              "holdout","hardware","rollback","attestations"} or evidence["schema"]!=SCHEMA:
        raise ValueError("V17_BAD_BUNDLE")
    fixed_candidate(evidence["candidate"])
    # Strictly verify the measured facts before accepting assertions by signers.
    blinded=holdout_results(evidence["holdout"])
    hardware=hardware_results(evidence["hardware"])
    # candidate artifact SHA must bind the exact trial to deployed canary
    hardware["candidate_artifact_sha256"]=evidence["hardware"]["candidate_artifact_sha256"]
    rollback=rollback_results(evidence["rollback"],hardware)
    attest=verify_signatures(evidence,trust)
    hold.update({"review_gate":"REVIEW_EVIDENCE_CRYPTO_VERIFIED_OWNER_APPROVAL_STILL_REQUIRED",
                 "holdout":blinded,"hardware":hardware,"service_revert":rollback,
                 "attestation":attest,
                 "reason":"THIS_IS_REVIEW_ELIGIBILITY_NOT_PERMISSION_TO_DEPLOY"})
    return hold

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence")
    p.add_argument("--owner-trust-file")
    p.add_argument("--out",default="runtime/essence_v17/model_admission.json")
    args=p.parse_args()
    if bool(args.evidence)!=bool(args.owner_trust_file):
        raise SystemExit("EVIDENCE_AND_OWNER_PINS_MUST_BE_PROVIDED_TOGETHER")
    result=review(load(args.evidence) if args.evidence else None,
                  load(args.owner_trust_file) if args.owner_trust_file else None)
    path=Path(args.out)
    if path.exists():raise FileExistsError("IMMUTABLE_REVIEW_RECEIPT")
    path.parent.mkdir(parents=True,exist_ok=True)
    result["receipt_sha256"]=sha(result)
    path.write_text(json.dumps(result,sort_keys=True,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"gate":result["review_gate"],"authority":False,
                      "receipt_sha256":result["receipt_sha256"]},sort_keys=True))

if __name__=="__main__":main()
