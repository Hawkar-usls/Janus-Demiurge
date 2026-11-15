#!/usr/bin/env python3
"""ESSENCE v4.3: REAL HTTP canary and rollback on isolated staging runner.

Uses the real sealed G4 Physarum and stronger 14-step fixed control FP32
checkpoints, via the independent v4.2 tensor loader. Runs two OS processes:
a loopback-bound model service and a separate rollout operator.
A real injected canary 503 forces atomic routing rollback to original
baseline14 on the *same live staging service process*; post-rollback HTTP
responses must exactly match baseline SHA256 outputs from before the switch.

No production service, deployment credentials, public port, model promotion,
workflow token mutation, or claim of live-production rollback.
"""
from __future__ import annotations
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import statistics
import struct
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.request import Request,urlopen

SCHEMA="janus.essence.isolated_http_model_deployment_rollback/4.3"
PORT_SCHEMA="janus.essence.staging_port_localhost/4.3"
ALLOWED={
    "baseline14":{
        "sha256":"a0a8a878fd784235e390f441ec192d973e079714321b5d8a6b2cbb343d3bd174",
        "generation":"g4_fixed_budget14",
    },
    "physarum":{
        "sha256":"dfbe1214f6e6f954b3f999d7d8802c89e2aa5fe45e75ffe9a68a73d76953683f",
        "generation":"g4_physarum",
    },
}
SENTINEL="PHYSARUM_G4_CANARY_ISOLATED_TEST_ONLY"
SAMPLE_TOKENS=[ord(c) for c in "def f(x): return x + 3\n"]
assert len(SAMPLE_TOKENS)==24


def require(ok,code):
    if not ok:
        raise ValueError(code)


def canonical(obj):
    return json.dumps(obj,ensure_ascii=False,sort_keys=True,
                      separators=(",",":"),allow_nan=False).encode("utf-8")


