"""R72A: typed path evidence on original full JSON documents, frozen skill transfer."""
from native_r71d7_common import *
import hashlib,math
NUM=re.compile(rb"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
SHORT=re.compile(r"[a-z]{2,7}\Z")
def git_blob(raw):return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
def kind(v):
    if v is None:return "null"
    if type(v) is bool:return "boolean"
    if type(v) is int:return "integer"
    if type(v) is float:return "number"
    if type(v) is str:return "string"
    if type(v) is list:return "array"
    if type(v) is dict:return "object"
    raise ValueError("TYPE")
class Scan:
    def __init__(self,raw):
        req(len(raw)<=2000000,"DOCUMENT_LIMIT");self.raw=raw;self.i=0;self.nodes={}
    def ws(self):
        while self.i<len(self.raw) and self.raw[self.i] in b" \t\r\n":self.i+=1
    def take(self,c):
        self.ws()
        if self.raw[self.i:self.i+1]!=c:raise ValueError("EXPECTED_TOKEN")
        self.i+=1
    def string(self):
        s=self.i;self.take(b'"');escape=False
        while self.i<len(self.raw):
            c=self.raw[self.i];self.i+=1
            if escape:escape=False
            elif c==92:escape=True
            elif c==34:
                v=json.loads(self.raw[s:self.i].decode("utf-8"))
                if not isinstance(v,str):raise ValueError("STRING")
                # Reject lone surrogate code points.
                v.encode("utf-8");return v
        raise ValueError("UNTERMINATED_STRING")
    def value(self,path=(),depth=0):
        if depth>64:raise ValueError("DEPTH")
        self.ws();s=self.i;ch=self.raw[self.i:self.i+1]
        if ch==b"{":
            self.i+=1;v={};self.ws()
            if self.raw[self.i:self.i+1]!=b"}":
                while True:
                    self.ws();k=self.string()
                    if k in v:raise ValueError("DUPLICATE_KEY")
                    self.take(b":");v[k]=self.value(path+(k,),depth+1);self.ws()
                    if self.raw[self.i:self.i+1]==b"}":break
                    self.take(b",")
            self.take(b"}")
        elif ch==b"[":
            self.i+=1;v=[];self.ws()
            if self.raw[self.i:self.i+1]!=b"]":
                while True:
                    v.append(self.value(path+(len(v),),depth+1));self.ws()
                    if self.raw[self.i:self.i+1]==b"]":break
                    self.take(b",")
            self.take(b"]")
        elif ch==b'"':v=self.string()
        else:
            for token,val in ((b"true",True),(b"false",False),(b"null",None)):
                if self.raw.startswith(token,self.i):self.i+=len(token);v=val;break
            else:
                m=NUM.match(self.raw,self.i)
                if m is None:raise ValueError("INVALID_VALUE")
                self.i=m.end();v=json.loads(m.group().decode("ascii"))
                if type(v) is float and not math.isfinite(v):raise ValueError("NONFINITE")
        self.nodes[path]={"span":(s,self.i),"kind":kind(v),"value":v}
        return v
    def parse(self):
        v=self.value();self.ws()
        if self.i!=len(self.raw):raise ValueError("TRAILING")
        return v,self.nodes
def strict_decode(raw):
    def unique(pairs):
        d={}
        for k,v in pairs:
            if k in d:raise ValueError("DUPLICATE")
            d[k]=v
        return d
    def bad(x):raise ValueError("CONSTANT")
    return json.loads(raw.decode("utf-8"),object_pairs_hook=unique,parse_constant=bad)
def reference_leaves(v,path=()):
    if type(v) is dict:
        for k,x in v.items():yield from reference_leaves(x,path+(k,))
    elif type(v) is list:
        for i,x in enumerate(v):yield from reference_leaves(x,path+(i,))
    else:yield path,v
def path_match(verifier,nodes,query):
    parent=();stats={"neural_segments":0,"structural_segments":0,"neural_failures":0}
    for q in query:
        if parent not in nodes:return "missing",None,stats
        node=nodes[parent];typ=node["kind"]
        if (typ=="object" and type(q) is not str) or (typ=="array" and type(q) is not int) or typ not in ("object","array"):
            return "missing",None,stats
        children=[p[-1] for p in nodes if len(p)==len(parent)+1 and p[:-1]==parent]
        if typ=="object" and SHORT.fullmatch(q) and all(type(k) is str and SHORT.fullmatch(k) for k in children) and children:
            stats["neural_segments"]+=1
            a,b,la,lb,_=key_batch([(q,k,0) for k in children])
            with torch.inference_mode():z=verifier(a,b,la,lb)
            i=int(z.argmax());chosen=children[i] if float(z[i])>=0 else None
            expected=q if q in children else None
            # Exact structural proof independently checks learned selection.
            if chosen!=expected:
                stats["neural_failures"]+=1;return "reject",None,stats
            if chosen is None:return "missing",None,stats
        else:
            stats["structural_segments"]+=1
            if q not in children:return "missing",None,stats
        parent=parent+(q,)
    return "present",nodes[parent],stats
def copy_tokens(copier,raw,spans,T):
    # Original byte windows; spans use absolute byte offsets, no reserialized values.
    fs=[]
    for s,e in spans:
        lo=max(0,s-32);hi=min(len(raw),lo+127)
        if e>hi:lo=max(0,e-127);hi=e
        ids=[256]+list(raw[lo:hi]);fs.append((ids,(1+s-lo,e-lo)))
    results=[]
    for i in range(0,len(fs),32):
        part=fs[i:i+32];pred=decode(copier,part,T)
        for (ids,(s,e)),(out,stop,positions) in zip(part,pred):
            # Compare emitted positions AND raw bytes; never count a wrong
            # decoded token as correct merely due to Unicode replacement.
            exact=stop and positions==list(range(s,e+1)) and bytes(ids[p] for p in positions)==bytes(ids[s:e+1])
            results.append(exact)
    return results
def synthetic():
    return [b'{"left":{"value":19},"right":{"value":20},"rows":[{"value":31},{"value":32}],"null":null,"flag":false,"zero":0,"obj":{"0":9},"a/b":{"~key":"x"},"mix":[1,"1",true,null]}',
            '{"root":{"café":"Привет","date":"2026-11-25","id":"JANUS_R72A","neg":-5,"float":1.25,"exp":1e3},"long":"abcdefghijklmnopqrstuvwxyz0123456789"}'.encode("utf-8"),
            b'{"ab":{"abc":2,"abd":3},"ac":{"abc":4,"abd":5},"abc":1,"abd":2,"list":[{"ab":1},{"ab":2}]}']
def invalid():
    return [b'{"a":1,"a":2}',b'{"a":{"b":1,"b":2}}',b'{"a":01}',b'{"a":NaN}',b'{"a":Infinity}',b'{"a":1e999}',b'{"a":1,}',b'{"a":[1,]}',b'{"a":1}x',b'{"a":',b'{"a":"\\uD800"}',b'{"a":"\xff"}']
