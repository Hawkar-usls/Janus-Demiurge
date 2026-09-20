#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, subprocess, urllib.request
from pathlib import Path

URLS={
 "hrain":"https://raw.githubusercontent.com/Hawkar-usls/Hrain/janus/fundamentum-structural-memory/data/fundamentum-mirror/LATEST.json",
 "inaihr":"https://raw.githubusercontent.com/Hawkar-usls/iNaiHR/janus/fundamentum-associative-memory/data/fundamentum-associative/ASSOCIATIONS.json",
 "topa":"https://raw.githubusercontent.com/Hawkar-usls/TOPA/janus/pnp-autoresearch-state/data/pnp-autoresearch/LATEST.json"
}
UA="JANUS-Demiurge-PNP-Autoresearch/1.0"

def fetch(url,optional=False):
    try:
        req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
        with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
    except Exception as e:
        if optional:return {"status":"UNAVAILABLE","error":type(e).__name__+":"+str(e)}
        raise

def sh(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def read_status(root):
    p=root/"docs/CURRENT_RESEARCH_STATUS.md"
    return p.read_text(encoding="utf-8",errors="replace") if p.exists() else ""

def extract(text,name,default="UNRESOLVED"):
    m=re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*([^\n\r]+)",text)
    return m.group(1).strip().strip(chr(96)) if m else default

def run_probe(root,rel,timeout=150):
    p=root/rel
    if not p.exists():return {"path":rel,"status":"MISSING"}
    try:
        r=subprocess.run(["python",str(p)],cwd=str(root),text=True,capture_output=True,timeout=timeout)
        tail=((r.stdout or "")+"\n"+(r.stderr or ""))[-5000:]
        return {"path":rel,"status":"PASS" if r.returncode==0 else "FAIL","returncode":r.returncode,"output_tail":tail}
    except subprocess.TimeoutExpired:
        return {"path":rel,"status":"TIMEOUT_RESOURCE_LIMIT","timeout_seconds":timeout}
    except Exception as e:
        return {"path":rel,"status":"ERROR","error":type(e).__name__+":"+str(e)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--fundamentum",required=True);ap.add_argument("--out",required=True);a=ap.parse_args()
    root=Path(a.fundamentum);out=Path(a.out)
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
    status=read_status(root)
    hrain=fetch(URLS["hrain"])
    inaihr=fetch(URLS["inaihr"])
    topa=fetch(URLS["topa"],optional=True)
    tracks={
      "P_VS_NP":extract(status,"P_VS_NP","OPEN"),
      "A3_EXTERNAL_REPLICATION":extract(status,"A3_EXTERNAL_REPLICATION"),
      "A3_WORLD_NOVELTY_N4":extract(status,"A3_WORLD_NOVELTY_N4"),
      "C023_ASYMPTOTIC_LOWER_BOUND":extract(status,"C023_ASYMPTOTIC_LOWER_BOUND")
    }
    candidates=[
      {"id":"JANUS-C023-SIMULATION-ATTACK","goal":"seek simulation/counterexample for the exact Formula-Caching calculus","source":"C023_ASYMPTOTIC_LOWER_BOUND","status":"CANDIDATE"},
      {"id":"JANUS-C023-REASON-REUSE-ATTACK","goal":"attack contextual soundness and reusable-reason extraction","source":"C023 mainline","status":"CANDIDATE"},
      {"id":"JANUS-A3-PRIOR-ART-ATTACK","goal":"search for prior theorem or independent reproduction of A3","source":"A3 publication track","status":"CANDIDATE"},
      {"id":"JANUS-PNP-POLY-SAT-CANDIDATE","goal":"generate and falsify exact semantics-preserving polynomial SAT candidates","source":"P_VS_NP","status":"CANDIDATE"}
    ]
    probes=[
      run_probe(root,"experiments/direct/janus_tear_policy0a_fc_serialized_verifier.py"),
      run_probe(root,"experiments/direct/janus_tear_policy0a_reason_reuse_audit_v2.py")
    ]
    obj={
      "schema":"janus.pnp_autoresearch_context.v1",
      "status":"ACTIVE_CANDIDATE_RESEARCH",
      "goal":"P_VS_NP_RESEARCH_WITHOUT_CLAIM_PROMOTION",
      "fundamentum":{"repository":"Hawkar-usls/Janus-Fundamentum","commit":head,"read_only":True,"tracks":tracks},
      "memory":{"hrain":hrain,"inaihr_source_commit":inaihr.get("source_commit"),"inaihr_routes":inaihr.get("routes",[]),"topa":topa},
      "janus_own_candidates":candidates,
      "bounded_replay_probes":probes,
      "next_actions":[
        "Use TOPA discovery graph to challenge candidates and search for prior art/counterexamples.",
        "Use HRAiN structural index to locate exact committed attack surfaces.",
        "Use iNaiHR associative routes only to generate candidate questions.",
        "Prefer falsification and exact replay before any candidate expansion."
      ],
      "authority":{"truth":False,"proof":False,"scientific_claim_promotion":False,"fundamentum_mutation":False,"autonomous_merge":False},
      "laws":["OWN_RESEARCH != FUNDAMENTUM_AUTHORITY","MODEL_OUTPUT != PROOF","FINITE_REPLAY != ASYMPTOTIC_THEOREM","P_VS_NP = OPEN","NO_EXPLICIT_PROOF_GATE => NO_PNP_PROMOTION"]
    }
    obj["context_sha256"]=sh(obj)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status":obj["status"],"context_sha256":obj["context_sha256"],"fundamentum_commit":head,"probe_status":[p["status"] for p in probes]},indent=2))

if __name__=="__main__":main()
