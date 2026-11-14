#!/usr/bin/env python3
"""ESSENCE v1.9 live localhost HTTP canary + automatic rollback research test.

Actually serves requests using the trained descendant and original parent neural
weights. Runs on a temporary 127.0.0.1 socket in GitHub Actions and closes on
completion. It is NOT an existing JANUS production service or production rollback.
"""
from __future__ import annotations
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import math
from pathlib import Path
import secrets
import threading
import urllib.request
import torch
from tools import essence_v19_gradirnya as e

torch.set_num_threads(1)
LOCK=threading.RLock()

class NeuralCanary:
    def __init__(self,checkpoint,receipt):
        path=Path(checkpoint)
        if path.is_symlink() or path.stat().st_size>12_000_000:
            raise ValueError("UNSAFE_SERVICE_CHECKPOINT")
        if e.sha(path.read_bytes())!=receipt.get("offspring_file_sha256"):
            raise ValueError("SERVICE_SHA_BINDING_FAILURE")
        if (receipt.get("schema")!=e.LINEAGE or receipt.get("production_authority") is not False
            or receipt.get("receipt_sha256")!=e.seal({k:v for k,v in receipt.items() if k!="receipt_sha256"})
            or type(receipt.get("cell")) is not int or not 0<=receipt["cell"]<6):
            raise ValueError("UNTRUSTED_SERVICE_RECEIPT")
        obj=torch.load(path,map_location="cpu",weights_only=True)
        if (obj.get("schema")!=e.LINEAGE or obj.get("production_authority") is not False
            or obj.get("cell")!=receipt["cell"]):
            raise ValueError("UNTRUSTED_SERVICE_ARTIFACT")
        self.baseline=e.r.model_for(receipt["cell"])
        self.baseline.load_state_dict(obj["initial_state"],strict=True)
        self.baseline.eval()
        self.candidate=e.r.model_for(receipt["cell"])
        self.candidate.load_state_dict(obj["final_state"],strict=True)
        self.candidate.eval()
        if (e.stable_state(self.baseline.state_dict())!=receipt["initial_weights_sha256"]
            or e.stable_state(self.candidate.state_dict())!=receipt["final_weights_sha256"]):
            raise ValueError("SERVICE_TENSOR_HASH_MISMATCH")
        self.baseline_sha=receipt["initial_weights_sha256"]
        self.candidate_sha=receipt["final_weights_sha256"]
        self.active="baseline"
        self.inject_fault=False
        self.total=0;self.candidate_requests=0;self.rollback_count=0
        self.token=secrets.token_hex(24)
        self.lock=threading.RLock()

    def status(self):
        with self.lock:
            return {"service_kind":"EPHEMERAL_LOCALHOST_HTTP_NEURAL_MODEL",
                    "active":self.active,
                    "active_sha256":self.baseline_sha if self.active=="baseline" else self.candidate_sha,
                    "requests":self.total,"candidate_requests":self.candidate_requests,
                    "rollbacks":self.rollback_count,"production_authority":False}

    def change(self,action,token):
        with self.lock:
            if not secrets.compare_digest(token,self.token):raise PermissionError("UNAUTHORIZED_CANARY_CONTROL")
            if action=="canary":
                if self.candidate_sha==self.baseline_sha:raise ValueError("NO_TRAINED_CHILD_TO_DEPLOY")
                self.active="candidate";return self.status()
            if action=="fault":
                if self.active!="candidate":raise ValueError("FAULT_ONLY_WITH_ACTIVE_CANARY")
                self.inject_fault=True;return self.status()
            if action=="rollback":
                self.active="baseline";self.inject_fault=False;self.rollback_count+=1
                return self.status()
            raise ValueError("UNKNOWN_CANARY_ACTION")

    def predict(self,tokens):
        if (not isinstance(tokens,list) or not 1<=len(tokens)<=e.r.CONFIG.context_length
            or any(type(t) is not int or not 0<=t<256 for t in tokens)):
            raise ValueError("INVALID_HTTP_MODEL_INPUT")
        with self.lock:
            use=self.active
            self.total+=1
            if use=="candidate":self.candidate_requests+=1
            try:
                if use=="candidate" and self.inject_fault:
                    raise ArithmeticError("INJECTED_NONFINITE_CANARY_OUTPUT")
                network=self.candidate if use=="candidate" else self.baseline
                with torch.no_grad():
                    logits=network(torch.tensor([tokens],dtype=torch.long))[0][0,-1,:len(e.r.LABELS)]
                    if not bool(torch.isfinite(logits).all()):raise ArithmeticError("NONFINITE_REAL_LOGITS")
                    best=int(torch.argmax(logits).item())
                return {"prediction":best,"served_by":use,"fallback":False}
            except (ArithmeticError,RuntimeError,ValueError):
                if use!="candidate":raise
                # Atomic rollback within this SAME live HTTP service process.
                self.active="baseline";self.inject_fault=False;self.rollback_count+=1
                with torch.no_grad():
                    logits=self.baseline(torch.tensor([tokens],dtype=torch.long))[0][0,-1,:len(e.r.LABELS)]
                    if not bool(torch.isfinite(logits).all()):raise ValueError("BASELINE_MODEL_INVALID")
                    best=int(torch.argmax(logits).item())
                return {"prediction":best,"served_by":"baseline","fallback":True}

