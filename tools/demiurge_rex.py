#!/usr/bin/env python3
from __future__ import annotations
import argparse, ast, hashlib, json, os, pathlib, py_compile, re, subprocess, sys, tempfile
from typing import Any

SPEC_SCHEMA = "janus.rex.module_spec.v1"
POLICY_SCHEMA = "janus.rex.policy.v1"
MODULE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
FORBIDDEN_NAMES = {"open","exec","eval","compile","__import__","input","breakpoint","globals","locals","vars","getattr","setattr","delattr","help"}
ALLOWED_CALL_NAMES = {"isinstance","dict","list","str","int","float","bool","len","sorted","TypeError"}
ALLOWED_METHOD_CALLS = {"get","update","keys"}


def cjson(obj: Any) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: pathlib.Path) -> str:
    return sha_bytes(path.read_bytes())


def load(path: pathlib.Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"{path}: expected JSON object")
    return obj


def validate_spec(policy: dict[str, Any], spec: dict[str, Any]) -> None:
    if policy.get("schema") != POLICY_SCHEMA:
        raise ValueError("unsupported policy schema")
    if spec.get("schema") != SPEC_SCHEMA:
        raise ValueError("unsupported module spec schema")
    mid = spec.get("module_id")
    if not isinstance(mid, str) or not MODULE_ID_RE.fullmatch(mid):
        raise ValueError("invalid module_id")
    limits = policy["limits"]
    purpose = spec.get("purpose")
    if not isinstance(purpose, str) or not purpose.strip() or len(purpose) > limits["max_purpose_length"]:
        raise ValueError("invalid purpose")
    version = spec.get("version")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("version must be x.y.z")
    template = spec.get("template")
    if template not in policy.get("allowed_templates", []):
        raise ValueError("template not allowed")
    cfg = spec.get("config", {})
    if not isinstance(cfg, dict):
        raise ValueError("config must be object")
    if "message" in cfg and (not isinstance(cfg["message"], str) or len(cfg["message"]) > limits["max_message_length"]):
        raise ValueError("invalid message")
    if template == "json_projection":
        keys = cfg.get("keys", [])
        constants = cfg.get("constants", {})
        if not isinstance(keys, list) or len(keys) > limits["max_projection_keys"] or not all(isinstance(x, str) and x for x in keys):
            raise ValueError("invalid keys")
        if not isinstance(constants, dict) or len(constants) > limits["max_constants"]:
            raise ValueError("invalid constants")
        json.dumps(constants, ensure_ascii=False)


def render(spec: dict[str, Any]) -> str:
    meta = {
        "schema": "janus.rex.generated_module.v1",
        "module_id": spec["module_id"],
        "version": spec["version"],
        "purpose": spec["purpose"],
        "template": spec["template"],
        "authority": "NONE__NEXUS_ADMISSION_REQUIRED",
    }
    cfg = spec.get("config", {})
    template = spec["template"]
    lines = [
        "# Generated deterministically by JANUS Rex v1. Do not hand-edit.",
        f"MODULE_META = {meta!r}",
        "",
        "async def run(context):",
        "    if not isinstance(context, dict):",
        "        raise TypeError('context must be dict')",
    ]
    if template == "heartbeat":
        lines += [
            "    return {",
            "        'status': 'ALIVE',",
            f"        'message': {cfg.get('message','JANUS REX HEARTBEAT')!r},",
            "        'module_id': MODULE_META['module_id'],",
            "        'authority_delta': 0,",
            "    }",
        ]
    elif template == "echo":
        lines += [
            "    return {",
            "        'status': 'OK',",
            f"        'message': {cfg.get('message','')!r},",
            "        'input': context,",
            "        'authority_delta': 0,",
            "    }",
        ]
    elif template == "json_projection":
        lines += [
            f"    keys = {list(cfg.get('keys',[]))!r}",
            f"    constants = {dict(cfg.get('constants',{}))!r}",
            "    out = {key: context.get(key) for key in keys if key in context}",
            "    out.update(constants)",
            "    return {'status': 'OK', 'projection': out, 'authority_delta': 0}",
        ]
    elif template == "ledger_summary":
        lines += [
            "    rows = context.get('rows', [])",
            "    if not isinstance(rows, list):",
            "        raise TypeError('context.rows must be list')",
            "    dict_rows = [row for row in rows if isinstance(row, dict)]",
            "    keys = sorted({key for row in dict_rows for key in row.keys() if isinstance(key, str)})",
            "    return {'status': 'OK', 'row_count': len(rows), 'dict_row_count': len(dict_rows), 'keys': keys, 'authority_delta': 0}",
        ]
    return "\n".join(lines) + "\n"


