"""JANUS Ocean R3.1: separate chronological training pack and held-out admission.

Inputs: real Ocean meta-next source-head pinned snapshot, report, and weights.
Does not train, read R3 quarantined contents, or deploy model candidates.
A good public retrospective score is not an external blind science test.
"""
from __future__ import annotations
import argparse,hashlib,json,re
from pathlib import Path
from experiments.ocean_transformer.ocean_r3_registry_bridge import chronology_allowed

SCHEMA="janus.ocean.r31.chronology_admission.v1"
TRAIN_SCHEMA="janus.ocean.r31.training_only_commit_chronology.v1"
SNAPSHOT_SCHEMA="janus.meta_next.snapshot.v1"
REPORT_SCHEMA="janus.meta_next.train_result.v1"
SHA40=re.compile(r"^[a-f0-9]{40}$")
CONTEXT=16

def need(condition,message):
    if not condition:raise ValueError(message)

def sha_bytes(x):return hashlib.sha256(x).hexdigest()
def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),
                      ensure_ascii=False,allow_nan=False).encode()
def digest(x):return sha_bytes(canonical(x))
def read(path):
    obj=json.loads(Path(path).read_text(encoding="utf8"))
    need(isinstance(obj,dict),"INPUT_NOT_DICT")
    return obj

def audit_snapshot(path):
    snap=read(path)
    need(snap.get("schema")==SNAPSHOT_SCHEMA,"SNAPSHOT_SCHEMA")
    need(snap.get("source_repository")=="Hawkar-usls/janus-meta-registry",
         "SOURCE_REPOSITORY")
    need(SHA40.fullmatch(str(snap.get("source_head",""))) is not None,
         "SOURCE_SHA")
    events=snap.get("events");seq=snap.get("sequence");labels=snap.get("labels")
    need(isinstance(events,list) and isinstance(seq,list) and
         isinstance(labels,list) and len(events)==len(seq) and
         160<=len(events)<=5000,"EVENT_COUNT")
    need(1<len(labels)<=48 and labels[-1]=="OTHER"
         and len(set(labels))==len(labels),"CLASS_MAP")
    need(snap.get("events_count")==len(events),"EVENT_COUNT_FIELD")
    train_end=int(len(seq)*.70)
    val_end=int(len(seq)*.85)
    need(snap.get("train_cutoff_idx")==train_end,"TRAIN_CUTOFF")
    train=list(range(CONTEXT,train_end))
    valid=list(range(train_end+CONTEXT,val_end))
    test=list(range(val_end+CONTEXT,len(seq)))
    need(min(len(train),len(valid),len(test))>=20,
         "HOLDOUT_TOO_SMALL")
    need(not (set(train)&set(valid) or set(train)&set(test)
              or set(valid)&set(test)),"HOLDOUT_OVERLAP")
    seen=set()
    for i,item in enumerate(events):
        need(isinstance(item,dict) and
             SHA40.fullmatch(str(item.get("commit",""))) is not None,
             "BAD_EVENT_SHA")
        need(item["commit"] not in seen,"DUPLICATE_COMMIT")
        seen.add(item["commit"])
        need(chronology_allowed(item.get("first_path","")) and
             isinstance(item.get("representative_label"),str),
             "QUARANTINE_IN_TRAINING_CHRONOLOGY")
        need(type(seq[i]) is int and 0<=seq[i]<len(labels),
             "BAD_CLASS_ID")
    rows=[{"commit":events[i]["commit"],
           "class_id":seq[i],
           "historical_time":events[i].get("timestamp")} for i in train]
    pack={
        "schema":TRAIN_SCHEMA,
        "source_snapshot_sha256":sha_bytes(Path(path).read_bytes()),
        "source_head_sha":snap["source_head"],
        "events_count_total":len(events),
        "train_indices_start":train[0],
        "train_indices_end_exclusive":train[-1]+1,
        "train_events":rows,
        "label_map":labels,
        "validation_target_count":len(valid),
        "test_target_count":len(test),
        "validation_target_ids_in_training":False,
        "test_target_ids_in_training":False,
        "source_quarantine_used_as_gradient":False,
        "science_claims_verified":False,
        "independent_external_blind_holdout":False,
        "training_authorized_for_research_only":True,
        "scientific_admission":"HOLD",
    }
    pack["pack_sha256"]=digest(pack)
    return snap,pack

