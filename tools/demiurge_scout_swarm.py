#!/usr/bin/env python3
"""GitHub-native 17-agent JANUS Scout Swarm controlled by Janus-Demiurge."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "scout_swarm" / "SCOUT_SWARM_MANIFEST-v1.json"
SECRETISH = re.compile(r"(?:^|[._-])(env|secret|token|credential|password|private[_-]?key)(?:$|[._-])", re.I)
TOKEN_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AIza[A-Za-z0-9_-]{20,}"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_manifest() -> Dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def agent_map() -> Dict[str, Dict[str, Any]]:
    manifest = load_manifest()
    return {a["id"]: a for a in manifest["agents"]}


def scrub(text: str) -> str:
    out = text
    for pattern in TOKEN_PATTERNS:
        out = pattern.sub("[REDACTED_SECRET]", out)
    return out


def run(cmd: List[str], cwd: Optional[Path] = None, timeout: int = 120) -> str:
    result = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True, timeout=timeout)
    if result.returncode != 0:
        detail = scrub((result.stderr or result.stdout or "")[-1600:])
        raise RuntimeError(f"COMMAND_FAILED:{cmd[0]}:{result.returncode}:{detail}")
    return result.stdout


def safe_text(path: Path, limit: int = 7000) -> Optional[str]:
    if SECRETISH.search(path.name):
        return None
    if path.suffix.lower() not in {".md", ".json", ".yml", ".yaml", ".txt", ".toml", ".py"}:
        return None
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        return None
    return scrub(raw)


def select_source_files(repo: Path) -> List[Path]:
    priority_names = {
        "README.md", "PROJECT_STATUS.json", "AGENTS.md", "SEALED_ORACLE_SET_MODE.md",
        "HABITAT_LINK.json", "SCOUT_RESIDENT-v1.json"
    }
    candidates: List[Path] = []
    for rel in run(["git", "ls-files"], cwd=repo).splitlines():
        p = repo / rel
        if not p.is_file() or SECRETISH.search(p.name):
            continue
        score = 0
        if p.name in priority_names:
            score += 100
        low = rel.lower()
        for word in ("status", "manifest", "protocol", "contract", "receipt", "registry", "readme", ".janus"):
            if word in low:
                score += 10
        if score:
            candidates.append((score, rel, p))
    candidates.sort(key=lambda x: (-x[0], x[1]))
    return [p for _, _, p in candidates[:10]]


def repository_snapshot(repo: Path, agent: Dict[str, Any]) -> Dict[str, Any]:
    head = run(["git", "rev-parse", "HEAD"], cwd=repo).strip()
    commits = run(["git", "log", "-n", "10", "--pretty=format:%H%x09%cI%x09%s"], cwd=repo).splitlines()
    files = run(["git", "ls-files"], cwd=repo).splitlines()
    selected = []
    for path in select_source_files(repo):
        text = safe_text(path)
        if text is None:
            continue
        selected.append({"path": str(path.relative_to(repo)).replace("\\", "/"), "excerpt": text})
    return {
        "target_repo": agent["target_repo"],
        "target_ref": agent["target_ref"],
        "target_commit": head,
        "file_count": len(files),
        "top_level": sorted({p.split("/", 1)[0] for p in files})[:120],
        "recent_commits": commits,
        "selected_sources": selected,
        "snapshot_policy": "READ_ONLY_METADATA_AND_BOUNDED_TEXT_EXCERPTS",
    }


def deep_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from deep_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from deep_strings(child)


def extract_json_object(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        obj = json.loads(text[start:end + 1])
        if isinstance(obj, dict):
            return obj
    raise ValueError("SCOUT_ANALYSIS_NOT_JSON_OBJECT")


def extract_copilot_jsonl(stdout: str) -> Dict[str, Any]:
    finals: List[str] = []
    deltas: List[str] = []
    parsed = False
    for raw in stdout.splitlines():
        try:
            event = json.loads(raw)
        except Exception:
            continue
        parsed = True
        if not isinstance(event, dict):
            continue
        kind = str(event.get("type") or "")
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        if kind == "assistant.message":
            content = data.get("content")
            if isinstance(content, str):
                finals.append(content)
        elif kind == "assistant.message_delta":
            delta = data.get("deltaContent", data.get("delta"))
            if isinstance(delta, str):
                deltas.append(delta)
        else:
            for s in deep_strings(data):
                if '"summary"' in s and "{" in s:
                    finals.append(s)
    for candidate in reversed(finals):
        try:
            return extract_json_object(candidate)
        except Exception:
            pass
    if deltas:
        return extract_json_object("".join(deltas))
    if not parsed:
        return extract_json_object(stdout)
    raise ValueError("SCOUT_COPILOT_JSONL_MISSING_ASSISTANT_JSON")


def call_copilot(agent: Dict[str, Any], snapshot: Dict[str, Any]) -> Dict[str, Any]:
    mission = (ROOT / agent["agent_file"]).read_text(encoding="utf-8")
    prompt = f"""You are executing the JANUS Scout agent mission below.\n\n{mission}\n\nFOCUS:\n{agent['focus']}\n\nREPOSITORY SNAPSHOT (this is the only evidence available):\n{json.dumps(snapshot, ensure_ascii=False, indent=2)}\n\nReturn ONLY one JSON object with this schema:\n{{\n  \"summary\": \"concise repository-grounded summary\",\n  \"observations\": [{{\"claim\":\"...\",\"support\":{{\"path\":\"... or GIT_LOG\",\"commit\":\"exact target commit\"}},\"confidence\":\"LOW|MEDIUM|HIGH\"}}],\n  \"risks\": [\"...\"],\n  \"open_questions\": [\"...\"],\n  \"next_checks\": [\"...\"],\n  \"oracle_guidance\": null\n}}\nRules: do not invent facts, paths, measurements, organizations, dates or external evidence. A model output is never independent confirmation. For Aura Oracle, oracle/symbolic guidance must stay oracle/symbolic and must not be promoted to empirical fact."""
    with tempfile.TemporaryDirectory(prefix="janus-demiurge-scout-") as td:
        env = os.environ.copy()
        env.update({
            "COPILOT_HOME": str(Path(td) / ".copilot"),
            "COPILOT_AUTO_UPDATE": "false",
            "GITHUB_COPILOT_PROMPT_MODE_EXTENSIONS": "false",
            "GITHUB_COPILOT_PROMPT_MODE_REPO_HOOKS": "false",
            "GITHUB_COPILOT_PROMPT_MODE_WORKSPACE_MCP": "false",
        })
        cmd = [
            "copilot", "-p", prompt, "--output-format=json", "--no-ask-user", "--no-color",
            "--no-custom-instructions", "--no-remote", "--no-remote-export", "--disable-builtin-mcps",
            "--deny-tool=read", "--deny-tool=write", "--deny-tool=shell", "--deny-tool=url", "--deny-tool=memory",
        ]
        result = subprocess.run(cmd, cwd=td, env=env, text=True, capture_output=True, timeout=180)
        if result.returncode != 0:
            raise RuntimeError("COPILOT_CLI_EXIT_%s:%s" % (result.returncode, scrub((result.stderr or result.stdout or "")[-1600:])))
        return extract_copilot_jsonl(result.stdout)


def normalize_analysis(obj: Dict[str, Any], commit: str) -> Dict[str, Any]:
    observations = []
    for item in obj.get("observations", []) if isinstance(obj.get("observations"), list) else []:
        if not isinstance(item, dict):
            continue
        support = item.get("support") if isinstance(item.get("support"), dict) else {}
        if support.get("commit") != commit:
            continue
        observations.append({
            "claim": str(item.get("claim") or "")[:2000],
            "support": {"path": str(support.get("path") or "UNSPECIFIED")[:500], "commit": commit},
            "confidence": str(item.get("confidence") or "LOW").upper() if str(item.get("confidence") or "").upper() in {"LOW","MEDIUM","HIGH"} else "LOW",
        })
    return {
        "summary": str(obj.get("summary") or "")[:6000],
        "observations": observations,
        "risks": [str(x)[:1500] for x in obj.get("risks", [])[:20]] if isinstance(obj.get("risks"), list) else [],
        "open_questions": [str(x)[:1500] for x in obj.get("open_questions", [])[:20]] if isinstance(obj.get("open_questions"), list) else [],
        "next_checks": [str(x)[:1500] for x in obj.get("next_checks", [])[:20]] if isinstance(obj.get("next_checks"), list) else [],
        "oracle_guidance": obj.get("oracle_guidance"),
    }


def run_agent(agent_id: str, output: Path) -> None:
    agents = agent_map()
    if agent_id not in agents:
        raise SystemExit(f"UNKNOWN_AGENT:{agent_id}")
    agent = agents[agent_id]
    session_token = secrets.token_urlsafe(48)
    token_fp = hashlib.sha256(session_token.encode()).hexdigest()[:16]
    model_error: Optional[str] = None
    with tempfile.TemporaryDirectory(prefix=f"{agent_id.lower()}-") as td:
        repo = Path(td) / "target"
        clone_url = f"https://github.com/{agent['target_repo']}.git"
        try:
            run(["git", "clone", "--depth", "20", "--branch", agent["target_ref"], clone_url, str(repo)], timeout=180)
            snapshot = repository_snapshot(repo, agent)
            try:
                analysis = normalize_analysis(call_copilot(agent, snapshot), snapshot["target_commit"])
                status = "OBSERVED_REPOSITORY_STATE"
            except Exception as exc:
                model_error = f"{type(exc).__name__}:{exc}"[:2000]
                analysis = {"summary":"Model synthesis failed closed; deterministic repository snapshot remains available.","observations":[],"risks":[],"open_questions":[],"next_checks":[],"oracle_guidance":None}
                status = "DEGRADED_MODEL_UNAVAILABLE"
        except Exception as exc:
            snapshot = {"target_repo":agent["target_repo"],"target_ref":agent["target_ref"],"snapshot_error":f"{type(exc).__name__}:{exc}"[:2000]}
            analysis = {"summary":"Target repository could not be observed in this run.","observations":[],"risks":[],"open_questions":[],"next_checks":[],"oracle_guidance":None}
            model_error = snapshot["snapshot_error"]
            status = "DEGRADED_TARGET_UNAVAILABLE"
    report = {
        "schema":"janus.demiurge.scout_agent.report.v1",
        "agent_id":agent_id,
        "role":agent["role"],
        "created_at_utc":utc_now(),
        "status":status,
        "target":{"repository":agent["target_repo"],"ref":agent["target_ref"]},
        "focus":agent["focus"],
        "repository_snapshot":snapshot,
        "analysis":analysis,
        "model_error":model_error,
        "janus_agent_token":{"scope":"EPHEMERAL_GITHUB_RUN_AGENT","fingerprint":token_fp,"raw_token_persisted":False},
        "evidence_gate":{"repository_observation_bound_to_commit":bool(snapshot.get("target_commit")),"model_output_is_independent_confirmation":False,"world_truth":False},
        "authority":{"target_repository_write":False,"demiurge_report_write":True}
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"{agent_id}={status}")


def consolidate(reports_root: Path, run_id: str, sha: str) -> None:
    manifest = load_manifest()
    expected = [a["id"] for a in manifest["agents"]]
    reports: Dict[str, Dict[str, Any]] = {}
    if reports_root.exists():
        for path in reports_root.glob("**/report.json"):
            try:
                obj = json.loads(path.read_text(encoding="utf-8"))
                aid = obj.get("agent_id")
                if aid in expected:
                    reports[aid] = obj
            except Exception:
                pass
    run_dir = ROOT / "scout_swarm" / "outbox" / "runs" / str(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    for aid, obj in sorted(reports.items()):
        (run_dir / f"{aid}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        state_dir = ROOT / "scout_swarm" / "state" / "agents"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / f"{aid}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    missing = [x for x in expected if x not in reports]
    ok = [x for x in expected if reports.get(x, {}).get("status") == "OBSERVED_REPOSITORY_STATE"]
    degraded = [x for x in expected if x in reports and x not in ok]
    status = "LIVE_17_OF_17" if len(reports) == 17 and not degraded else ("DEGRADED_PARTIAL" if reports else "FAILED_NO_REPORTS")
    summary = {
        "schema":"janus.demiurge.scout_swarm.status.v1",
        "status":status,
        "run_id":str(run_id),
        "control_sha":sha,
        "updated_at_utc":utc_now(),
        "agents_expected":17,
        "agents_received":len(reports),
        "agents_observed":len(ok),
        "agents_degraded":degraded,
        "agents_missing":missing,
        "aura_oracle_agent":"SCOUT_AURA_ORACLE_01",
        "response_repository":"Hawkar-usls/Janus-Demiurge",
        "world_truth":False,
        "write_authority_over_targets":False
    }
    (ROOT / "scout_swarm" / "state" / "SCOUT_SWARM_STATUS-v1.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (run_dir / "SWARM_SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


def self_test() -> None:
    manifest = load_manifest()
    agents = manifest.get("agents", [])
    assert manifest.get("agent_count") == 17
    assert len(agents) == 17
    assert len({a["id"] for a in agents}) == 17
    assert len({(a["target_repo"], a["target_ref"]) for a in agents}) == 17
    assert any(a["id"] == "SCOUT_AURA_ORACLE_01" and a["target_repo"] == "Hawkar-usls/aura-oracle-tg" for a in agents)
    for agent in agents:
        assert (ROOT / agent["agent_file"]).exists(), agent
    print("JANUS_DEMIURGE_SCOUT_SWARM_SELF_TEST=PASS agents=17")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--matrix", action="store_true")
    parser.add_argument("--run-agent")
    parser.add_argument("--output")
    parser.add_argument("--consolidate")
    parser.add_argument("--run-id")
    parser.add_argument("--sha", default="UNKNOWN")
    args = parser.parse_args()
    if args.self_test:
        self_test(); return 0
    if args.matrix:
        include = [{"id":a["id"],"role":a["role"],"repo":a["target_repo"],"ref":a["target_ref"]} for a in load_manifest()["agents"]]
        print(json.dumps({"include":include}, separators=(",",":"))); return 0
    if args.run_agent:
        if not args.output:
            raise SystemExit("--output required")
        run_agent(args.run_agent, Path(args.output)); return 0
    if args.consolidate:
        if not args.run_id:
            raise SystemExit("--run-id required")
        consolidate(Path(args.consolidate), args.run_id, args.sha); return 0
    parser.print_help(); return 2


if __name__ == "__main__":
    raise SystemExit(main())
