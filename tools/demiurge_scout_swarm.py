#!/usr/bin/env python3
"""GitHub-native 17-agent JANUS Scout Swarm controlled by Janus-Demiurge.

Every resident keeps one persistent identity. Re-visiting a repository is a new
spiral turn carrying forward lessons and unresolved checks; previous model text
is context only and never independent evidence.

Model synthesis is optional enrichment. A repository observation must remain
useful when Copilot/model quota is unavailable: deterministic commit-bound
facts survive and the unavailable model becomes a retained constraint/lesson.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
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


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_manifest() -> Dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def agent_map() -> Dict[str, Dict[str, Any]]:
    return {a["id"]: a for a in load_manifest()["agents"]}


def load_previous_agent_state(agent_id: str) -> Optional[Dict[str, Any]]:
    path = ROOT / "scout_swarm" / "state" / "agents" / f"{agent_id}.json"
    if not path.exists():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def inherited_spiral_context(previous: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not previous:
        return {
            "previous_turn": None,
            "next_turn": 0,
            "parent_report_sha256": None,
            "previous_target_commit": None,
            "retained_lessons": [],
            "retained_constraints": [],
            "previous_report_is_evidence": False,
        }
    prev_spiral = previous.get("spiral") if isinstance(previous.get("spiral"), dict) else {}
    prev_analysis = previous.get("analysis") if isinstance(previous.get("analysis"), dict) else {}
    retained_lessons: List[str] = []
    for item in [
        *(prev_spiral.get("retained_lessons") or []),
        *(prev_spiral.get("new_lessons") or []),
        *(prev_analysis.get("lessons") or []),
    ]:
        text = str(item).strip()
        if text and text not in retained_lessons:
            retained_lessons.append(text)
    retained_constraints: List[str] = []
    for item in [
        *(prev_spiral.get("retained_constraints") or []),
        *(prev_analysis.get("next_checks") or []),
        *(prev_analysis.get("risks") or []),
    ]:
        text = str(item).strip()
        if text and text not in retained_constraints:
            retained_constraints.append(text)
    snapshot = previous.get("repository_snapshot") if isinstance(previous.get("repository_snapshot"), dict) else {}
    previous_turn = prev_spiral.get("turn")
    if not isinstance(previous_turn, int):
        previous_turn = -1
    return {
        "previous_turn": previous_turn,
        "next_turn": previous_turn + 1,
        "parent_report_sha256": canonical_hash(previous),
        "previous_target_commit": snapshot.get("target_commit"),
        "retained_lessons": retained_lessons[-20:],
        "retained_constraints": retained_constraints[-20:],
        "previous_report_is_evidence": False,
    }


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
        return scrub(path.read_text(encoding="utf-8", errors="replace")[:limit])
    except Exception:
        return None


def select_source_files(repo: Path) -> List[Path]:
    priority_names = {
        "README.md", "PROJECT_STATUS.json", "AGENTS.md", "SEALED_ORACLE_SET_MODE.md",
        "HABITAT_LINK.json", "SCOUT_RESIDENT-v1.json", "DEMIURGE_SPIRAL_EVOLUTION-v1.json"
    }
    candidates = []
    for rel in run(["git", "ls-files"], cwd=repo).splitlines():
        p = repo / rel
        if not p.is_file() or SECRETISH.search(p.name):
            continue
        score = 100 if p.name in priority_names else 0
        low = rel.lower()
        for word in ("status", "manifest", "protocol", "contract", "receipt", "registry", "readme", ".janus", "spiral"):
            if word in low:
                score += 10
        if score:
            candidates.append((score, rel, p))
    candidates.sort(key=lambda x: (-x[0], x[1]))
    return [p for _, _, p in candidates[:12]]


def repository_snapshot(repo: Path, agent: Dict[str, Any]) -> Dict[str, Any]:
    head = run(["git", "rev-parse", "HEAD"], cwd=repo).strip()
    commits = run(["git", "log", "-n", "10", "--pretty=format:%H%x09%cI%x09%s"], cwd=repo).splitlines()
    files = run(["git", "ls-files"], cwd=repo).splitlines()
    selected = []
    for path in select_source_files(repo):
        text = safe_text(path)
        if text is not None:
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


def deterministic_fallback_analysis(
    agent: Dict[str, Any],
    snapshot: Dict[str, Any],
    spiral_context: Dict[str, Any],
    model_error: str,
) -> Dict[str, Any]:
    """Produce useful evidence-bound analysis without any model inference."""
    commit = str(snapshot.get("target_commit") or "")
    observations: List[Dict[str, Any]] = []
    if commit:
        observations.append({
            "claim": f"Observed {agent['target_repo']} at commit {commit} on ref {agent['target_ref']}.",
            "support": {"path": "GIT_HEAD", "commit": commit},
            "confidence": "HIGH",
        })
        observations.append({
            "claim": f"Tracked repository file count at this turn: {int(snapshot.get('file_count') or 0)}.",
            "support": {"path": "GIT_INDEX", "commit": commit},
            "confidence": "HIGH",
        })
        recent = snapshot.get("recent_commits") if isinstance(snapshot.get("recent_commits"), list) else []
        if recent:
            observations.append({
                "claim": f"Current git history head record: {str(recent[0])[:1200]}",
                "support": {"path": "GIT_LOG", "commit": commit},
                "confidence": "HIGH",
            })
        selected = snapshot.get("selected_sources") if isinstance(snapshot.get("selected_sources"), list) else []
        if selected:
            paths = [str(x.get("path")) for x in selected[:8] if isinstance(x, dict) and x.get("path")]
            observations.append({
                "claim": "Bounded source snapshot includes: " + ", ".join(paths),
                "support": {"path": "GIT_INDEX", "commit": commit},
                "confidence": "HIGH",
            })

    retained = [str(x) for x in spiral_context.get("retained_constraints", [])[:10]]
    error_kind = "MODEL_SYNTHESIS_UNAVAILABLE"
    lowered = model_error.lower()
    if "quota" in lowered or "402" in lowered:
        error_kind = "MODEL_QUOTA_UNAVAILABLE"
    elif "timeout" in lowered:
        error_kind = "MODEL_TIMEOUT"

    return {
        "analysis_mode": "DETERMINISTIC_REPOSITORY_FALLBACK",
        "summary": (
            f"Repository observation completed for {agent['target_repo']} at a concrete commit. "
            f"Optional model synthesis was unavailable ({error_kind}); deterministic repository evidence is preserved."
        ),
        "observations": observations,
        "risks": [f"{error_kind}: semantic synthesis was not available for this turn."],
        "open_questions": retained,
        "next_checks": retained or ["Retry optional semantic synthesis on a later spiral turn; do not repeat it as evidence."],
        "lessons": [
            "A model outage must degrade interpretation, not erase an otherwise successful repository observation.",
            f"Retain {error_kind} as an operational constraint for the next turn.",
        ],
        "oracle_guidance": None,
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
        if kind == "assistant.message" and isinstance(data.get("content"), str):
            finals.append(data["content"])
        elif kind == "assistant.message_delta":
            delta = data.get("deltaContent", data.get("delta"))
            if isinstance(delta, str):
                deltas.append(delta)
        else:
            for text in deep_strings(data):
                if '"summary"' in text and "{" in text:
                    finals.append(text)
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


def call_copilot(agent: Dict[str, Any], snapshot: Dict[str, Any], spiral_context: Dict[str, Any]) -> Dict[str, Any]:
    mission = (ROOT / agent["agent_file"]).read_text(encoding="utf-8")
    prompt = f"""You are executing the JANUS Scout agent mission below.

