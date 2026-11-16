#!/usr/bin/env python3
"""Real Qwen G2 -> accepted G3 HTTP staging canary and failure rollback.

All model bytes are pinned to the prospectively accepted v5.4 G3 lineage.
A separate OS service process binds 127.0.0.1 only; a control process
atomically switches a closed set of adapters, injects real HTTP 503 and
requires post-rollback Qwen response digests identical to the original.

Never claims production deployment or independent scientific replication.
"""
from __future__ import annotations
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.request import Request,urlopen
from urllib.error import HTTPError

SCHEMA="janus.essence.v54.actual_qwen_http_staging_rollback/5.4"
ROUTE="janus.essence.v54.local_stage_route/5.4"
PORT="janus.essence.v54.loopback_http_service/5.4"
MODEL="Qwen/Qwen2.5-0.5B-Instruct"
REV="7ae557604adf67be50417f59c2c2f167def9a775"
PARENT="1ec5b21689ee5af6eec5345e0f5b91fc0870ffa520a56ef8778ce914ac28f3bc"
CHILD="bc05f07916cab24ae4fe814971b1de7e4b60a948bad1e99df19bbad720b2ef8d"
PARENT_LINEAGE="bea00f89a3e03b05faaed901afdb6cdd0c7f5f70293615250c20dec171196b6c"
CHILD_LINEAGE="9f8d54a6e3d497a46a12d3a27752caa710900e1c5b4a506f6477812d35162025"
MODELS={"g2":PARENT,"g3":CHILD}
PROMPT="In Hawkar-usls/iNaiHR/PROJECT_STATUS.json, what is the exact value of portfolio_class? Output only that value."
MAX_REPLY=384


def require(value,error):
    if not value: raise ValueError(error)


def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),
                      ensure_ascii=False,allow_nan=False).encode()


def seal(obj):
    return dict(obj,sha256=hashlib.sha256(canonical(obj)).hexdigest())


def check(obj):
    require(isinstance(obj,dict) and
            obj.get("sha256")==hashlib.sha256(canonical({
                k:v for k,v in obj.items() if k!="sha256"})).hexdigest(),
            "ST54_SEAL_BROKEN")
    return obj


def unique(pairs):
    obj={}
    for k,v in pairs:
        require(k not in obj,"ST54_DUPLICATE_JSON_KEY")
        obj[k]=v
    return obj


def read(path,cap=4096):
    p=Path(path)
    require(p.is_file() and not p.is_symlink() and
            2<=p.stat().st_size<=cap,"ST54_UNSAFE_JSON_FILE")
    return json.loads(p.read_text("utf-8"),object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(
            ValueError("ST54_NONFINITE_JSON")))


def route(name):
    require(name in MODELS,"ST54_UNKNOWN_MODEL")
    return seal({"schema":ROUTE,"target":name,
         "adapter_sha256":MODELS[name],"staging_only":True,
         "production_authority":False,"sentinel_dispatch":False})


def verify_route(obj):
    check(obj)
    name=obj.get("target")
    require(name in MODELS and obj==route(name),
            "ST54_ROUTE_ESCALATION")
    return name


def switch(stage,name):
    stage=Path(stage)
    require(stage.is_dir() and not stage.is_symlink(),"ST54_INVALID_STAGE_DIR")
    data=canonical(route(name))+b"\n"
    fd,tmp=tempfile.mkstemp(prefix=".st54-",dir=stage)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp,stage/"active.json")
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def load_route(stage):
    return verify_route(read(Path(stage)/"active.json"))


def adapter(directory,sha,lineage_sha):
    d=Path(directory)
    require(d.is_dir() and not d.is_symlink(),"ST54_MISSING_MODEL_DIR")
    w=d/"adapter_model.safetensors"
    require(w.is_file() and not w.is_symlink() and
            2000<=w.stat().st_size<=6_000_000 and
            hashlib.sha256(w.read_bytes()).hexdigest()==sha,
            "ST54_ADAPTER_BYTES_WRONG")
    obj=check(read(d/"lineage.json",50000))
    require(obj.get("sha256")==lineage_sha and
            obj.get("adapter_sha256")==sha and
            obj.get("production_promotion") in (False,None) and
            obj.get("sentinel_dispatch") in (False,None),
            "ST54_LINEAGE_BYTES_WRONG")
    return d


def verify_pair(parent,child):
    a=adapter(parent,PARENT,PARENT_LINEAGE)
    b=adapter(child,CHILD,CHILD_LINEAGE)
    child_lineage=check(read(b/"lineage.json",50000))
    require(child_lineage.get("generation")==3 and
            child_lineage.get("parent_generation")==2 and
            child_lineage.get("parent_adapter_sha256")==PARENT,
            "ST54_NOT_ACCEPTED_G2_TO_G3")
    return a,b


