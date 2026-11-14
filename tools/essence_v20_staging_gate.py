#!/usr/bin/env python3
"""Stage only genuinely fresh, CI-verified cross-run research descendants.

No production endpoint is accepted. The only service instantiated by this
module is localhost HTTP, destroyed at the end of the job. It exercises real
PyTorch inference, 120 real localhost requests, injected fault, automatic
same-process rollback, original weight-SHA restoration and healthcheck.
A historical public CI split is NOT an independent external blind evaluation.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

from tools import essence_v19_gradirnya as e
from tools import essence_v19_http_canary as c

SCHEMA="janus.essence.staged_cross_run_successor/2.0"
CHILD=re.compile(r"^essence-v20-offspring-([0-5])-[1-9][0-9]*$")

def eligible(verdict,lineage,validation):
    if (not isinstance(verdict,dict) or not isinstance(lineage,dict)
        or verdict.get("receipt_sha256")!=e.seal({k:v for k,v in verdict.items() if k!="receipt_sha256"})
        or lineage.get("receipt_sha256")!=e.seal({k:v for k,v in lineage.items() if k!="receipt_sha256"})
        or lineage.get("schema")!=e.LINEAGE
        or verdict.get("schema")!="janus.essence.gradirnya_verifier/1.9"
        or lineage.get("production_authority") is not False
        or verdict.get("automatic_production_promotion") is not False
        or verdict.get("research_artifact_only") is not True
        or verdict.get("externally_custodied_test") is not False
        or verdict.get("lineage_sha256")!=lineage["receipt_sha256"]
        or verdict.get("source_commit")!=lineage.get("source_commit")
        or verdict.get("cell")!=lineage.get("cell")
        or verdict.get("holdout_sha256")!=lineage.get("holdout_sha256")):
        raise ValueError("UNTRUSTED_NEW_SUCCESSOR_RESEARCH_RECEIPTS")
    if (not isinstance(validation,dict) or validation.get("packet_sha256")!=lineage.get("validation_sha256")
        or validation.get("source_commit")!=lineage.get("source_commit")
        or validation.get("dataset_sha256")!=lineage.get("dataset_sha256")):
        raise ValueError("UNTRUSTED_CANARY_VALIDATION_PACKET")
    e.check_packet(validation,"validation",lineage["source_commit"],lineage["dataset_sha256"])
    ancestors=lineage.get("cross_run_inheritance")
    if ancestors is not None:
        if (not isinstance(ancestors,dict)
            or ancestors.get("parent_weights_sha256")!=lineage.get("initial_weights_sha256")
            or type(ancestors.get("ancestry_depth")) is not int
            or not 1<=ancestors["ancestry_depth"]<=12):
            raise ValueError("CROSS_RUN_STARTING_WEIGHTS_NOT_PINNED")
    if (verdict.get("gate")!="RESEARCH_HISTORICAL_DATE_HOLDOUT_GAIN"
        or verdict.get("diversity_gate") is not True
        or verdict.get("heldout_represented_classes",0)<3
        or verdict.get("heldout_majority_fraction",2)>.85
        or verdict.get("nll_gain_vs_prior",-1)<.02
        or verdict.get("accuracy_gain_vs_prior",0)<=0
        or lineage.get("accepted_generations",0)<1
        or ancestors is None):
        return False
    return True

def stage(children,verdicts,validation,out):
    out=Path(out)
    if out.exists():raise FileExistsError("STAGING_ARCHIVE_IMMUTABLE")
    packet=e.read_json(validation)
    collected=[];held=[]
    seen=set()
    for folder in sorted(Path(children).glob("essence-v20-offspring-*")):
        if not folder.is_dir():continue
        match=CHILD.fullmatch(folder.name)
        if not match:raise ValueError("UNTRUSTED_CHILD_ARTIFACT_NAME")
        cell=int(match.group(1))
        if cell in seen:raise ValueError("DUPLICATE_CANARY_CELL")
        seen.add(cell)
        verdict_path=Path(verdicts)/f"cell-{cell}.json"
        lineage_path=folder/"lineage.json"
        weights=folder/"offspring.pt"
        if not verdict_path.is_file() or not lineage_path.is_file() or not weights.is_file():
            raise ValueError("MISSING_CANARY_EVIDENCE")
        verdict=e.read_json(verdict_path)
        lineage=e.read_json(lineage_path)
        if not eligible(verdict,lineage,packet):
            held.append({"cell":cell,"reason":"NO_STRONG_NEW_HOLDOUT_GAIN"})
            continue
        receipt=c.exercise(weights,lineage,packet,
                           out/f"cell-{cell}.json",requests=120)
        if (receipt["baseline_weights_sha256"]!=lineage["initial_weights_sha256"]
            or receipt["candidate_weights_sha256"]!=lineage["final_weights_sha256"]
            or receipt["service_status_after"]["active_sha256"]!=lineage["initial_weights_sha256"]
            or receipt["rollbacks"]!=1
            or receipt["live_production_service_tested"] is not False):
            raise ValueError("NO_CONFIRMED_EPHEMERAL_SERVICE_RESTORATION")
        collected.append({"cell":cell,"receipt_sha256":receipt["receipt_sha256"],
                          "rollbacks":receipt["rollbacks"],
                          "canary_requests":receipt["actual_canary_requests"]})
    report={
        "schema":SCHEMA,"status":"RESEARCH_EPHEMERAL_ROLLBACKS_VERIFIED" if collected
                  else "HOLD_NO_ELIGIBLE_CROSS_RUN_SUCCESSOR",
        "checked_cells":len(seen),"staged":collected,"held":held,
        "staging_service_type":"EPHEMERAL_LOCALHOST_NOT_PRODUCTION",
        "independent_external_attestation":False,
        "target_hardware":False,"real_deployed_service_rollback":False,
        "production_authority":False,"automatic_service_promotion":False
    }
    report["receipt_sha256"]=e.seal(report)
    e.atomic_json(out/"index.json",report)
    return report

def cli():
    p=argparse.ArgumentParser()
    for v in ("children","verdicts","validation","out"):
        p.add_argument("--"+v,required=True)
    args=p.parse_args()
    report=stage(args.children,args.verdicts,args.validation,args.out)
    print(json.dumps({"status":report["status"],
                      "staged_cells":[x["cell"] for x in report["staged"]],
                      "held_cells":[x["cell"] for x in report["held"]],
                      "production_authority":False},sort_keys=True))

if __name__=="__main__":cli()
