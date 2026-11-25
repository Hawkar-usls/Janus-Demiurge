from native_r72b7_common import *
def main():
    root,registry,folder,out=sys.argv[1:5]
    spec=read("research/native_heritage/R72B7B_PROTOCOL.json");train=read("research/native_heritage/R72B7_PROTOCOL.json")
    torch.set_num_threads(2);torch.manual_seed(train["seed"])
    receipt=read(Path(folder)/"RECEIPT.json");pin=receipt["receipt_sha256"]
    req(receipt["train_spec_sha256"]==sha(canonical(train)),"TRAIN_SPEC")
    parent,_,_=load_base(root,train);parent.eval();basepin=frozen_digest(parent);req(basepin==spec["parent_tensor_sha256"],"PARENT")
    students=frozen_heads(folder,pin,{k:v["sha256"] for k,v in receipt["variants"].items()},basepin,parent.config.d_model,Student)
    rows=[]
    for src in spec["sources"]:
        raw=(Path(registry)/src["path"]).read_bytes();req(git_blob(raw)==src["blob"],"SOURCE_PIN")
        doc=json.loads(raw)
        for entry in src["entries"]:
            value=doc
            for k in entry["path"]:value=value[int(k)] if isinstance(value,list) else value[k]
            req(isinstance(value,str),"TEXT")
            v=value[entry["start"]:entry["end"]];req(v==entry["exact_text"],"EXCERPT_PIN")
            rows.append({"source":src["path"],"path":entry["path"],"type":"string","value":json.dumps(v),"event":entry["event"],"outcome":entry["outcome"],"cohort":entry["cohort"],"start":entry["start"],"end":entry["end"]})
    req(len({r["value"] for r in rows})==len(rows),"DUPLICATE_EXAM")
    req(not set(receipt["train_text_sha256"])&{sha(r["value"].encode()) for r in rows},"TRAIN_OVERLAP")
    x,mask,n=raw_features(parent,rows)
    ge=torch.tensor([r["event"] for r in rows]);go=torch.tensor([r["outcome"] for r in rows]);known=ge>=0
    gold=compose(ge,go);results={};predictions={}
    def score(e,o):
        p=compose(e,o);d={"n":int(known.sum()),"ambiguous_n":int((~known).sum()),"factor_exact":int(((e==ge)&(o==go)&known).sum()),"group":selective_stats(gold[known],p[known]),"cohorts":{}}
        for cohort in sorted(set(r["cohort"] for r in rows)):
            ix=torch.tensor([r["cohort"]==cohort for r in rows])&known
            if not ix.any():continue
            d["cohorts"][cohort]={"n":int(ix.sum()),"factor_exact":int(((e==ge)&(o==go)&ix).sum()),"group":selective_stats(gold[ix],p[ix])}
        return d
    for name,m in students.items():
        e,o=predict_student(m,x,mask,n);results[name]=score(e,o)
        predictions[name]=[{"source":r["source"],"path":r["path"],"text_sha256":sha(r["value"].encode()),"event":int(a),"outcome":int(b),"gold_event":r["event"],"gold_outcome":r["outcome"],"cohort":r["cohort"]} for r,a,b in zip(rows,e,o)]
    # Teacher is a separate comparator only, after student inference.
    t=[locked_scope(r,-1,-1) for r in rows];results["teacher"]=score(torch.tensor([q[0] for q in t]),torch.tensor([q[1] for q in t]))
    gates={};g=spec["gates"]
    for name in students:
        d=results[name];c=d["cohorts"]
        checks={"factor":d["factor_exact"]/d["n"]>=g["factor_min"],"group":d["group"]["correct"]/d["n"]>=g["group_min"],"critical":d["group"]["critical_as_evidence"]<=g["critical_max"],"negative":c["negative_result"]["factor_exact"]/c["negative_result"]["n"]>=g["negative_min"],"negated":c["negated_execution"]["factor_exact"]/c["negated_execution"]["n"]>=g["negated_min"]}
        gates[name]={**checks,"pilot_gate":all(checks.values())}
    req(frozen_digest(parent)==basepin,"PARENT_CHANGED")
    report={"schema":"janus.native.r72b7b.result.v1","source_run":spec["source_run_id"],"student_receipt":pin,"source_blobs":[s["blob"] for s in spec["sources"]],"exam_sha256":sha(canonical(rows)),"results":results,"gates":gates,"predictions":predictions,"trained":False,"teacher_at_student_inference":False,"externally_blind":False,"native_pretraining_overlap_unknown":True,"manual_selected_pilot":True,"production_changed":False,"automatic_admission":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out).write_bytes(canonical(report));print("R72B7B_EXAM "+json.dumps({k:v for k,v in report.items() if k!="predictions"},sort_keys=True))
if __name__=="__main__":main()