def served(parent,child,stage):
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from peft import PeftModel
    verify_pair(parent,child)
    require(load_route(stage)=="g2","ST54_MUST_START_PARENT")
    torch.set_num_threads(4)
    tk=AutoTokenizer.from_pretrained(MODEL,revision=REV,trust_remote_code=False)
    base=AutoModelForCausalLM.from_pretrained(
        MODEL,revision=REV,torch_dtype=torch.float32,
        use_safetensors=True,trust_remote_code=False).to("cpu")
    require(getattr(base.config,"_commit_hash",None)==REV,"ST54_BASE_REV_DRIFT")
    model=PeftModel.from_pretrained(base,str(parent),is_trainable=False).to("cpu").eval()
    model.load_adapter(str(child),adapter_name="candidate",is_trainable=False)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,status,obj):
            raw=canonical(obj)
            self.send_response(status)
            self.send_header("Content-Type","application/json")
            self.send_header("Cache-Control","no-store")
            self.send_header("Content-Length",str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        def do_GET(self):
            if self.path!="/health":
                return self.send(404,{"error":"INVALID_PATH"})
            try:
                name=load_route(stage)
                self.send(200,{"model":name,"adapter_sha256":MODELS[name],
                       "pid":os.getpid(),"bind":"127.0.0.1",
                       "production_authority":False})
            except (ValueError,KeyError,TypeError):
                self.send(503,{"error":"UNVERIFIED_STAGE"})
        def do_POST(self):
            if self.path!="/infer":
                return self.send(404,{"error":"INVALID_PATH"})
            try:
                size=int(self.headers.get("Content-Length","0"))
                require(1<=size<=512,"ST54_INVALID_REQUEST_SIZE")
                raw=self.rfile.read(size)
                msg=json.loads(raw,object_pairs_hook=unique)
                require(msg=={"question_id":"FROZEN_V54_STAGING_01"},
                        "ST54_ARBITRARY_MODEL_TEXT_DENIED")
                name=load_route(stage)
                if name=="g3" and (Path(stage)/"inject_503").exists():
                    return self.send(503,{"error":"INJECTED_QWEN_STAGE_FAULT",
                           "adapter_sha256":CHILD})
                model.set_adapter("default" if name=="g2" else "candidate")
                ids=tk.apply_chat_template(
                    [{"role":"user","content":PROMPT}],
                    tokenize=True,add_generation_prompt=True,
                    return_tensors="pt")
                with torch.inference_mode():
                    generated=model.generate(
                        ids,attention_mask=torch.ones_like(ids),
                        max_new_tokens=24,do_sample=False,
                        pad_token_id=tk.eos_token_id)
                answer=tk.decode(generated[0,ids.shape[1]:],
                                 skip_special_tokens=True).strip()
                require(len(answer)<=MAX_REPLY,"ST54_UNBOUNDED_INFERENCE")
                self.send(200,{"model":name,"adapter_sha256":MODELS[name],
                    "answer_sha256":hashlib.sha256(answer.encode()).hexdigest(),
                    "pid":os.getpid(),"production_authority":False})
            except (ValueError,TypeError,KeyError):
                self.send(400,{"error":"INVALID_MODEL_REQUEST"})
    http=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    http.daemon_threads=True
    p=Path(stage)/"port.json"
    p.write_bytes(canonical(seal({"schema":PORT,"port":http.server_address[1],
          "pid":os.getpid(),"bind":"127.0.0.1",
          "production_authority":False}))+b"\n")
    try: http.serve_forever(poll_interval=.1)
    finally:http.server_close()


def call(port,route_path,payload=None,status=200):
    request=Request(f"http://127.0.0.1:{port}{route_path}",
                    data=canonical(payload) if payload is not None else None,
                    headers={"Content-Type":"application/json"},
                    method="POST" if payload is not None else "GET")
    try:
        with urlopen(request,timeout=15) as resp:
            code=resp.status
            obj=json.loads(resp.read(2048))
    except HTTPError as exc:
        code=exc.code
        obj=json.loads(exc.read(2048))
    require(code==status,"ST54_HTTP_STATUS_WRONG")
    return obj


def rehearse(parent,child,stage,destination):
    verify_pair(parent,child)
    stage=Path(stage)
    destination=Path(destination)
    require(not stage.exists() and not stage.is_symlink() and
            not destination.exists(),"ST54_MUST_USE_NEW_STAGING_SPACE")
    stage.mkdir(parents=True,mode=0o700)
    switch(stage,"g2")
    proc=subprocess.Popen([sys.executable,"-m",
        "tools.essence_v54_qwen_stage","serve",
        "--parent",str(Path(parent).resolve()),
        "--child",str(Path(child).resolve()),
        "--stage",str(stage.resolve())],
        stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,text=True)
    try:
        doc=None
        for _ in range(300):
            if proc.poll() is not None:
                raise RuntimeError("ST54_MODEL_SERVICE_EXITED: "+proc.stderr.read()[-2500:])
            if (stage/"port.json").exists():
                doc=check(read(stage/"port.json"))
                break
            time.sleep(.1)
        require(doc is not None and doc.get("schema")==PORT and
                doc.get("bind")=="127.0.0.1" and
                doc.get("production_authority") is False and
                type(doc.get("port")) is int and
                1024<doc["port"]<65536,"ST54_UNVERIFIED_SERVICE_BIND")
        pid=doc["pid"]
        payload={"question_id":"FROZEN_V54_STAGING_01"}
        first=call(doc["port"],"/health")
        require(first["pid"]==pid and first["model"]=="g2",
                "ST54_PARENT_SERVICE_DID_NOT_START")
        baseline=[call(doc["port"],"/infer",payload) for _ in range(3)]
        require(all(x["pid"]==pid and x["model"]=="g2" and
                    x["adapter_sha256"]==PARENT for x in baseline),
                "ST54_REAL_BASELINE_INFER_FAILED")
        require(len({x["answer_sha256"] for x in baseline})==1,
                "ST54_BASELINE_NOT_DETERMINISTIC")
        switch(stage,"g3")
        candidate=call(doc["port"],"/health")
        require(candidate["pid"]==pid and candidate["model"]=="g3" and
                candidate["adapter_sha256"]==CHILD,
                "ST54_REAL_MODEL_NOT_SWITCHED")
        switched=[call(doc["port"],"/infer",payload) for _ in range(3)]
        require(all(x["model"]=="g3" and x["pid"]==pid and
                    x["adapter_sha256"]==CHILD for x in switched),
                "ST54_NEW_MODEL_INFER_FAILED")
        (stage/"inject_503").write_text("TEST_ONLY\n")
        fault=call(doc["port"],"/infer",payload,status=503)
        require(fault.get("error")=="INJECTED_QWEN_STAGE_FAULT",
                "ST54_INJECTED_FAULT_NOT_OBSERVED")
        switch(stage,"g2")
        back=call(doc["port"],"/health")
        restored=[call(doc["port"],"/infer",payload) for _ in range(3)]
        require(back["pid"]==pid and back["model"]=="g2" and
                all(x["pid"]==pid and x["model"]=="g2" and
                    x["answer_sha256"]==baseline[0]["answer_sha256"] and
                    x["adapter_sha256"]==PARENT for x in restored),
                "ST54_ROLLBACK_NOT_IDENTICAL")
        receipt=seal({"schema":SCHEMA,
            "status":"PASS_REAL_QWEN_LOOPBACK_ROLLOUT_AND_ROLLBACK",
            "g2_adapter_sha256":PARENT,"g3_adapter_sha256":CHILD,
            "candidate_was_accepted_internal_shadow":True,
            "live_service_pid_preserved":True,
            "real_qwen_http_requests_before":len(baseline),
            "real_qwen_http_requests_after_switch":len(switched),
            "real_qwen_http_requests_after_rollback":len(restored),
            "injected_canary_http_status":503,
            "original_answer_sha256":baseline[0]["answer_sha256"],
            "candidate_answer_sha256":switched[0]["answer_sha256"],
            "restored_answer_sha256":restored[0]["answer_sha256"],
            "restored_original_answer_exactly":True,
            "same_os_process":True,"bind":"127.0.0.1",
            "evidence_level":"SAME_OWNER_EPHEMERAL_ACTIONS_STAGING_ONLY",
            "public_network_exposure":False,
            "model_quality_claim":False,"production_promotion":False,
            "sentinel_dispatch":False,
            "actual_production_service_modified":False,
            "real_production_rollback_proven":False})
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(canonical(receipt)+b"\n")
        return receipt
    finally:
        proc.terminate()
        try:proc.wait(timeout=10)
        except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=("serve","rehearse"))
    p.add_argument("--parent",required=True)
    p.add_argument("--child",required=True)
    p.add_argument("--stage",required=True)
    p.add_argument("--out")
    a=p.parse_args()
    if a.mode=="serve":
        served(a.parent,a.child,a.stage)
    else:
        require(bool(a.out),"ST54_RECEIPT_REQUIRED")
        result=rehearse(a.parent,a.child,a.stage,a.out)
        print(json.dumps({"status":result["status"],
                 "production_promotion":False},sort_keys=True))


if __name__=="__main__":
    main()