def make_handler(manager):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def answer(self,status,payload):
            data=json.dumps(payload,sort_keys=True).encode()
            self.send_response(status)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        def do_GET(self):
            if self.path!="/health":return self.answer(404,{"error":"UNKNOWN_ROUTE"})
            return self.answer(200,manager.status())
        def do_POST(self):
            if self.path not in ("/infer","/admin/canary","/admin/fault","/admin/rollback"):
                return self.answer(404,{"error":"UNKNOWN_ROUTE"})
            try:
                size=int(self.headers.get("Content-Length","0"))
                if not 1<=size<=2048:raise ValueError("PAYLOAD_LIMIT")
                obj=json.loads(self.rfile.read(size))
                if self.path=="/infer":out=manager.predict(obj.get("tokens"))
                else:out=manager.change(self.path.rsplit("/",1)[-1],self.headers.get("X-Research-Token",""))
                self.answer(200,out)
            except (ValueError,PermissionError,TypeError,KeyError) as exc:
                self.answer(400,{"error":str(exc)[:120]})
    return Handler

def request(port,path,obj=None,token=None):
    url=f"http://127.0.0.1:{port}{path}"
    if obj is None:
        with urllib.request.urlopen(url,timeout=5) as response:
            return json.load(response)
    headers={"Content-Type":"application/json"}
    if token is not None:headers["X-Research-Token"]=token
    data=json.dumps(obj).encode()
    with urllib.request.urlopen(urllib.request.Request(url,data=data,headers=headers,method="POST"),timeout=5) as response:
        return json.load(response)

def exercise(weights,receipt,validation,out,requests=120):
    if type(requests) is not int or not 100<=requests<=200:
        raise ValueError("CANARY_REQUEST_BUDGET")
    if validation.get("kind")!="validation":
        raise ValueError("SERVICE_MUST_NOT_USE_SEALED_HOLDOUT")
    e.check_packet(validation,"validation",receipt["source_commit"],receipt["dataset_sha256"])
    if validation["packet_sha256"]!=receipt["validation_sha256"]:
        raise ValueError("CANARY_VALIDATION_SOURCE_MISMATCH")
    m=NeuralCanary(weights,receipt)
    server=ThreadingHTTPServer(("127.0.0.1",0),make_handler(m))
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    port=server.server_address[1]
    observed=[]
    try:
        before=request(port,"/health")
        if receipt["accepted_generations"]==0:
            raise ValueError("NO_VALIDATED_DESCENDANT_FOR_RESEARCH_CANARY")
        request(port,"/admin/canary",{},m.token)
        rows=validation["rows"]
        for i in range(requests):
            observed.append(request(port,"/infer",{"tokens":rows[i%len(rows)]["x"]}))
        if any(x["served_by"]!="candidate" for x in observed):
            raise ValueError("CANDIDATE_NEVER_SERVED_REAL_HTTP_REQUESTS")
        request(port,"/admin/fault",{},m.token)
        result=request(port,"/infer",{"tokens":rows[0]["x"]})
        after=request(port,"/health")
        if (not result["fallback"] or result["served_by"]!="baseline"
            or after["active"]!="baseline" or after["active_sha256"]!=m.baseline_sha
            or after["rollbacks"]!=1 or after["candidate_requests"]<requests):
            raise ValueError("LIVE_HTTP_ROLLBACK_NOT_RESTORED")
        for i in range(10):
            verify=request(port,"/infer",{"tokens":rows[i%len(rows)]["x"]})
            if verify["served_by"]!="baseline":raise ValueError("POST_ROLLBACK_INVALID")
        result={"schema":"janus.essence.ephemeral_http_canary/1.9",
                "run_local_only":True,"same_process_live_http_service":True,
                "real_neural_model_inference":True,"actual_canary_requests":requests,
                "post_rollback_requests":10,"rollbacks":after["rollbacks"],
                "baseline_weights_sha256":m.baseline_sha,
                "candidate_weights_sha256":m.candidate_sha,
                "service_status_after":after,"fault_injected":True,
                "rollback_within_single_service_process":True,
                "live_production_service_tested":False,
                "independent_external_holdout":False,
                "target_hardware_certified":False,
                "production_promotion":False,"gate":"PASS_ISOLATED_HTTP_RESEARCH_SERVICE_ONLY"}
        result["receipt_sha256"]=e.seal(result)
        e.atomic_json(out,result)
        return result
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--weights",required=True);p.add_argument("--lineage",required=True)
    p.add_argument("--validation",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    result=exercise(a.weights,e.read_json(a.lineage),e.read_json(a.validation),a.out)
    print(json.dumps({"requests":result["actual_canary_requests"],"rollbacks":result["rollbacks"],
                      "production_authority":False,"gate":result["gate"]}))

if __name__=="__main__":main()