def cmd_build(a: argparse.Namespace) -> int:
    policy = load(pathlib.Path(a.policy))
    spec = load(pathlib.Path(a.spec))
    validate_spec(policy, spec)
    source = render(spec).encode()
    if len(source) > policy["limits"]["max_source_bytes"]:
        raise SystemExit("source too large")
    cdir = pathlib.Path(a.out_root) / spec["module_id"]
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "module.py").write_bytes(source)
    manifest = {
        "schema": "janus.rex.candidate.v1",
        "module_id": spec["module_id"],
        "version": spec["version"],
        "template": spec["template"],
        "spec_path": pathlib.Path(a.spec).as_posix(),
        "spec_sha256": sha_bytes(cjson(spec)),
        "policy_sha256": sha_bytes(cjson(policy)),
        "source_sha256": sha_bytes(source),
        "source_bytes": len(source),
        "state": "CANDIDATE__NOT_ADMITTED",
        "authority_delta": 0,
        "law": "REX_CAN_CREATE_NE_REX_CAN_CROWN",
    }
    (cdir / "candidate.json").write_bytes(cjson(manifest))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


def audit_ast(tree: ast.AST) -> list[str]:
    errors: list[str] = []
    runs = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            errors.append("imports are forbidden")
        if isinstance(n, (ast.Global, ast.Nonlocal)):
            errors.append("global/nonlocal are forbidden")
        if isinstance(n, ast.Attribute) and n.attr.startswith("__"):
            errors.append(f"dunder attribute forbidden: {n.attr}")
        if isinstance(n, ast.Name) and n.id in FORBIDDEN_NAMES:
            errors.append(f"forbidden name: {n.id}")
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Name) and n.func.id not in ALLOWED_CALL_NAMES:
                errors.append(f"call forbidden: {n.func.id}")
            elif isinstance(n.func, ast.Attribute) and n.func.attr not in ALLOWED_METHOD_CALLS:
                errors.append(f"method call forbidden: {n.func.attr}")
            elif not isinstance(n.func, (ast.Name, ast.Attribute)):
                errors.append("indirect call forbidden")
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "run":
            runs.append(n)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name != "run":
            errors.append(f"extra function forbidden: {n.name}")
        if isinstance(n, (ast.ClassDef, ast.Lambda, ast.With, ast.AsyncWith, ast.Try, ast.Delete)):
            errors.append(f"node forbidden: {type(n).__name__}")
    if len(runs) != 1:
        errors.append("exactly one async run(context) required")
    elif len(runs[0].args.args) != 1 or runs[0].args.args[0].arg != "context" or runs[0].args.vararg or runs[0].args.kwarg or runs[0].args.kwonlyargs:
        errors.append("run ABI must be async def run(context)")
    return sorted(set(errors))


def cmd_audit(a: argparse.Namespace) -> int:
    cdir = pathlib.Path(a.candidate_dir)
    source = cdir / "module.py"
    candidate = cdir / "candidate.json"
    c = load(candidate)
    errors: list[str] = []
    actual = sha(source)
    if c.get("source_sha256") != actual:
        errors.append("candidate source SHA mismatch")
    try:
        errors += audit_ast(ast.parse(source.read_text(encoding="utf-8"), filename=str(source)))
    except SyntaxError as e:
        errors.append(f"syntax: {e}")
    if not errors:
        with tempfile.TemporaryDirectory() as td:
            try:
                py_compile.compile(str(source), cfile=str(pathlib.Path(td) / "m.pyc"), doraise=True)
            except py_compile.PyCompileError as e:
                errors.append(f"py_compile: {e}")
    receipt = {
        "schema": "janus.rex.audit_receipt.v1",
        "module_id": c.get("module_id"),
        "source_sha256": actual,
        "candidate_manifest_sha256": sha(candidate),
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "admission": "NOT_GRANTED",
        "authority_delta": 0,
        "law": "AUDIT_PASS_NE_ADMISSION",
    }
    out = pathlib.Path(a.receipt) if a.receipt else cdir / "audit.json"
    out.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


