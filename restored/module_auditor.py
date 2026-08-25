from __future__ import annotations
import ast, hashlib
from typing import Any

SCHEMA="janus.module_audit.receipt.v1"
FORBIDDEN_IMPORT_ROOTS={"subprocess","socket","ctypes"}
FORBIDDEN_CALLS={
    "eval","exec","compile","__import__","input",
    "os.system","os.popen","sys.exit","shutil.rmtree",
    "subprocess.call","subprocess.Popen"
}
BARE_MARKERS={"python","py"}

def _call_name(node: ast.Call) -> str|None:
    if isinstance(node.func,ast.Name): return node.func.id
    if isinstance(node.func,ast.Attribute):
        parts=[]; cur=node.func
        while isinstance(cur,ast.Attribute):
            parts.append(cur.attr); cur=cur.value
        if isinstance(cur,ast.Name):
            parts.append(cur.id); return ".".join(reversed(parts))
    return None

def audit_source(source:str)->dict[str,Any]:
    sha=hashlib.sha256(source.encode("utf-8")).hexdigest()
    findings=[]
    try:
        tree=ast.parse(source)
    except SyntaxError as e:
        return {"schema":SCHEMA,"source_sha256":sha,"status":"REJECT","findings":[{"kind":"SYNTAX","line":e.lineno,"message":e.msg}]}
    has_async_run=False
    for node in ast.walk(tree):
        if isinstance(node,ast.AsyncFunctionDef) and node.name=="run":
            args=[a.arg for a in node.args.args]
            if args and args[0]=="core": has_async_run=True
        if isinstance(node,(ast.Import,ast.ImportFrom)):
            names=[]
            if isinstance(node,ast.Import): names=[a.name.split(".")[0] for a in node.names]
            elif node.module: names=[node.module.split(".")[0]]
            for name in names:
                if name in FORBIDDEN_IMPORT_ROOTS:
                    findings.append({"kind":"FORBIDDEN_IMPORT","name":name,"line":getattr(node,"lineno",None)})
        if isinstance(node,ast.Call):
            fn=_call_name(node)
            if fn in FORBIDDEN_CALLS:
                findings.append({"kind":"FORBIDDEN_CALL","name":fn,"line":getattr(node,"lineno",None)})
        if isinstance(node,ast.Expr) and isinstance(node.value,ast.Name) and node.value.id in BARE_MARKERS:
            findings.append({"kind":"BARE_LANGUAGE_MARKER","name":node.value.id,"line":getattr(node,"lineno",None)})
    if not has_async_run:
        findings.append({"kind":"ABI_MISSING","required":"async def run(core)"})
    return {"schema":SCHEMA,"source_sha256":sha,"status":"PASS_STATIC" if not findings else "REJECT",
            "findings":findings,
            "boundary":"STATIC_ANALYSIS_ONLY_NOT_RUNTIME_OR_SECURITY_PROOF"}