def sha(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def immutable_json(path,data):
    p=Path(path)
    require(not p.exists() and not p.is_symlink(),
            "IMMUTABLE_RECEIPT_ALREADY_EXISTS")
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("x",encoding="utf-8") as f:
        json.dump(data,f,sort_keys=True,indent=2)
        f.write("\n")


def atomic_json(path,data):
    path=Path(path)
    require(path.parent.is_dir() and not path.parent.is_symlink() and
            not path.is_symlink(),"INVALID_LOCAL_STAGING_STATE")
    fd,tmp=tempfile.mkstemp(prefix=".stage-switch-",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(canonical(data)+b"\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def active_payload(name):
    require(name in ALLOWED,"UNKNOWN_MODEL_CANNOT_BE_DEPLOYED")
    return {"schema":"janus.essence.stage_active_route/4.3",
            "model":name,"checkpoint_weights_sha256":ALLOWED[name]["sha256"],
            "production_authority":False,"stage_only":True}


def validate_active(row):
    require(isinstance(row,dict),"INVALID_ACTIVE_STATE")
    name=row.get("model")
    require(name in ALLOWED and row==active_payload(name),
            "ROUTE_NOT_PINNED_TO_LOCKED_CHECKPOINT")
    return name


def read_active(root):
    path=Path(root)/"active.json"
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_size<=512,"UNSAFE_ACTIVE_ROUTE_FILE")
    row=json.loads(path.read_text("utf-8"))
    return validate_active(row)


def stage_switch(root,name):
    require(name in ALLOWED,"UNAUTHORIZED_STAGING_MODEL")
    atomic_json(Path(root)/"active.json",active_payload(name))


def read_checkpoint(path,target,torch):
    from tools.essence_v42_cleanroom_verifier import restore_model
    path=Path(path)
    mf=path/"manifest.json"
    wt=path/"weights.f32"
    for p in (mf,wt):
        require(p.is_file() and not p.is_symlink() and
                32<p.stat().st_size<=500000,
                "UNSAFE_OR_MISSING_MODEL_CHECKPOINT")
    manifest=json.loads(mf.read_text("utf-8"))
    data=wt.read_bytes()
    expected=ALLOWED[target]
    require(hashlib.sha256(data).hexdigest()==expected["sha256"] and
            manifest.get("generation")==expected["generation"],
            "STAGING_WEIGHTS_NOT_PINNED")
    return restore_model(torch,manifest,data,target,expected["generation"])


def server(root,baseline,physarum):
    import torch
    torch.set_num_threads(1)
    models={
        "baseline14":read_checkpoint(baseline,"baseline14",torch),
        "physarum":read_checkpoint(physarum,"physarum",torch),
    }
    require(read_active(root)=="baseline14",
            "STAGING_MUST_START_WITH_STRONG_FIXED_BASELINE")
    root=Path(root)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass

        def respond(self,status,data):
            raw=canonical(data)
            self.send_response(status)
            self.send_header("Content-Type","application/json")
            self.send_header("Cache-Control","no-store")
            self.send_header("Content-Length",str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path!="/health":
                return self.respond(404,{"error":"UNKNOWN_ROUTE"})
            try:
                active=read_active(root)
                self.respond(200,{
                    "status":"STAGING_ONLY_HEALTHY",
                    "model":active,
                    "sha256":ALLOWED[active]["sha256"],
                    "pid":os.getpid(),
                    "production_authority":False,
                    "bind":"127.0.0.1"})
            except (ValueError,KeyError,TypeError) as error:
                self.respond(503,{"error":"INVALID_STAGE_STATE",
                                  "detail":str(error)})

        def do_POST(self):
            if self.path!="/infer":
                return self.respond(404,{"error":"UNKNOWN_ROUTE"})
            try:
                length=int(self.headers.get("Content-Length","0"))
                require(0<length<=512,"UNBOUNDED_REQUEST")
                data=json.loads(self.rfile.read(length))
                tokens=data.get("tokens") if isinstance(data,dict) else None
                require(isinstance(tokens,list) and len(tokens)==24 and
                        all(type(x)==int and 0<=x<=255 for x in tokens),
                        "INVALID_BYTE_CONTEXT")
                name=read_active(root)
                if name=="physarum" and (root/"fault.injection").exists():
                    return self.respond(503,{
                        "error":"INJECTED_STAGING_CANARY_FAULT",
                        "checkpoint_weights_sha256":ALLOWED[name]["sha256"]})
                x=torch.tensor([tokens],dtype=torch.long)
                start=time.perf_counter_ns()
                with torch.inference_mode():
                    out=models[name](x)
                logits=out[0,-1].tolist()
                require(len(logits)==256 and all(math.isfinite(v)
                        for v in logits),"INVALID_MODEL_OUTPUT")
                packed=struct.pack("<256f",*logits)
                elapsed=time.perf_counter_ns()-start
                self.respond(200,{
                    "model":name,"sha256":ALLOWED[name]["sha256"],
                    "logits_digest":hashlib.sha256(packed).hexdigest(),
                    "predicted_next_byte":max(range(256),key=lambda i:logits[i]),
                    "forward_wall_nanoseconds":elapsed,
                    "pid":os.getpid(),"production_authority":False})
            except (ValueError,TypeError,KeyError,json.JSONDecodeError) as error:
                self.respond(400,{"error":"INVALID_REQUEST_OR_STAGE_STATE",
                                  "detail":str(error)})

    http=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    http.daemon_threads=True
    port=http.server_address[1]
    immutable_json(root/"port.json",{
        "schema":PORT_SCHEMA,"port":port,"pid":os.getpid(),
        "listen":"127.0.0.1","production_authority":False})
    try:
        http.serve_forever(poll_interval=0.1)
    finally:
        http.server_close()


def api(port,route,payload=None,expected=200):
    url=f"http://127.0.0.1:{port}{route}"
    start=time.perf_counter_ns()
    request=Request(url,data=canonical(payload) if payload is not None else None,
                    headers={"Content-Type":"application/json"},
                    method="POST" if payload is not None else "GET")
    try:
        with urlopen(request,timeout=4) as f:
            code=f.status
            data=json.loads(f.read(4096))
    except HTTPError as error:
        code=error.code
        data=json.loads(error.read(4096))
    elapsed=(time.perf_counter_ns()-start)/1e6
    require(code==expected,"STAGING_HTTP_STATUS_UNEXPECTED")
    return data,elapsed


def verify_response(item,model,pid):
    require(item["model"]==model and
            item["sha256"]==ALLOWED[model]["sha256"] and
            item["pid"]==pid and
            item["production_authority"] is False and
            len(item["logits_digest"])==64 and
            type(item["predicted_next_byte"])==int,
            "LIVE_STAGING_RESPONSE_NOT_FROM_LOCKED_MODEL")


def rehearse(baseline,physarum,root,out):
    root=Path(root)
    require(not root.exists() and not root.is_symlink() and
            not Path(out).exists(),
            "ISOLATED_STAGING_WORKSPACE_MUST_BE_NEW")
    root.mkdir(parents=True,mode=0o700)
    stage_switch(root,"baseline14")
    command=[sys.executable,"-m","tools.essence_v43_staging_rollback",
             "serve","--baseline14-dir",str(Path(baseline).resolve()),
             "--physarum-dir",str(Path(physarum).resolve()),
             "--stage-dir",str(root.resolve())]
    proc=subprocess.Popen(command,stdin=subprocess.DEVNULL,
                          stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
                          text=True)
    try:
        port_rec=None
        for _ in range(200):
            if proc.poll() is not None:
                stderr=proc.stderr.read()[-3000:]
                raise RuntimeError("STAGING_SERVICE_DID_NOT_START: "+stderr)
            port_path=root/"port.json"
            if port_path.exists():
                port_rec=json.loads(port_path.read_text("utf-8"))
                break
            time.sleep(0.05)
        require(port_rec is not None,"STAGING_START_TIMEOUT")
        require(port_rec.get("schema")==PORT_SCHEMA and
                port_rec.get("listen")=="127.0.0.1" and
                port_rec.get("pid")==proc.pid and
                port_rec.get("production_authority") is False,
                "STAGING_MUST_BIND_LOOPBACK_ONLY")
        port=port_rec["port"]
        health,_=api(port,"/health")
        require(health["model"]=="baseline14" and
                health["sha256"]==ALLOWED["baseline14"]["sha256"],
                "INITIAL_STRONG_BASELINE_NOT_ACTIVE")
        payload={"tokens":SAMPLE_TOKENS}
        # Initial HTTP real inference on sealed baseline14
        previous,initial_latency=api(port,"/infer",payload)
        verify_response(previous,"baseline14",proc.pid)
        initial_output_digest=previous["logits_digest"]
        # Canary rollout is one atomic local route write.
        stage_switch(root,"physarum")
        canary_health,_=api(port,"/health")
        require(canary_health["model"]=="physarum" and
                canary_health["pid"]==proc.pid,
                "CANDIDATE_WAS_NOT_ACTUALLY_DEPLOYED")
        canary_latencies=[]
        candidate_digests=set()
        for _ in range(100):
            candidate,latency=api(port,"/infer",payload)
            verify_response(candidate,"physarum",proc.pid)
            canary_latencies.append(latency)
            candidate_digests.add(candidate["logits_digest"])
        require(len(candidate_digests)==1 and
                next(iter(candidate_digests))!=initial_output_digest,
                "CANDIDATE_MUST_RETURN_REAL_DISTINCT_MODEL_OUTPUT")
        fault=root/"fault.injection"
        with fault.open("x") as f:
            f.write(SENTINEL)
        bad,failure_latency=api(port,"/infer",payload,expected=503)
        require(bad.get("error")=="INJECTED_STAGING_CANARY_FAULT" and
                bad.get("checkpoint_weights_sha256")==
                ALLOWED["physarum"]["sha256"],
                "FAULT_INJECTION_DID_NOT_EXERCISE_CANDIDATE")
        rollback_start=time.perf_counter_ns()
        stage_switch(root,"baseline14")
        # Strong rollback evidence: same PID and same actual logits SHA.
        rollback_latencies=[]
        for _ in range(100):
            restored,latency=api(port,"/infer",payload)
            verify_response(restored,"baseline14",proc.pid)
            require(restored["logits_digest"]==initial_output_digest,
                    "ROLLBACK_DID_NOT_RESTORE_EXACT_ORIGINAL_OUTPUT")
            rollback_latencies.append(latency)
        rollback_elapsed=(time.perf_counter_ns()-rollback_start)/1e6
        final_health,_=api(port,"/health")
        require(final_health["pid"]==proc.pid and
                final_health["model"]=="baseline14" and
                final_health["sha256"]==ALLOWED["baseline14"]["sha256"],
                "FINAL_STAGING_SERVICE_NOT_RESTORED")
        def stats(values):
            return {"count":len(values),
                    "median_http_ms":statistics.median(values),
                    "p95_http_ms":sorted(values)[int(0.95*(len(values)-1))]}
        receipt={
            "schema":SCHEMA,
            "status":"PASS_REAL_ISOLATED_HTTP_CANARY_FAULT_AND_ROLLBACK",
            "service_type":"real_separate_process_python_http_on_loopback",
            "bind":"127.0.0.1","pid_preserved":True,
            "original_checkpoint":ALLOWED["baseline14"],
            "candidate_checkpoint":ALLOWED["physarum"],
            "initial_baseline_logits_sha256":initial_output_digest,
            "canary_logits_sha256":next(iter(candidate_digests)),
            "restored_baseline_logits_sha256":initial_output_digest,
            "before_after_baseline_byte_identical":True,
            "canary_real_inference_requests":100,
            "post_rollback_real_inference_requests":100,
            "observed_candidate_fault_http_status":503,
            "observed_candidate_fault_code":bad["error"],
            "rollout_method":"atomic_local_route_file_replace",
            "rollback_method":"atomic_local_route_file_replace",
            "fault_to_verified_rollback_http_milliseconds":
                rollback_elapsed,
            "candidate_http_latency":stats(canary_latencies),
            "restored_http_latency":stats(rollback_latencies),
            "initial_baseline_http_ms":initial_latency,
            "simulated_stage_only":True,
            "external_independent_replication":False,
            "actual_production_service_modified":False,
            "real_production_target_hardware_verified":False,
            "real_production_rollback_proven":False,
            "production_authority":False,
            "automatic_promotion":False
        }
        receipt["receipt_sha256"]=sha(receipt)
        immutable_json(out,receipt)
        return receipt
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        if proc.stderr is not None:
            proc.stderr.close()


def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="cmd",required=True)
    for cmd in ("serve","rehearse"):
        a=sub.add_parser(cmd)
        a.add_argument("--baseline14-dir",required=True)
        a.add_argument("--physarum-dir",required=True)
        a.add_argument("--stage-dir",required=True)
        if cmd=="rehearse":
            a.add_argument("--out",required=True)
    args=p.parse_args()
    if args.cmd=="serve":
        server(args.stage_dir,args.baseline14_dir,args.physarum_dir)
    else:
        result=rehearse(args.baseline14_dir,args.physarum_dir,
                       args.stage_dir,args.out)
        print(json.dumps({
            "status":result["status"],
            "canary_requests":result["canary_real_inference_requests"],
            "rollback_requests":result["post_rollback_real_inference_requests"],
            "receipt_sha256":result["receipt_sha256"],
            "real_production_rollback_proven":False,
            "production_authority":False},sort_keys=True))


if __name__=="__main__":
    main()
