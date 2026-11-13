#!/usr/bin/env python3
"""ESSENCE R2: dated GitHub Actions job-duration research, no production authority.

A completely read-only, CPU-only and deterministic predictor. Target is actual
job execution duration (completed_at-started_at), NOT queued/wall/run duration.
Labels and time features are causally constructed; train never receives holdout.
A "gene" here means a candidate temporal feature set, not inherited model
weights or permission to activate agents.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import urllib.request

OWNER = "Hawkar-usls"
REPOS = ("Janus-Demiurge", "Janus_Genesis", "janus-meta-registry")
SCHEMA = "janus.essence.duration_r2.v1"
LIMIT_RUNS = 100
EMBARGO = 5
MAX_JOB_SECONDS = 4 * 3600
GATE_MIN_ROWS = 60
SEED = 20261113

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")

def sha(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()

def save(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False,
                               allow_nan=False) + "\n", encoding="utf-8")

def load(path):
    p = Path(path)
    if p.stat().st_size > 8_000_000:
        raise ValueError("FILE_BOUND_EXCEEDED")
    obj = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("EXPECTED_OBJECT")
    return obj

def stamp(s):
    if not isinstance(s, str):
        raise ValueError("MISSING_TIMESTAMP")
    d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("NAIVE_TIMESTAMP")
    return d.astimezone(dt.timezone.utc)

def iso(d):
    return d.isoformat(timespec="seconds")

def api(path, token):
    if not path.startswith("/repos/" + OWNER + "/"):
        raise ValueError("UNTRUSTED_API_PATH")
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers={"User-Agent": "JANUS-ESSENCE-R2-Research/1",
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 **({"Authorization": "Bearer " + token} if token else {})})
    with urllib.request.urlopen(req, timeout=25) as resp:
        raw = resp.read(3_000_001)
    if len(raw) > 3_000_000:
        raise ValueError("API_RESPONSE_TOO_LARGE")
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("BAD_API_PAYLOAD")
    return obj, hashlib.sha256(raw).hexdigest()

def fetch_jobs(token):
    jobs, payload_sha = [], []
    for repo in REPOS:
        runs, h = api(f"/repos/{OWNER}/{repo}/actions/runs?"
                      f"per_page={LIMIT_RUNS}&status=completed", token)
        payload_sha.append([repo, "runs", h])
        entries = runs.get("workflow_runs")
        if not isinstance(entries, list):
            raise ValueError("RUNS_NOT_LIST")
        if len(entries) < 70:
            raise ValueError("TOO_FEW_RUNS_" + repo)
        for run in entries:
            run_id = run.get("id")
            if type(run_id) is not int or run.get("status") != "completed":
                continue
            obj, jsha = api(f"/repos/{OWNER}/{repo}/actions/runs/{run_id}/jobs?"
                            "per_page=100", token)
            payload_sha.append([repo, run_id, jsha])
            entries2 = obj.get("jobs")
            if (not isinstance(entries2, list) or obj.get("total_count", 0) > 100):
                raise ValueError("INCOMPLETE_JOB_PAGE")
            for j in entries2:
                if j.get("status") != "completed" or j.get("conclusion") not in ("success", "failure"):
                    continue
                job_id = j.get("id")
                if type(job_id) is not int:
                    raise ValueError("INVALID_JOB_ID")
                try:
                    start, end = stamp(j.get("started_at")), stamp(j.get("completed_at"))
                except (ValueError, TypeError):
                    continue
                duration = (end-start).total_seconds()
                if not (1 <= duration <= MAX_JOB_SECONDS):
                    continue
                job_name = j.get("name")
                if not isinstance(job_name, str) or not (0 < len(job_name) <= 250):
                    continue
                jobs.append({"repo": repo, "job_id": job_id, "run_id": run_id,
                             "workflow": str(run.get("name", ""))[:160],
                             "job": job_name, "started_at": iso(start),
                             "completed_at": iso(end), "duration_s": duration})
    return jobs, payload_sha

def past_values(rows, now, repo, job=None):
    # End BEFORE prediction time. Earlier start alone is insufficient:
    # concurrent jobs must never expose their future durations.
    vals = [r for r in rows if r["repo"] == repo
            and (job is None or (r["workflow"], r["job"]) == job)
            and stamp(r["completed_at"]) < now]
    vals.sort(key=lambda r: (r["completed_at"], r["job_id"]))
    return [v["duration_s"] for v in vals]

def features(jobs):
    ids = [r["job_id"] for r in jobs]
    if len(ids) != len(set(ids)):
        raise ValueError("DUPLICATE_JOB_ID")
    ordered = sorted(jobs, key=lambda r: (r["started_at"], r["job_id"]))
    out = []
    for j in ordered:
        start = stamp(j["started_at"])
        end = stamp(j["completed_at"])
        duration = (end-start).total_seconds()
        if not (1 <= duration <= MAX_JOB_SECONDS and duration == j["duration_s"]):
            raise ValueError("JOB_DURATION_INTEGRITY")
        prev_repo = past_values(ordered, start, j["repo"])
        prev_group = past_values(ordered, start, j["repo"], (j["workflow"], j["job"]))
        fallback = prev_repo or [60.0]
        chosen = prev_group or fallback
        hour = start.hour + start.minute / 60
        x = [
            1.0,
            math.log1p(statistics.median(fallback)),
            math.log1p(statistics.median(chosen)),
            math.log1p(chosen[-1]),
            math.log1p(max(chosen)),
            math.log1p(len(prev_group)),
            math.sin(2 * math.pi * hour / 24),
            math.cos(2 * math.pi * hour / 24),
            math.log1p(fallback[-1]),
        ]
        out.append({"repo": j["repo"], "job_id": j["job_id"],
                    "run_id": j["run_id"], "started_at": j["started_at"],
                    "completed_at": j["completed_at"],
                    "y_s": duration, "x": x,
                    "group": j["workflow"] + "/" + j["job"],
                    "prior_repo_count": len(prev_repo),
                    "prior_group_count": len(prev_group)})
    return out

def split(rows):
    parts = {k: [] for k in ("train", "validation", "holdout")}
    summaries = []
    for repo in REPOS:
        seq = [r for r in rows if r["repo"] == repo]
        if len(seq) < 75:
            raise ValueError("INSUFFICIENT_JOBS_" + repo)
        seq.sort(key=lambda r: (r["started_at"], r["job_id"]))
        n = len(seq)
        a, b = int(n * 0.62), int(n * 0.82)
        if not (0 < a+EMBARGO < b and b+EMBARGO < n):
            raise ValueError("INSUFFICIENT_EMBARGO_SPACE_" + repo)
        validation_start = stamp(seq[a + EMBARGO]["started_at"])
        holdout_start = stamp(seq[b + EMBARGO]["started_at"])
        purged = {"train": 0, "validation": 0}
        for i, r in enumerate(seq):
            finished = stamp(r["completed_at"])
            if i < a:
                # Late-finishing jobs are *not* training labels at the time
                # of the first validation prediction.
                if finished >= validation_start:
                    purged["train"] += 1
                    continue
                label = "train"
            elif i < a + EMBARGO: continue
            elif i < b:
                # Purge validation labels that finish after holdout starts.
                if finished >= holdout_start:
                    purged["validation"] += 1
                    continue
                label = "validation"
            elif i < b + EMBARGO: continue
            else: label = "holdout"
            parts[label].append(r)
        summaries.append({"repo": repo, "job_count": n,
                          "purged_late_finishes": purged,
                          "first_validation_start": iso(validation_start),
                          "first_holdout_start": iso(holdout_start),
                          "train_last_start": seq[a-1]["started_at"],
                          "validation_last_start": seq[b-1]["started_at"]})
    if min(len(x) for x in parts.values()) < 20:
        raise ValueError("INSUFFICIENT_SPLIT_ROWS")
    keys = [r["job_id"] for a in parts.values() for r in a]
    if len(keys) != len(set(keys)):
        raise ValueError("SPLIT_OVERLAP")
    return parts, summaries

def prepare(out_dir, token):
    jobs, raw_sha = fetch_jobs(token)
    rows = features(jobs)
    parts, summaries = split(rows)
    provenance = {"schema": SCHEMA,
                  "source": "PUBLIC_GITHUB_ACTIONS_JOB_START_AND_COMPLETION",
                  "target": "execution_seconds_excluding_queue",
                  "repositories": list(REPOS),
                  "embargo_jobs_per_repo": EMBARGO,
                  "raw_api_response_sha256_list_sha256": sha(raw_sha),
                  "collected_jobs_sha256": sha(jobs),
                  "feature_rows_sha256": sha(rows),
                  "summaries": summaries,
                  "sealed_holdout": True,
                  "not_meta_registry_weight_training": True}
    h = sha(provenance)
    for name, arr in parts.items():
        save(Path(out_dir) / (name + ".json"),
             {"schema": SCHEMA, "split": name, "provenance_sha256": h,
              "rows": arr})
    save(Path(out_dir) / "provenance.json", provenance)
    print(json.dumps({k: len(v) for k, v in parts.items()}, sort_keys=True))

def check_split(path, expected, provenance=None):
    d = load(path)
    if d.get("schema") != SCHEMA or d.get("split") != expected:
        raise ValueError("SCHEMA_OR_SPLIT_MISMATCH")
    if not isinstance(d.get("provenance_sha256"), str) or len(d["provenance_sha256"]) != 64:
        raise ValueError("BAD_PROVENANCE")
    if provenance is not None and d["provenance_sha256"] != provenance:
        raise ValueError("PROVENANCE_MISMATCH")
    rows = d.get("rows")
    if not isinstance(rows, list) or len(rows) < 20:
        raise ValueError("EMPTY_SPLIT")
    seen = set()
    for r in rows:
        if r.get("repo") not in REPOS or type(r.get("job_id")) is not int:
            raise ValueError("BAD_ROW_ID")
        if r["job_id"] in seen: raise ValueError("DUPLICATE_ROW")
        seen.add(r["job_id"])
        if (not isinstance(r.get("x"), list) or len(r["x"]) != 9 or
                any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in r["x"])):
            raise ValueError("BAD_FEATURE_VECTOR")
        if not isinstance(r.get("y_s"), (int, float)) or not (1 <= r["y_s"] <= MAX_JOB_SECONDS):
            raise ValueError("BAD_DURATION")
        if not stamp(r["completed_at"]) > stamp(r["started_at"]):
            raise ValueError("BAD_CHRONOLOGY")
    return d

def fit(rows, valid, dims, steps=800):
    # Deterministic bounded ridge regression on log(1+seconds), no packages.
    means = [statistics.mean(r["x"][k] for r in rows) for k in dims[1:]]
    sd = [max(0.05, statistics.pstdev(r["x"][k] for r in rows)) for k in dims[1:]]
    def vector(r):
        return [1.0] + [(r["x"][k]-m)/s for k, m, s in zip(dims[1:], means, sd)]
    xs = [vector(r) for r in rows]
    ys = [math.log1p(r["y_s"]) for r in rows]
    weights = [statistics.mean(ys)] + [0.0]*(len(dims)-1)
    best = None
    for step in range(steps):
        grads = [0.0]*len(dims)
        for x, y in zip(xs, ys):
            residual = sum(w*t for w,t in zip(weights,x))-y
            for k in range(len(dims)):
                grads[k] += 2.0*residual*x[k]/len(rows)
        for k in range(1,len(dims)):
            grads[k] += 0.025*weights[k]
        rate = 0.02
        weights = [max(-20.0,min(20.0,w-rate*g)) for w,g in zip(weights,grads)]
        if step % 10 == 0 or step == steps-1:
            model = {"dimensions": dims, "means": means, "stddev": sd, "weights": weights[:]}
            loss = statistics.mean(abs(predict(model,r)-r["y_s"]) for r in valid)
            if best is None or loss < best[0]:
                best = (loss, model)
    return best[1]

def predict(model, r):
    dims = model["dimensions"]
    vals = [1.0] + [(r["x"][k]-m)/s
                    for k,m,s in zip(dims[1:],model["means"],model["stddev"])]
    log_pred = sum(a*b for a,b in zip(model["weights"],vals))
    return max(1.0, min(MAX_JOB_SECONDS, math.expm1(max(0.0,min(12.0,log_pred)))))

def score(pred, actual):
    if len(pred) != len(actual) or not pred:
        raise ValueError("INVALID_METRIC")
    return {"mae_s": round(statistics.mean(abs(p-y) for p,y in zip(pred,actual)),5),
            "median_ae_s": round(statistics.median(abs(p-y) for p,y in zip(pred,actual)),5),
            "log_mae": round(statistics.mean(abs(math.log1p(p)-math.log1p(y))
                                              for p,y in zip(pred,actual)),6)}

def train(train_path, valid_path, out_dir):
    t = check_split(train_path,"train")
    v = check_split(valid_path,"validation",t["provenance_sha256"])
    a,b=t["rows"],v["rows"]
    if set(r["job_id"] for r in a) & set(r["job_id"] for r in b):
        raise ValueError("TRAIN_VALIDATION_LEAK")
    for repo in REPOS:
        train_ends=[stamp(r["completed_at"]) for r in a if r["repo"]==repo]
        valid_starts=[stamp(r["started_at"]) for r in b if r["repo"]==repo]
        if not train_ends or not valid_starts or max(train_ends)>=min(valid_starts):
            raise ValueError("TRAIN_VALIDATION_TEMPORAL_LEAK_" + repo)
    # Two genuine independently fitted read-only duration microcore candidates.
    plain = fit(a,b,[0,1])
    gene = fit(a,b,list(range(9)))
    ckpt={"schema":SCHEMA,"provenance_sha256":t["provenance_sha256"],
          "no_gene":plain,"temporal_gene":gene,
          "training_job_ids_sha256":sha(sorted(r["job_id"] for r in a)),
          "validation_job_ids_sha256":sha(sorted(r["job_id"] for r in b)),
          "train_median_duration_s":statistics.median(r["y_s"] for r in a),
          "train_repo_medians":{repo:statistics.median(
              r["y_s"] for r in a if r["repo"]==repo) for repo in REPOS},
          "last_validation_completion_by_repo":{
              repo:iso(max(stamp(r["completed_at"]) for r in b if r["repo"]==repo))
              for repo in REPOS},
          "holdout_seen_by_trainer":False,
          "production_authority":False,"seed":SEED}
    save(Path(out_dir)/"duration_microcores.json",ckpt)
    print(json.dumps({"trained":True,"train":len(a),"validation":len(b),
                      "holdout_seen":False},sort_keys=True))

def verify(hold_path, ckpt_path, out_path):
    ck = load(ckpt_path)
    if (ck.get("schema")!=SCHEMA or ck.get("holdout_seen_by_trainer") is not False
        or ck.get("production_authority") is not False):
        raise ValueError("CHECKPOINT_AUTHORITY")
    h = check_split(hold_path,"holdout",ck.get("provenance_sha256"))
    rows=h["rows"]
    for repo in REPOS:
        repo_rows=[r for r in rows if r["repo"]==repo]
        if not repo_rows:
            raise ValueError("MISSING_HOLDOUT_REPOSITORY_" + repo)
        if min(stamp(r["started_at"]) for r in repo_rows) <= stamp(
                ck["last_validation_completion_by_repo"][repo]):
            raise ValueError("VALIDATION_HOLDOUT_TEMPORAL_LEAK_" + repo)
    real=[r["y_s"] for r in rows]
    for model in (ck["no_gene"],ck["temporal_gene"]):
        if not all(math.isfinite(v) for v in model["weights"]):
            raise ValueError("NONFINITE_WEIGHTS")
    preds={
        "frozen_train_median":[ck["train_median_duration_s"]]*len(rows),
        "frozen_repo_median":[ck["train_repo_medians"][r["repo"]] for r in rows],
        "causal_repo_median":[math.expm1(r["x"][1]) for r in rows],
        "no_gene":[predict(ck["no_gene"],r) for r in rows],
        "temporal_gene":[predict(ck["temporal_gene"],r) for r in rows],
    }
    metrics={name:score(values,real) for name,values in preds.items()}
    by_repo={}
    for repo in REPOS:
        ix=[i for i,r in enumerate(rows) if r["repo"]==repo]
        if ix:
            by_repo[repo]={k:score([v[i] for i in ix],[real[i] for i in ix]) for k,v in preds.items()}
    candidate=metrics["temporal_gene"]["mae_s"]
    opponent=min(metrics[n]["mae_s"] for n in preds if n!="temporal_gene")
    across_repos=all(
        v["temporal_gene"]["mae_s"] < .95*min(v[n]["mae_s"] for n in preds if n!="temporal_gene")
        for v in by_repo.values())
    pass_candidate=(len(rows)>=GATE_MIN_ROWS and len(by_repo)==len(REPOS)
                    and candidate < .95*opponent and across_repos
                    and metrics["temporal_gene"]["log_mae"] < metrics["no_gene"]["log_mae"])
    result={"schema":SCHEMA,"provenance_sha256":h["provenance_sha256"],
            "holdout_count":len(rows),"holdout_job_ids_sha256":sha(sorted(r["job_id"] for r in rows)),
            "target":"actual_job_execution_seconds_excluding_queue",
            "models":metrics,"by_repository":by_repo,
            "research_gate":"R2_CANDIDATE_IMPROVEMENT_UNREPLICATED" if pass_candidate else "HOLD_NO_INDEPENDENT_DURATION_GAIN",
            "production_gate":"HOLD_REQUIRES_EXTERNAL_PROSPECTIVE_REPLICATION",
            "no_automatic_weight_promotion":True,
            "no_automatic_offspring":True}
    save(out_path,result)
    print(json.dumps({"research_gate":result["research_gate"],"holdout_count":len(rows),
                      "production_gate":result["production_gate"]},sort_keys=True))

def verify_future(previous_checkpoint_path, freeze_at, current_paths, out_path):
    """Out-of-time, frozen-weight comparison; strictly future job starts only.

    Previous weights and all frozen baselines were committed in a *prior* run.
    Features can use only histories completed before the respective job starts.
    Later outcomes never enter model fitting in this function.
    """
    previous=load(previous_checkpoint_path)
    if (previous.get("schema")!=SCHEMA or previous.get("production_authority") is not False
            or previous.get("holdout_seen_by_trainer") is not False):
        raise ValueError("BAD_FROZEN_CHECKPOINT")
    freeze=stamp(freeze_at)
    if freeze > dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
        raise ValueError("FUTURE_FREEZE_TIMESTAMP")
    for repo in REPOS:
        if stamp(previous["last_validation_completion_by_repo"][repo]) > freeze:
            raise ValueError("FROZEN_MODEL_TRAINED_AFTER_FUTURE_CUTOFF_" + repo)
    datasets=[check_split(p,name) for p,name in zip(current_paths,
                                                    ("train","validation","holdout"))]
    if len(datasets)!=3:
        raise ValueError("EXPECTED_THREE_NEW_SPLITS")
    provenance={x["provenance_sha256"] for x in datasets}
    if len(provenance)!=1:
        raise ValueError("NEW_SNAPSHOT_PROVENANCE_MISMATCH")
    rows=[r for dataset in datasets for r in dataset["rows"]
          if stamp(r["started_at"])>freeze+dt.timedelta(hours=1)]
    rows.sort(key=lambda r:(r["started_at"],r["job_id"]))
    if len({r["job_id"] for r in rows})!=len(rows):
        raise ValueError("FUTURE_DUPLICATE_JOB")
    counts={repo:sum(r["repo"]==repo for r in rows) for repo in REPOS}
    previous_hash=sha(previous)
    base={"schema":SCHEMA,"method":"FROZEN_PRIOR_RUN_PROSPECTIVE",
          "freeze_run_completed_at":iso(freeze),
          "prior_checkpoint_sha256":previous_hash,
          "new_dataset_provenance_sha256":next(iter(provenance)),
          "future_job_count":len(rows),"future_by_repo":counts,
          "baseline_frozen":True,"weights_updated":False,
          "production_gate":"HOLD_REQUIRES_EXTERNAL_PROSPECTIVE_REPLICATION"}
    if len(rows)<GATE_MIN_ROWS or min(counts.values())<10:
        base.update({"prospective_gate":"PENDING_INSUFFICIENT_NEW_JOBS",
                     "models":{},"by_repository":{}})
    else:
        actual=[r["y_s"] for r in rows]
        preds={
            "frozen_train_median":[previous["train_median_duration_s"]]*len(rows),
            "frozen_repo_median":[previous["train_repo_medians"][r["repo"]] for r in rows],
            "no_gene":[predict(previous["no_gene"],r) for r in rows],
            "temporal_gene":[predict(previous["temporal_gene"],r) for r in rows],
        }
        base["models"]={k:score(x,actual) for k,x in preds.items()}
        by_repo={}
        for repo in REPOS:
            idx=[i for i,r in enumerate(rows) if r["repo"]==repo]
            by_repo[repo]={k:score([v[i] for i in idx],[actual[i] for i in idx])
                           for k,v in preds.items()}
        base["by_repository"]=by_repo
        candidate=base["models"]["temporal_gene"]["mae_s"]
        strongest=min(base["models"][k]["mae_s"] for k in preds if k!="temporal_gene")
        per_repo_gain=all(
            vals["temporal_gene"]["mae_s"] <
              .95*min(vals[k]["mae_s"] for k in preds if k!="temporal_gene")
            for vals in by_repo.values())
        proof=(candidate < .95*strongest and per_repo_gain
               and base["models"]["temporal_gene"]["log_mae"] <
                   base["models"]["no_gene"]["log_mae"])
        base["prospective_gate"]=("FUTURE_CANDIDATE_GAIN_NEEDS_REPLICATION" if proof
                                  else "HOLD_NO_FUTURE_DURATION_GAIN")
    base["report_sha256"]=sha(base)
    save(out_path,base)
    print(json.dumps({"future_jobs":len(rows),"gate":base["prospective_gate"],
                      "production_gate":base["production_gate"]},sort_keys=True))
    return base

def main():
    ap=argparse.ArgumentParser()
    sub=ap.add_subparsers(dest="action",required=True)
    p=sub.add_parser("prepare");p.add_argument("--out",required=True)
    p=sub.add_parser("train");p.add_argument("--train",required=True)
    p.add_argument("--validation",required=True);p.add_argument("--out",required=True)
    p=sub.add_parser("verify");p.add_argument("--holdout",required=True)
    p.add_argument("--checkpoint",required=True);p.add_argument("--out",required=True)
    x=sub.add_parser("future")
    x.add_argument("--checkpoint",required=True)
    x.add_argument("--freeze-at",required=True)
    x.add_argument("--train",required=True)
    x.add_argument("--validation",required=True)
    x.add_argument("--holdout",required=True)
    x.add_argument("--out",required=True)
    args=ap.parse_args()
    if args.action=="future":
        verify_future(args.checkpoint,args.freeze_at,
                      [args.train,args.validation,args.holdout],args.out)
    elif args.action=="prepare":prepare(args.out,os.getenv("GH_TOKEN",""))
    elif args.action=="train":train(args.train,args.validation,args.out)
    else:verify(args.holdout,args.checkpoint,args.out)

if __name__=="__main__":
    main()
