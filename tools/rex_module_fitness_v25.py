#!/usr/bin/env python3
"""JANUS ESSENCE v2.5: prospective second-generation Rex organ evaluation.

A ledger_trend descendant inherits ledger_health, which inherited
ledger_summary. New evaluation rows must have been ADDED by Git commits
strictly after the parent's first fitness receipt was committed.
This guards the prior v2.4 retrospective result from reuse as "new" evidence.

No model-weight improvement, arbitrary-source execution, automatic merge,
external-blind generalization or production authority is claimed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from tools import rex_module_fitness_v24 as prior
from tools import demiurge_rex as rex

SCHEMA = "janus.rex.prospective_lineage_fitness/2.5"
MIN_POSTBIRTH_ROWS = 12
MAX_POSTBIRTH_ROWS = 64


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True,
          separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args],
                            text=True, capture_output=True, timeout=20,
                            check=False)
    if result.returncode:
        raise ValueError("GIT_PROVENANCE_UNAVAILABLE")
    return result.stdout.strip()


def checked_health_ancestor(root, name, source, sha):
    spec, _, parent_sha = prior.validate_generated(
        root/"rex/candidates"/name,
        root/"rex/specs/generated"/f"{name}.json", "ledger_health")
    fitness_path = root/"rex/candidates"/name/"fitness.json"
    fitness = rex.load(fitness_path)
    seal = fitness.get("receipt_sha256")
    if (fitness.get("schema") != prior.SCHEMA or
        fitness.get("status") != "RESEARCH_FUNCTIONAL_GAIN" or
        fitness.get("new_functional_capability_proven") is not True or
        fitness.get("quality_on_external_future_tasks_proven") is not False or
        fitness.get("production_authority") is not False or
        fitness.get("candidate_source_sha256") != parent_sha or
        fitness.get("candidate_module") != name or
        fitness.get("ledger_family") != source or
        seal != digest({k:v for k,v in fitness.items()
                        if k != "receipt_sha256"}) or
        parent_sha != sha):
        raise ValueError("UNTRUSTED_HEALTH_FITNESS")
    grand_name = name.removesuffix("_ledger_health")+"_ledger_summary"
    grand, _, grand_sha = prior.validate_generated(
        root/"rex/candidates"/grand_name,
        root/"rex/specs/generated"/f"{grand_name}.json", "ledger_summary")
    if (fitness.get("parent_module") != grand_name or
        fitness.get("parent_source_sha256") != grand_sha):
        raise ValueError("BROKEN_THREE_GENERATION_ANCESTRY")
    admission = rex.load(root/"rex/admissions"/f"{name}.json")
    lifecycle = rex.load(root/"rex/lifecycle"/f"{name}.json")
    if (admission.get("state") != "ADMITTED_EXACT_SHA" or
        admission.get("source_sha256") != parent_sha or
        lifecycle.get("state") != "LIFECYCLE_ADMITTED_EXACT_SHA" or
        lifecycle.get("source_sha256") != parent_sha):
        raise ValueError("HEALTH_PARENT_NOT_ADMITTED")
    observed = (spec.get("nexus") or {}).get("input") or {}
    if observed.get("observed_path") != source:
        raise ValueError("HEALTH_PARENT_WRONG_DATA")
    return grand_sha, seal, fitness_path


def newly_added_rows(root, source, parent_fitness_path):
    rel = parent_fitness_path.relative_to(root).as_posix()
    commits = git(root, "log", "--format=%H", "--diff-filter=A",
                  "--", rel).splitlines()
    if len(commits) != 1 or len(commits[0]) != 40:
        raise ValueError("UNIQUE_HEALTH_BIRTH_COMMIT_REQUIRED")
    born = commits[0]
    changes = git(root, "diff", "--name-status", "--no-renames",
                  born, "HEAD", "--", source)
    paths=[]
    for row in changes.splitlines():
        fields = row.split("\t")
        if len(fields) != 2 or fields[0] != "A" or not fields[1].startswith(source+"/"):
            raise ValueError("NON_APPEND_ONLY_POST_BIRTH_HISTORY")
        paths.append(fields[1])
    if len(paths) < MIN_POSTBIRTH_ROWS:
        raise ValueError("HOLD_INSUFFICIENT_GIT_NEW_ROWS")
    if len(paths) > prior.MAX_LEDGER_RECORDS:
        raise ValueError("POSTBIRTH_LEDGER_TOO_LARGE")
    # Use commit history to order the newly seen files (not hash filenames).
    history = git(root,"log","--reverse","--format=__COMMIT__:%H",
                  "--name-only","--diff-filter=A",born+"..HEAD","--",source)
    seen, ordered = set(), []
    for line in history.splitlines():
        value=line.strip()
        if value in paths and value not in seen:
            seen.add(value)
            ordered.append(value)
    if set(paths) != seen:
        raise ValueError("INCOMPLETE_GIT_FIRST_SEEN_HISTORY")
    selected = (ordered[:MAX_POSTBIRTH_ROWS//2] +
                ordered[-MAX_POSTBIRTH_ROWS//2:] if
                len(ordered)>MAX_POSTBIRTH_ROWS else ordered)
    records=[]
    for name in selected:
        file=(root/name)
        if not file.is_file() or file.is_symlink() or file.stat().st_size>prior.MAX_RECORD_BYTES:
            raise ValueError("UNTRUSTED_NEW_EVIDENCE_FILE")
        payload=rex.load(file)
        if payload.get("authority_delta",0)!=0:
            raise ValueError("NONZERO_NEW_EVIDENCE_AUTHORITY")
        records.append((name, prior.sha(file.read_bytes()),
                        __import__("tools.demiurge_rex_need_discovery",fromlist=["compact_row"]).compact_row(payload)))
    return born, records, len(paths)


def expected_counts(rows):
    counts={}
    for row in rows:
        state=row.get("result_status",row.get("status",row.get("state","UNKNOWN")))
        if not isinstance(state,str):
            state="UNKNOWN"
        state=state[:64]
        counts[state]=counts.get(state,0)+1
    return counts


def evaluate(root, candidate_dir, candidate_spec, baseline_dir, baseline_spec):
    root=Path(root).resolve(strict=True)
    child, candidate, child_sha=prior.validate_generated(
        candidate_dir,candidate_spec,"ledger_trend")
    parent, previous, prev_sha=prior.validate_generated(
        baseline_dir,baseline_spec,"ledger_health")
    new_meta=(child.get("nexus") or {}).get("input") or {}
    prev_meta=(parent.get("nexus") or {}).get("input") or {}
    source=new_meta.get("observed_path")
    if (not isinstance(source,str) or not source.startswith(
        ("rex/lifecycle_runs/","rex/runs/")) or
        prev_meta.get("observed_path")!=source or
        new_meta.get("verified_parent_source_sha256")!=prev_sha or
        new_meta.get("verified_parent_module")!=parent.get("module_id")):
        raise ValueError("INVALID_GENERATION_2_PROVENANCE")
    grand_sha,parent_fitness,parent_path=checked_health_ancestor(
        root,parent["module_id"],source,prev_sha)
    if new_meta.get("verified_parent_fitness_sha256")!=parent_fitness:
        raise ValueError("PARENT_FITNESS_ANCHOR_MISMATCH")
    born,records,count=newly_added_rows(root,source,parent_path)
    if len(records) < MIN_POSTBIRTH_ROWS or len(set(
        status for row in records for status in expected_counts([row[2]])) ) < 2:
        raise ValueError("HOLD_LOW_INFORMATION_NEW_ROWS")
    chunks=(records[::2],records[1::2])
    reviews=[]
    for sample in chunks:
        rows=[r[2] for r in sample]
        baseline=prior.isolate_run(previous,rows)
        descendant=prior.isolate_run(candidate,rows)
        original_fields=("status","row_count","dict_row_count","keys",
                         "status_counts","authority_delta")
        preserved=all(baseline.get(k)==descendant.get(k)
                      for k in original_fields)
        middle=len(rows)//2
        older=expected_counts(rows[:middle])
        newer=expected_counts(rows[middle:])
        delta={k:newer.get(k,0)-older.get(k,0)
               for k in sorted(set(older)|set(newer))}
        added=(not any(k in baseline for k in
               ("prior_status_counts","recent_status_counts","status_delta")) and
               descendant.get("prior_status_counts")==older and
               descendant.get("recent_status_counts")==newer and
               descendant.get("status_delta")==delta)
        reviews.append({"rows":len(rows),"inherited_health_abi_preserved":preserved,
                        "new_status_trend_correct":added})
    passed=all(row["inherited_health_abi_preserved"] and row["new_status_trend_correct"]
               for row in reviews)
    document={
        "schema":SCHEMA,
        "status":"GIT_POSTBIRTH_FUNCTIONAL_GAIN" if passed else "HOLD_NO_GAIN",
        "chain":["ledger_summary","ledger_health","ledger_trend"],
        "generation_depth":2,
        "ancestor_source_sha256":grand_sha,
        "parent_source_sha256":prev_sha,
        "child_source_sha256":child_sha,
        "parent_fitness_receipt_sha256":parent_fitness,
        "parent_birth_commit":born,
        "eval_commit":git(root,"rev-parse","HEAD"),
        "source_family":source,
        "git_added_records_since_parent_birth":count,
        "used_postbirth_rows":len(records),
        "postbirth_sample_sha256":digest([(r[0],r[1]) for r in records]),
        "reviews":reviews,
        "functional_gain_verified":passed,
        "independent_external_future_examination":False,
        "independently_proven_neural_weight_gain":False,
        "automatic_merge":False,
        "production_model_promotion":False,
        "authority_delta":0
    }
    document["receipt_sha256"]=digest(document)
    return document


def main():
    p=argparse.ArgumentParser()
    for field in ("root","candidate-dir","candidate-spec",
                  "baseline-dir","baseline-spec","out"):
        p.add_argument("--"+field,required=True)
    a=p.parse_args()
    result=evaluate(a.root,a.candidate_dir,a.candidate_spec,
                    a.baseline_dir,a.baseline_spec)
    output=Path(a.out)
    if output.exists():
        raise FileExistsError("IMMUTABLE_LINEAGE_FITNESS")
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":result["status"],
        "postbirth_records":result["used_postbirth_rows"],
        "production_authority":False}))
    if result["status"]!="GIT_POSTBIRTH_FUNCTIONAL_GAIN":
        raise SystemExit(3)

if __name__=="__main__":
    main()