def evaluate(snapshot,report,ckpt):
    snap,pack=audit_snapshot(snapshot)
    r=read(report)
    need(r.get("schema")==REPORT_SCHEMA
         and r.get("production_promotion") is False,
         "REPORT_NOT_RESEARCH")
    snapshot_sha=sha_bytes(Path(snapshot).read_bytes())
    ckpt_sha=sha_bytes(Path(ckpt).read_bytes())
    need(r.get("source_snapshot_sha256")==snapshot_sha,
         "SNAPSHOT_SHA_MISMATCH")
    need(r.get("candidate_weights_sha256")==ckpt_sha,
         "CHECKPOINT_SHA_MISMATCH")
    need(r.get("meta_head")==snap["source_head"],"META_HEAD_DRIFT")
    need(r.get("events_count")==len(snap["events"]),"EVENTS_COUNT_DRIFT")
    need(type(r.get("test_event_indices")) is int
         and r["test_event_indices"]==pack["test_target_count"],
         "TEST_COUNT_DRIFT")
    need(type(r.get("train_event_indices")) is int
         and r["train_event_indices"]==len(pack["train_events"]),
         "TRAIN_COUNT_DRIFT")
    model=r.get("test_model");base=r.get("test_baselines")
    need(isinstance(model,dict) and isinstance(base,dict),
         "METRIC_REPORT_MISSING")
    need(model.get("n")==pack["test_target_count"],
         "METRIC_DENOMINATOR")
    xs=(model.get("accuracy"),base.get("majority_accuracy"),
        base.get("markov_accuracy"))
    need(all(type(x) in (float,int) and 0<=x<=1 for x in xs),
         "INVALID_METRICS")
    acc=xs[0];control=max(xs[1:])
    margin=round(acc-control,8)
    positive=margin>=.02
    status=("DEVELOPMENT_GAIN_REQUIRES_NEW_PROSPECTIVE_TEST"
            if positive else "NO_REPRODUCIBLE_BASELINE_GAIN")
    obj={
        "schema":SCHEMA,
        "source_snapshot_sha256":snapshot_sha,
        "source_head_sha":snap["source_head"],
        "training_pack_sha256":pack["pack_sha256"],
        "candidate_checkpoint_sha256":ckpt_sha,
        "train_count":len(pack["train_events"]),
        "validation_count":pack["validation_target_count"],
        "test_count":pack["test_target_count"],
        "model_accuracy":acc,
        "majority_baseline_accuracy":xs[1],
        "markov_baseline_accuracy":xs[2],
        "strongest_baseline_accuracy":control,
        "absolute_accuracy_gain_over_strongest_baseline":margin,
        "development_gain_ge_0p02":positive,
        "retrospective_test_predictions_available":False,
        "paired_significance_estimated":False,
        "independent_external_blind_evaluation":False,
        "scientific_claims_accepted":False,
        "model_trained_on_news_or_r3_quarantine":False,
        "production_model_promotion":False,
        "scientific_admission":"HOLD",
        "status":status,
    }
    obj["receipt_sha256"]=digest(obj)
    return pack,obj

def main():
    p=argparse.ArgumentParser()
    for flag in ("snapshot","report","checkpoint","out","train-out"):
        p.add_argument("--"+flag,required=True)
    args=p.parse_args()
    pack,report=evaluate(args.snapshot,args.report,args.checkpoint)
    a,b=Path(args.out),Path(args.train_out)
    need(a!=b and not a.exists() and not b.exists(),
         "REFUSE_OVERWRITE")
    for path,obj in ((a,report),(b,pack)):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n",
                        encoding="utf8")
    print(json.dumps({key:report[key] for key in (
        "model_accuracy","majority_baseline_accuracy",
        "markov_baseline_accuracy","absolute_accuracy_gain_over_strongest_baseline",
        "status","scientific_admission")},sort_keys=True))

if __name__=="__main__":main()
