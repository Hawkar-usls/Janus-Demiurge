from native_r71b_common import *
import re
def historical(root,manifest_root,tr,records,split):
    raw=(Path(manifest_root)/"janus_model/state/LAST_CORPUS_MANIFEST.json").read_bytes()
    req(hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\x00"+raw).hexdigest()==tr["historical_manifest_blob"],"MANIFEST_PIN")
    m=json.loads(raw);req(m["source_commit"]==tr["historical_registry_commit"],"SOURCE_PIN")
    req(m["anchor_is_training_source"] is False and m["eye_exclusions_enforced"] is True,"FIREWALL")
    docs=[]
    for row in records:
        req(row in m["records"] and row["split"]==split,"SPLIT")
        raw=(Path(root)/row["path"]).read_bytes()
        req(len(raw)==row["bytes"] and sha(raw)==row["sha256"],"REPLAY_PIN")
        req((int(row["sha256"][:8],16)%10==0)==(split=="holdout"),"HASH_SPLIT")
        txt=raw.decode("utf-8",errors="replace")
        for pattern in (r"ghp_[A-Za-z0-9]{20,}",r"github_pat_[A-Za-z0-9_]{20,}",r"sk-[A-Za-z0-9_-]{20,}",r"AIza[A-Za-z0-9_-]{20,}"):
            txt=re.sub(pattern,"[REDACTED_SECRET]",txt)
        envelope="\n<JANUS_REGISTRY_RECORD path="+json.dumps(row["path"])+" sha256="+row["sha256"]+' authority="REGISTRY_SOURCE_REQUIRES_VERIFICATION">\n'+txt+"\n</JANUS_REGISTRY_RECORD>\n"
        docs.append(envelope.encode("utf-8"))
    req(sum(map(len,docs))>=10000,"TEXT_SIZE")
    return docs
def sample_text(docs,rng,n):
    rows=[]
    for _ in range(n):
        doc=rng.choice(docs);start=rng.randrange(len(doc)-128);rows.append(list(doc[start:start+129]))
    return torch.tensor([w[:-1] for w in rows]),torch.tensor([w[1:] for w in rows])
def options(gold,alt,rng,i):
    choices=[gold,alt]
    for v in rng.sample(["?","0","1","2","3","101","205","99999"],8):
        if v not in choices:choices.append(v)
        if len(choices)==4:break
    req(len(set(choices))==4,"OPTIONS")
    choices.remove(gold);rng.shuffle(choices);choices.insert(i%4,gold)
    return choices
def augment(rows):
    rng=random.Random(713);extra=[]
    for i,r in enumerate(x for x in rows if x["group"]=="missing"):
        doc=dict(r["doc"]);value=next(iter(doc.values()));doc["absent"]=value;gold=str(value)
        extra.append({**r,"doc":doc,"gold":gold,"options":options(gold,"?",rng,i),"other":None,"alt":None})
    return rows+extra
def new_suite(ex):
    rng=random.Random(ex["seed"]);rows=[];seen=set()
    for group in GROUPS:
        for i in range(ex["cases_per_group"]):
            while True:
                k,l=rng.choice([("oak","elm"),("sun","moon"),("north","south"),("one","two")])
                a,b=rng.sample(range(101,200),2);doc={k:a,l:b}
                if group=="lookup":q="Value of "+k+"?";gold=str(a);alt=str(b);other={k:b,l:a}
                elif group=="addition":q=k+"+"+l+"?";gold=str(a+b);alt=str(a+b+1);other={k:a+1,l:b}
                elif group=="comparison":q=k+">"+l+"? 1=yes,0=no.";gold=str(int(a>b));alt=str(int(b>a));other={k:b,l:a}
                else:q="Value of absent? ?=absent.";gold="?";alt=str(a);other={**doc,"absent":a}
                identity=sha(canonical([doc,q]))
                if identity not in seen:seen.add(identity);break
            rows.append({"group":group,"doc":doc,"q":q,"gold":gold,"options":options(gold,alt,rng,i),"other":other,"alt":alt})
    return rows
def exact(r,doc):
    v=list(doc.values())
    if r["group"]=="lookup":return str(v[0])
    if r["group"]=="addition":return str(v[0]+v[1])
    if r["group"]=="comparison":return str(int(v[0]>v[1]))
    return str(doc.get("absent","?"))