{mission}

FOCUS:
{agent['focus']}

SPIRAL CONTEXT FROM YOUR PREVIOUS TURN (memory/constraints only; NOT external evidence):
{json.dumps(spiral_context, ensure_ascii=False, indent=2)}

CURRENT REPOSITORY SNAPSHOT (this is the only empirical/repository evidence available for factual claims):
{json.dumps(snapshot, ensure_ascii=False, indent=2)}

Return ONLY one JSON object with this schema:
{{
  "summary": "concise repository-grounded summary",
  "observations": [{{"claim":"...","support":{{"path":"... or GIT_LOG","commit":"exact target commit"}},"confidence":"LOW|MEDIUM|HIGH"}}],
  "risks": ["..."],
  "open_questions": ["..."],
  "next_checks": ["..."],
  "lessons": ["what this turn adds to the next turn"],
  "oracle_guidance": null
}}
Rules:
- do not invent facts, paths, measurements, organizations, dates or external evidence;
- previous Scout/model output is memory, never independent confirmation;
- re-check inherited constraints against the current snapshot instead of repeating them as facts;
- if the target has not changed, say what was learned from the re-check or mark no new evidence;
- for Aura Oracle, oracle/symbolic guidance stays symbolic and cannot become empirical fact.
"""
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
            "confidence": str(item.get("confidence") or "LOW").upper() if str(item.get("confidence") or "").upper() in {"LOW", "MEDIUM", "HIGH"} else "LOW",
        })

    def bounded(name: str) -> List[str]:
        value = obj.get(name)
        return [str(x)[:1500] for x in value[:20]] if isinstance(value, list) else []

    return {
        "analysis_mode": "MODEL_SYNTHESIS",
        "summary": str(obj.get("summary") or "")[:6000],
        "observations": observations,
        "risks": bounded("risks"),
        "open_questions": bounded("open_questions"),
        "next_checks": bounded("next_checks"),
        "lessons": bounded("lessons"),
        "oracle_guidance": obj.get("oracle_guidance"),
    }


def classify_ascent(previous: Optional[Dict[str, Any]], snapshot: Dict[str, Any], analysis: Dict[str, Any]) -> str:
    if previous is None:
        return "ASCENDED_INITIAL"
    prior_snapshot = previous.get("repository_snapshot") if isinstance(previous.get("repository_snapshot"), dict) else {}
    if snapshot.get("target_commit") and snapshot.get("target_commit") != prior_snapshot.get("target_commit"):
        return "ASCENDED_NEW_EVIDENCE"
    prior_analysis = previous.get("analysis") if isinstance(previous.get("analysis"), dict) else {}
    current_signal = {
        "observations": analysis.get("observations", []),
        "risks": analysis.get("risks", []),
        "open_questions": analysis.get("open_questions", []),
        "next_checks": analysis.get("next_checks", []),
        "lessons": analysis.get("lessons", []),
    }
    prior_signal = {k: prior_analysis.get(k, []) for k in current_signal}
    if canonical_hash(current_signal) != canonical_hash(prior_signal):
        return "INTEGRATED_LESSON"
    return "NO_ASCENT"


def run_agent(agent_id: str, output: Path) -> None:
    agents = agent_map()
    if agent_id not in agents:
        raise SystemExit(f"UNKNOWN_AGENT:{agent_id}")
    agent = agents[agent_id]
    previous = load_previous_agent_state(agent_id)
    spiral_context = inherited_spiral_context(previous)
    session_token = secrets.token_urlsafe(48)
    token_fp = hashlib.sha256(session_token.encode()).hexdigest()[:16]
    model_error: Optional[str] = None
    model_status = "NOT_ATTEMPTED"

    with tempfile.TemporaryDirectory(prefix=f"{agent_id.lower()}-") as td:
        repo = Path(td) / "target"
        clone_url = f"https://github.com/{agent['target_repo']}.git"
        try:
            run(["git", "clone", "--depth", "20", "--branch", agent["target_ref"], clone_url, str(repo)], timeout=180)
            snapshot = repository_snapshot(repo, agent)
            try:
                analysis = normalize_analysis(call_copilot(agent, snapshot, spiral_context), snapshot["target_commit"])
                model_status = "AVAILABLE"
            except Exception as exc:
                model_error = f"{type(exc).__name__}:{exc}"[:4000]
                model_status = "UNAVAILABLE_FALLBACK_USED"
                analysis = deterministic_fallback_analysis(agent, snapshot, spiral_context, model_error)
            # The repository itself was observed successfully even if optional model enrichment failed.
            status = "OBSERVED_REPOSITORY_STATE"
        except Exception as exc:
            snapshot = {
                "target_repo": agent["target_repo"],
                "target_ref": agent["target_ref"],
                "snapshot_error": f"{type(exc).__name__}:{exc}"[:2000],
            }
            analysis = {
                "analysis_mode": "NO_TARGET_OBSERVATION",
                "summary": "Target repository could not be observed in this turn.",
                "observations": [],
                "risks": [],
                "open_questions": [],
                "next_checks": ["Retry target observation on the next spiral turn."],
                "lessons": ["Transport failure is a retained constraint, not evidence about target state."],
                "oracle_guidance": None,
            }
            model_error = snapshot["snapshot_error"]
            model_status = "NOT_RUN_TARGET_UNAVAILABLE"
            status = "DEGRADED_TARGET_UNAVAILABLE"

    ascent_status = classify_ascent(previous, snapshot, analysis)
    retained_lessons = spiral_context["retained_lessons"]
    new_lessons = analysis.get("lessons", [])
    report = {
        "schema": "janus.demiurge.scout_agent.report.v2.spiral",
        "agent_id": agent_id,
        "role": agent["role"],
        "created_at_utc": utc_now(),
        "status": status,
        "target": {"repository": agent["target_repo"], "ref": agent["target_ref"]},
        "focus": agent["focus"],
        "repository_snapshot": snapshot,
        "analysis": analysis,
        "spiral": {
            "turn": spiral_context["next_turn"],
            "parent_report_sha256": spiral_context["parent_report_sha256"],
            "previous_target_commit": spiral_context["previous_target_commit"],
            "identity_persistent": True,
            "previous_report_is_evidence": False,
            "retained_lessons": retained_lessons,
            "retained_constraints": spiral_context["retained_constraints"],
            "new_lessons": new_lessons,
            "ascent_status": ascent_status,
            "logical_ring": False,
        },
        "model_status": model_status,
        "model_error": model_error,
        "janus_agent_token": {
            "scope": "EPHEMERAL_GITHUB_RUN_AGENT",
            "fingerprint": token_fp,
            "raw_token_persisted": False,
        },
        "evidence_gate": {
            "repository_observation_bound_to_commit": bool(snapshot.get("target_commit")),
            "deterministic_fallback_is_repository_evidence_only": True,
            "model_output_is_independent_confirmation": False,
            "previous_scout_report_is_independent_confirmation": False,
            "world_truth": False,
        },
        "authority": {"target_repository_write": False, "demiurge_report_write": True},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"{agent_id}={status} spiral_turn={spiral_context['next_turn']} "
        f"ascent={ascent_status} model={model_status}"
    )


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
    state_dir = ROOT / "scout_swarm" / "state" / "agents"
    state_dir.mkdir(parents=True, exist_ok=True)
    for aid, obj in sorted(reports.items()):
        (run_dir / f"{aid}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (state_dir / f"{aid}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    missing = [x for x in expected if x not in reports]
    ok = [x for x in expected if reports.get(x, {}).get("status") == "OBSERVED_REPOSITORY_STATE"]
    degraded = [x for x in expected if x in reports and x not in ok]
    fallback = [x for x in expected if reports.get(x, {}).get("model_status") == "UNAVAILABLE_FALLBACK_USED"]
    turns = {aid: reports[aid].get("spiral", {}).get("turn") for aid in reports}
    ascents = {aid: reports[aid].get("spiral", {}).get("ascent_status") for aid in reports}
    status = "LIVE_17_OF_17" if len(reports) == 17 and not degraded else ("DEGRADED_PARTIAL" if reports else "FAILED_NO_REPORTS")
    summary = {
        "schema": "janus.demiurge.scout_swarm.status.v2.spiral",
        "status": status,
        "run_id": str(run_id),
        "control_sha": sha,
        "updated_at_utc": utc_now(),
        "agents_expected": 17,
        "agents_received": len(reports),
        "agents_observed": len(ok),
        "agents_degraded": degraded,
        "agents_missing": missing,
        "agents_model_fallback": fallback,
        "agent_spiral_turns": turns,
        "agent_ascent_status": ascents,
        "aura_oracle_agent": "SCOUT_AURA_ORACLE_01",
        "response_repository": "Hawkar-usls/Janus-Demiurge",
        "evolution_model": "SPIRAL_ACCUMULATIVE_NO_ENTITY_DELETION",
        "model_synthesis_required_for_repository_observation": False,
        "world_truth": False,
        "write_authority_over_targets": False,
    }
    state_root = ROOT / "scout_swarm" / "state"
    (state_root / "SCOUT_SWARM_STATUS-v1.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "SWARM_SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


def self_test() -> None:
    manifest = load_manifest()
    agents = manifest.get("agents", [])
    assert manifest.get("agent_count") == 17
    assert len(agents) == 17
    assert len({a["id"] for a in agents}) == 17
    assert len({(a["target_repo"], a["target_ref"]) for a in agents}) == 17
    assert "NO_LEARNING_ENTITY_DELETION" in manifest.get("invariants", [])
    assert "ITERATION_IS_SPIRAL_NOT_RING" in manifest.get("invariants", [])
    assert any(a["id"] == "SCOUT_AURA_ORACLE_01" and a["target_repo"] == "Hawkar-usls/aura-oracle-tg" for a in agents)
    for agent in agents:
        assert (ROOT / agent["agent_file"]).exists(), agent
    synthetic = {
        "spiral": {"turn": 3, "new_lessons": ["L1"], "retained_constraints": ["C1"]},
        "analysis": {"next_checks": ["C2"], "risks": []},
        "repository_snapshot": {"target_commit": "abc"},
    }
    ctx = inherited_spiral_context(synthetic)
    assert ctx["next_turn"] == 4
    assert ctx["previous_report_is_evidence"] is False
    assert "L1" in ctx["retained_lessons"]
    fallback = deterministic_fallback_analysis(
        agents[0],
        {"target_commit": "abc", "file_count": 3, "recent_commits": [], "selected_sources": []},
        ctx,
        "quota_exceeded",
    )
    assert fallback["analysis_mode"] == "DETERMINISTIC_REPOSITORY_FALLBACK"
    assert fallback["observations"][0]["support"]["commit"] == "abc"
    print("JANUS_DEMIURGE_SCOUT_SWARM_SELF_TEST=PASS agents=17 spiral=TRUE fallback=TRUE")


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
        self_test()
        return 0
    if args.matrix:
        include = [{"id": a["id"], "role": a["role"], "repo": a["target_repo"], "ref": a["target_ref"]} for a in load_manifest()["agents"]]
        print(json.dumps({"include": include}, separators=(",", ":")))
        return 0
    if args.run_agent:
        if not args.output:
            raise SystemExit("--output required")
        run_agent(args.run_agent, Path(args.output))
        return 0
    if args.consolidate:
        if not args.run_id:
            raise SystemExit("--run-id required")
        consolidate(Path(args.consolidate), args.run_id, args.sha)
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
