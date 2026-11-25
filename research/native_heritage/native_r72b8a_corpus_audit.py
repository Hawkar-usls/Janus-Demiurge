"""R72B8A: bounded source inventory, no labels inferred, no training."""
import hashlib,json,re,sys,subprocess
from pathlib import Path
HERE=Path(__file__).parent
P=json.loads((HERE/"R72B8A_PROTOCOL.json").read_text())
def digest(s):return hashlib.sha256(s if isinstance(s,bytes) else s.encode("utf-8")).hexdigest()
def blob(raw):return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
def req(ok,msg):
    if not ok:raise ValueError(msg)
def read(name):return json.loads((HERE/name).read_text())
def family(path):
    m=re.search(r"JANUS-COSMOS-SETI-R(\d+)",path)
    if m:return "cosmos_seti_r"+m.group(1)
    if "OSIRIS-SPEAR" in path:return "cosmos_osiris"
    if "TACHYON-DEMIHEAD" in path:return "tachyon_demihead"
    if "TACHYON-SIMPTOMAT" in path:return "tachyon_simptomat"
    m=re.search(r"data/essence/v(\d+)/",path)
    if m:
        n=int(m.group(1));return "essence_v"+str(n//10*10)+"s"
    return "ocean_controls"
def in_scope(p):
    return bool(re.match(r"^data/(?:JANUS-COSMOS-(?:SETI|OSIRIS-SPEAR)-|JANUS-TACHYON-(?:DEMIHEAD|SIMPTOMAT)-|essence/v\d+/|JANUS-OCEAN-|experiments/[^/]*(?:OCEAN|CAUSALITY-CONTROLS))",p,re.I) and p.endswith(".json"))
def leaves(v,path=()):
    if isinstance(v,dict):
        for k,x in v.items():yield from leaves(x,path+(k,))
    elif isinstance(v,list):
        for i,x in enumerate(v):yield from leaves(x,path+(i,))
    elif isinstance(v,str):yield path,v
def policy(doc):
    if not isinstance(doc,dict):return "NON_OBJECT"
    # Conservative: skip any record declaring report-only, no-training,
    # access or personal/clinical constraints. Existing source policy is not
    # replaced by the path allowlist.
    for k,v in doc.items():
        if any(s in k.lower() for s in ("storage_policy","training_policy","data_policy","privacy","license","consent")):
            t=json.dumps(v,ensure_ascii=False).lower()
            if re.search(r"reports.only|not.training|no.training|not.for.training|train(?:ing)?.{0,25}(?:forbid|prohibit|disallow|denied)|restricted|private.patient|personal.data|no.consent",t):return "POLICY_EXCLUDED"
    return None
CUES={
 "negative_result_candidate":r"\b(?:null result|negative result|below chance|no (?:gain|effect|improvement|difference|advantage)|worse than|failed (?:the |to meet )?(?:target|gate|criterion)|no evidence of|zero gain)\b|FAIL_ZERO|ZERO_GAIN|NO_GAIN|NEGATIVE_RESULT",
 "negated_execution_candidate":r"\b(?:not (?:yet )?(?:run|executed|conducted|performed|started|measured|tested|called)|never (?:run|executed|conducted|performed|completed)|not been (?:run|performed|tested|conducted)|no (?:measurements|experiment|test was)|not attempted|did not (?:run|execute|conduct))\b|NOT_(?:RUN|EXECUTED|CALLED|TESTED|MEASURED|PERFORMED)",
 "positive_candidate":r"\b(?:reproduced|verified|confirmed|passed|completed|matched|observed|recovered)\b|(?:^|_)PASS(?:_|$)",
 "future_candidate":r"\b(?:next (?:step|gate|stage)|will|preregister|pre-register|collect|obtain|evaluate|request|prepare|await|seek|compare)\b|NEXT_GATE",
 "mixed_scope_candidate":r"\b(?:but|however|only|not independent|not proof|not established|no claim|not validated|not externally|not demonstrated|cannot establish|cannot prove)\b",
 "uncertainty_candidate":r"\b(?:unknown|uncertain|unconfirmed|unverified|unavailable|inconclusive|undetermined|ambiguous|might|may|pending)\b|UNVERIFIED|UNKNOWN|UNCONFIRMED"
}
def tags(v):return sorted(k for k,p in CUES.items() if re.search(p,v,re.I))
def git_tree(root):
    raw=subprocess.check_output(["git","-C",str(root),"ls-tree","-r","-z",P["registry_commit"]])
    out=[]
    for x in raw.split(b"\0"):
        if not x:continue
        meta,p=x.split(b"\t",1);mode,kind,sha=meta.decode().split()
        path=p.decode("utf-8")
        if mode in ("100644","100755") and kind=="blob" and in_scope(path):out.append((path,sha))
    return sorted(out)
def main():
    root=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
    req(subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"]).decode().strip()==P["registry_commit"],"REGISTRY_PIN")
    exams={s["path"] for name in P["excluded_exam_specs"] for s in read(name)["sources"]}
    prior=read(P["existing_train_spec"]);old_docs={s["path"] for s in prior["sources"]};old_blobs={s["blob"] for s in prior["sources"]}|{s["blob"] for name in P["excluded_exam_specs"] for s in read(name)["sources"]}
    seen={digest(a["exact_text"]) for s in prior["sources"] for a in s["entries"]}
    # Also exclude exact excerpts from disclosed scope exams, irrespective of document.
    for name in ("R72B7B_PROTOCOL.json","R72B8_EXAM.json"):
        seen.update(digest(a["exact_text"]) for s in read(name)["sources"] for a in s.get("entries",[]))
    existing={}
    for s in prior["sources"]:
        for a in s["entries"]:existing[a["cohort"]]=existing.get(a["cohort"],0)+1
    counters={};queue=[];reserve=[];processed=0;counts={}
    def bump(k):counters[k]=counters.get(k,0)+1
    tree=git_tree(root)
    req(len(tree)<=P["max_documents"],"DOCUMENT_BOUND_EXCEEDED")
    for path,sha in tree:
        if path in exams or path in old_docs or sha in old_blobs:bump("prior_document_excluded");continue
        f=family(path)
        if f in P["reserve_families"]:
            reserve.append({"source":path,"blob":sha,"family":f});continue
        raw=(root/path).read_bytes();req(blob(raw)==sha,"BLOB_PIN")
        if len(raw)>P["max_file_bytes"]:bump("oversize_document");continue
        try:doc=json.loads(raw.decode("utf-8"))
        except (ValueError,UnicodeError):bump("invalid_document");continue
        reject=policy(doc)
        if reject:bump(reject);continue
        processed+=1
        for kp,v in leaves(doc):
            if len(v.encode("utf-8"))>P["candidate_max_bytes"] or len(v.strip())<12:bump("length_outside");continue
            if re.search(r"https?://|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",v):bump("contact_or_url");continue
            if re.search(r"(?i)\b(patient|participant)[ _-]?(?:name|id|record|identifier)\b",v):bump("possible_personal_record");continue
            cues=tags(v)
            if not cues:continue
            h=digest(v)
            if h in seen:bump("duplicate_or_disclosed_text");continue
            seen.add(h)
            queue.append({"source":path,"blob":sha,"family":f,"json_path":list(kp),"start":0,"end":len(v),"offset_unit":"unicode_codepoint","text_sha256":h,"exact_text":v,"candidate_tags":cues,"event":None,"outcome":None,"review_status":"UNREVIEWED"})
            for t in cues:counts[t]=counts.get(t,0)+1
    # Prioritize rare cues and lexical diversity; deterministic cap, not labels.
    queue.sort(key=lambda r:(min(counts[t] for t in r["candidate_tags"]),r["text_sha256"]))
    total=len(queue);queue=queue[:P["max_candidates"]]
    selected={}
    for r in queue:
        for t in r["candidate_tags"]:selected[t]=selected.get(t,0)+1
    report={"schema":"janus.native.r72b8a.result.v1","registry_commit":P["registry_commit"],"matched_documents":len(tree),"scanned_documents":processed,"reserve_documents":len(reserve),"candidate_total":total,"queued":len(queue),"candidate_tags":selected,"previous_real_labeled":sum(existing.values()),"previous_cohorts":existing,"excluded":counters,"new_labels":0,"minimum_reviewed_real":P["min_reviewed_real"],"minimum_per_critical_cohort":P["min_per_critical_cohort"],"training_ready":False,"training_performed":False,"production_changed":False,"note":"Cue counts overlap and are not class counts. Reserve manifests contain no text; source families are predeclared, not an external blind holdout."}
    for name,obj in (("CANDIDATE_QUEUE.json",queue),("RESERVE_MANIFEST.json",reserve),("AUDIT.json",report)):
        (out/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("R72B8A_AUDIT "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