def cmd_admit(a: argparse.Namespace) -> int:
    cdir = pathlib.Path(a.candidate_dir)
    source = cdir / "module.py"
    c = load(cdir / "candidate.json")
    audit = load(cdir / "audit.json")
    actual = sha(source)
    if audit.get("status") != "PASS":
        raise SystemExit("NEXUS REFUSED: audit is not PASS")
    if c.get("source_sha256") != actual or audit.get("source_sha256") != actual:
        raise SystemExit("NEXUS REFUSED: source SHA mismatch")
    if a.source_sha256 != actual:
        raise SystemExit("NEXUS REFUSED: explicit expected source SHA mismatch")
    if a.authority != "EXPLICIT_EXTERNAL_GATE":
        raise SystemExit("NEXUS REFUSED: Rex cannot self-authorize")
    outdir = pathlib.Path(a.admissions_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"{c['module_id']}.json"
    admission = {
        "schema": "janus.nexus.rex_admission.v1",
        "module_id": c["module_id"],
        "version": c["version"],
        "source_sha256": actual,
        "candidate_manifest_sha256": sha(cdir / "candidate.json"),
        "audit_receipt_sha256": sha(cdir / "audit.json"),
        "authority": "EXPLICIT_EXTERNAL_GATE",
        "state": "ADMITTED_EXACT_SHA",
        "authority_delta": 0,
        "law": "REX_CAN_CREATE_NE_REX_CAN_CROWN",
    }
    if out.exists() and load(out) != admission:
        raise SystemExit("NEXUS REFUSED: admission exists with different binding")
    out.write_text(json.dumps(admission, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(admission, ensure_ascii=False, indent=2))
    return 0


def runner_source() -> str:
    return """import asyncio,importlib.util,json,pathlib,sys\np=pathlib.Path(sys.argv[1]).resolve(); i=pathlib.Path(sys.argv[2]).resolve()\ns=importlib.util.spec_from_file_location('janus_rex_admitted_module',p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)\nc=json.loads(i.read_text(encoding='utf-8'))\nif not isinstance(c,dict): raise SystemExit('input must be JSON object')\nr=asyncio.run(m.run(c)); print(json.dumps(r,ensure_ascii=False,sort_keys=True))\n"""


def cmd_run(a: argparse.Namespace) -> int:
    cdir = pathlib.Path(a.candidate_dir)
    c = load(cdir / "candidate.json")
    source = cdir / "module.py"
    admission = load(pathlib.Path(a.admissions_dir) / f"{c['module_id']}.json")
    actual = sha(source)
    if admission.get("state") != "ADMITTED_EXACT_SHA" or admission.get("source_sha256") != actual:
        raise SystemExit("NEXUS REFUSED: current source is not admitted")
    payload = pathlib.Path(a.input)
    raw = payload.read_bytes()
    if len(raw) > a.max_input_bytes:
        raise SystemExit("input exceeds bounded size")
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    with tempfile.TemporaryDirectory() as td:
        runner = pathlib.Path(td) / "runner.py"
        runner.write_text(runner_source(), encoding="utf-8")
        p = subprocess.run([sys.executable, "-I", "-S", "-B", str(runner), str(source.resolve()), str(payload.resolve())], cwd=td, env=env, text=True, capture_output=True, timeout=a.timeout)
    if p.returncode:
        sys.stderr.write(p.stderr)
        return p.returncode
    print(p.stdout.strip())
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="JANUS Demiurge Rex v1: bounded organogenesis + Auditor + Nexus")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--policy", default="rex/policy.json")
    b.add_argument("--spec", required=True)
    b.add_argument("--out-root", default="rex/candidates")
    b.set_defaults(fn=cmd_build)
    u = sub.add_parser("audit")
    u.add_argument("--candidate-dir", required=True)
    u.add_argument("--receipt")
    u.set_defaults(fn=cmd_audit)
    d = sub.add_parser("admit")
    d.add_argument("--candidate-dir", required=True)
    d.add_argument("--admissions-dir", default="rex/admissions")
    d.add_argument("--source-sha256", required=True)
    d.add_argument("--authority", required=True)
    d.set_defaults(fn=cmd_admit)
    r = sub.add_parser("run")
    r.add_argument("--candidate-dir", required=True)
    r.add_argument("--admissions-dir", default="rex/admissions")
    r.add_argument("--input", required=True)
    r.add_argument("--timeout", type=int, default=8)
    r.add_argument("--max-input-bytes", type=int, default=100000)
    r.set_defaults(fn=cmd_run)
    a = ap.parse_args()
    return int(a.fn(a))


if __name__ == "__main__":
    raise SystemExit(main())