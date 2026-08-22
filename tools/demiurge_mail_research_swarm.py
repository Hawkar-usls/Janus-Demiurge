#!/usr/bin/env python3
"""Evidence-carrying public-web mission runner for the JANUS Demiurge Scout Swarm.

This runner is intentionally separate from repository reconnaissance. It lets the
same 17 persistent Scout identities execute one bounded public-research mission.
Discovery is deterministic HTTP search/fetch; Copilot is optional interpretation
only and cannot promote unsupported model text to evidence.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
MISSION_PATH = ROOT / "scout_swarm" / "missions" / "HA10_ASCENSION_MAIL_TRIAD-v1.json"
USER_AGENT = "JANUS-Demiurge-Public-Research/1.0 (+https://github.com/Hawkar-usls/Janus-Demiurge)"
MAX_DOWNLOAD_BYTES = 4_000_000
MAX_TEXT_CHARS = 28_000
MAX_SOURCES = 8
SECRETISH = re.compile(r"(?:token|password|credential|private[_-]?key|authorization)", re.I)
TOKEN_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AIza[A-Za-z0-9_-]{20,}"),
]


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def scrub(text: str) -> str:
    out = str(text)
    for pattern in TOKEN_PATTERNS:
        out = pattern.sub("[REDACTED_SECRET]", out)
    return out


def load_mission() -> Dict[str, Any]:
    mission = json.loads(MISSION_PATH.read_text(encoding="utf-8"))
    if mission.get("agent_count") != 17 or len(mission.get("agents", [])) != 17:
        raise ValueError("mission must contain exactly 17 agents")
    if mission.get("status") != "AUTHORIZED_TO_RUN":
        raise ValueError("mission is not authorized")
    return mission


def agent_map() -> Dict[str, Dict[str, Any]]:
    return {item["id"]: item for item in load_mission()["agents"]}


def normalize_host(host: str) -> str:
    host = (host or "").lower().split(":", 1)[0].strip(".")
    return host[4:] if host.startswith("www.") else host


def host_allowed(url: str, allowed_domains: Iterable[str]) -> bool:
    try:
        host = normalize_host(urlparse(url).hostname or "")
    except Exception:
        return False
    if not host:
        return False
    for domain in allowed_domains:
        d = normalize_host(str(domain))
        if host == d or host.endswith("." + d):
            return True
    return False


def clean_search_url(href: str) -> Optional[str]:
    if not href:
        return None
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in (parsed.hostname or ""):
        qs = parse_qs(parsed.query)
        if qs.get("uddg"):
            return unquote(qs["uddg"][0])
    if parsed.scheme in {"http", "https"}:
        return href
    return None


def search_public(query: str, allowed_domains: List[str], limit: int = 8) -> List[str]:
    """Best-effort public discovery. Search failure is a valid negative event."""
    try:
        response = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        response.raise_for_status()
    except Exception:
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    urls: List[str] = []
    for anchor in soup.select("a.result__a, a.result-link, a[href]"):
        url = clean_search_url(anchor.get("href") or "")
        if not url or not host_allowed(url, allowed_domains):
            continue
        if url not in urls:
            urls.append(url)
        if len(urls) >= limit:
            break
    return urls


def _pdf_text(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    chunks: List[str] = []
    for page in reader.pages[:80]:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:
            continue
        if sum(len(x) for x in chunks) >= MAX_TEXT_CHARS:
            break
    return "\n".join(chunks)[:MAX_TEXT_CHARS]


def fetch_public(url: str, allowed_domains: List[str], method: str) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "url": url,
        "discovery_method": method,
        "status": "UNFETCHED",
        "title": "",
        "content_type": "",
        "text_sha256": None,
        "excerpt": "",
    }
    if not host_allowed(url, allowed_domains):
        record["status"] = "REJECTED_DOMAIN"
        return record
    if SECRETISH.search(url):
        record["status"] = "REJECTED_SECRETISH_URL"
        return record
    try:
        with requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=25,
            allow_redirects=True,
            stream=True,
        ) as response:
            response.raise_for_status()
            final_url = response.url
            if not host_allowed(final_url, allowed_domains):
                record["status"] = "REJECTED_REDIRECT_DOMAIN"
                record["final_url"] = final_url
                return record
            content_type = (response.headers.get("content-type") or "").lower()
            chunks: List[bytes] = []
            size = 0
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                size += len(chunk)
                if size > MAX_DOWNLOAD_BYTES:
                    break
                chunks.append(chunk)
            data = b"".join(chunks)
            record["final_url"] = final_url
            record["content_type"] = content_type
            record["bytes_read"] = len(data)
            if "pdf" in content_type or final_url.lower().endswith(".pdf"):
                text = _pdf_text(data)
                title = Path(urlparse(final_url).path).name or "PDF"
            else:
                decoded = data.decode(response.encoding or "utf-8", errors="replace")
                if "html" in content_type or "<html" in decoded[:1000].lower():
                    soup = BeautifulSoup(decoded, "html.parser")
                    title = soup.title.get_text(" ", strip=True) if soup.title else ""
                    for tag in soup(["script", "style", "noscript", "svg"]):
                        tag.decompose()
                    text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
                else:
                    title = Path(urlparse(final_url).path).name
                    text = decoded
                text = text[:MAX_TEXT_CHARS]
            text = scrub(text)
            record["title"] = scrub(title)[:500]
            record["text_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
            record["excerpt"] = text
            record["status"] = "FETCHED" if text.strip() else "FETCHED_NO_TEXT"
            return record
    except Exception as exc:
        record["status"] = "FETCH_FAILED"
        record["error"] = scrub(f"{type(exc).__name__}:{exc}")[:1000]
        return record


def discover(agent: Dict[str, Any]) -> Dict[str, Any]:
    allowed = [str(x) for x in agent.get("allowed_domains", [])]
    urls: List[tuple[str, str]] = []
    for url in agent.get("seed_urls", []):
        if host_allowed(str(url), allowed):
            urls.append((str(url), "SEED"))
    search_events: List[Dict[str, Any]] = []
    for query in agent.get("queries", []):
        found = search_public(str(query), allowed, limit=6)
        search_events.append({"query": str(query), "urls": found, "result_count": len(found)})
        for url in found:
            if all(existing != url for existing, _ in urls):
                urls.append((url, "SEARCH"))
    sources: List[Dict[str, Any]] = []
    for url, method in urls[:MAX_SOURCES]:
        sources.append(fetch_public(url, allowed, method))
    return {
        "queries": [str(q) for q in agent.get("queries", [])],
        "search_events": search_events,
        "sources": sources,
        "fetched_count": sum(1 for s in sources if s.get("status") == "FETCHED"),
        "failed_count": sum(1 for s in sources if s.get("status") not in {"FETCHED", "FETCHED_NO_TEXT"}),
    }


def extract_json_object(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        obj = json.loads(text[start:end + 1])
        if isinstance(obj, dict):
            return obj
    raise ValueError("MODEL_OUTPUT_NOT_JSON_OBJECT")


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
    for candidate in reversed(finals):
        try:
            return extract_json_object(candidate)
        except Exception:
            continue
    if deltas:
        return extract_json_object("".join(deltas))
    if not parsed:
        return extract_json_object(stdout)
    raise ValueError("COPILOT_JSONL_MISSING_ASSISTANT_JSON")


def model_analyze(agent: Dict[str, Any], discovery: Dict[str, Any]) -> tuple[Dict[str, Any], Optional[str]]:
    usable = [s for s in discovery.get("sources", []) if s.get("status") == "FETCHED"]
    evidence_pack = [
        {
            "url": s.get("final_url") or s.get("url"),
            "title": s.get("title"),
            "text_sha256": s.get("text_sha256"),
            "excerpt": s.get("excerpt", "")[:12000],
        }
        for s in usable
    ]
    if not evidence_pack:
        return {
            "summary": "No public source text was successfully fetched in this pass.",
            "findings": [],
            "gaps": ["PUBLIC_SOURCE_TEXT_NOT_FETCHED"],
            "next_checks": list(agent.get("queries", [])),
        }, "NO_FETCHED_EVIDENCE"

    prompt = f"""You are one JANUS Scout performing a bounded public-data research mission.
SCOUT_ID: {agent['id']}
TRACK: {agent['track']}
FOCUS: {agent['focus']}

RULES:
- Use ONLY the supplied evidence pack for factual findings.
- Model knowledge and previous Scout output are not evidence.
- Every positive factual finding must cite one or more exact URLs from the pack.
- Distinguish FOUND, POINTER_ONLY, NOT_FOUND_IN_THIS_PASS, and NEEDS_CUSTODIAN_REPLY.
- Do not infer absence from a failed fetch.
- Do not claim dataset coverage of a coordinate unless the source states bounds/track/coordinates sufficient to support it.
- Preserve conflicts and uncertainty.
- The user's goal is physical data validation, not archaeological identification.

EVIDENCE PACK:
{json.dumps(evidence_pack, ensure_ascii=False)}

Return ONLY one JSON object:
{{
  "summary": "concise synthesis",
  "findings": [
    {{"claim":"...","status":"FOUND|POINTER_ONLY|NOT_FOUND_IN_THIS_PASS|NEEDS_CUSTODIAN_REPLY","source_urls":["exact supplied URL"],"confidence":"LOW|MEDIUM|HIGH"}}
  ],
  "gaps": ["..."],
  "next_checks": ["..."]
}}
"""
    with tempfile.TemporaryDirectory(prefix="janus-mail-research-") as td:
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
        try:
            result = subprocess.run(cmd, cwd=td, env=env, text=True, capture_output=True, timeout=180)
            if result.returncode != 0:
                raise RuntimeError(f"COPILOT_CLI_EXIT_{result.returncode}:{scrub((result.stderr or result.stdout or '')[-1200:])}")
            raw = extract_copilot_jsonl(result.stdout)
        except Exception as exc:
            return {
                "summary": "Evidence was collected; model interpretation was unavailable, so no model-derived findings were admitted.",
                "findings": [],
                "gaps": ["MODEL_INTERPRETATION_UNAVAILABLE"],
                "next_checks": list(agent.get("queries", [])),
            }, scrub(f"{type(exc).__name__}:{exc}")[:1400]

    source_urls = {str(item["url"]) for item in evidence_pack}
    findings: List[Dict[str, Any]] = []
    for item in raw.get("findings", []) if isinstance(raw.get("findings"), list) else []:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "NOT_FOUND_IN_THIS_PASS")
        if status not in {"FOUND", "POINTER_ONLY", "NOT_FOUND_IN_THIS_PASS", "NEEDS_CUSTODIAN_REPLY"}:
            status = "NOT_FOUND_IN_THIS_PASS"
        urls = [str(u) for u in (item.get("source_urls") or []) if str(u) in source_urls]
        if status in {"FOUND", "POINTER_ONLY"} and not urls:
            continue
        confidence = str(item.get("confidence") or "LOW").upper()
        if confidence not in {"LOW", "MEDIUM", "HIGH"}:
            confidence = "LOW"
        findings.append({
            "claim": str(item.get("claim") or "")[:3000],
            "status": status,
            "source_urls": urls,
            "confidence": confidence,
        })
    return {
        "summary": str(raw.get("summary") or "")[:6000],
        "findings": findings[:40],
        "gaps": [str(x)[:1500] for x in (raw.get("gaps") or [])[:30]],
        "next_checks": [str(x)[:1500] for x in (raw.get("next_checks") or [])[:30]],
    }, None


def run_agent(agent_id: str, output: Path) -> None:
    mission = load_mission()
    agents = agent_map()
    if agent_id not in agents:
        raise SystemExit(f"UNKNOWN_AGENT:{agent_id}")
    agent = agents[agent_id]
    token = secrets.token_urlsafe(32)
    token_fp = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    discovery = discover(agent)
    analysis, model_error = model_analyze(agent, discovery)
    report = {
        "schema": "janus.demiurge.public_research_agent_report.v1",
        "mission_id": mission["mission_id"],
        "scout_id": agent_id,
        "track": agent["track"],
        "focus": agent["focus"],
        "janus_agent_token": {"scope": "EPHEMERAL_GITHUB_RUN_AGENT", "fingerprint": token_fp, "raw_persisted": False},
        "discovery": discovery,
        "analysis": analysis,
        "model_error": model_error,
        "evidence_boundary": {
            "model_output_is_not_evidence": True,
            "positive_findings_require_fetched_source_url": True,
            "failed_fetch_is_not_proof_of_absence": True,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def consolidate(reports_root: Path, run_id: str, sha: str) -> Path:
    mission = load_mission()
    reports: List[Dict[str, Any]] = []
    for path in sorted(reports_root.rglob("report.json")):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(obj, dict) and obj.get("mission_id") == mission["mission_id"]:
                reports.append(obj)
        except Exception:
            continue
    by_id = {r.get("scout_id"): r for r in reports if r.get("scout_id")}
    expected = [a["id"] for a in mission["agents"]]
    missing = [agent_id for agent_id in expected if agent_id not in by_id]
    all_sources: Dict[str, Dict[str, Any]] = {}
    all_findings: List[Dict[str, Any]] = []
    for report in reports:
        scout_id = report.get("scout_id")
        for source in report.get("discovery", {}).get("sources", []):
            url = str(source.get("final_url") or source.get("url") or "")
            if url:
                all_sources.setdefault(url, {
                    "url": url,
                    "title": source.get("title"),
                    "status": source.get("status"),
                    "text_sha256": source.get("text_sha256"),
                    "seen_by": [],
                })
                if scout_id not in all_sources[url]["seen_by"]:
                    all_sources[url]["seen_by"].append(scout_id)
        for finding in report.get("analysis", {}).get("findings", []):
            all_findings.append({"scout_id": scout_id, "track": report.get("track"), **finding})

    summary = {
        "schema": "janus.demiurge.public_research_swarm_result.v1",
        "mission_id": mission["mission_id"],
        "run_id": str(run_id),
        "controller_sha": str(sha),
        "status": "COMPLETE" if not missing else "PARTIAL",
        "agents_expected": 17,
        "agents_observed": len(reports),
        "agents_missing": missing,
        "source_count_unique": len(all_sources),
        "finding_count": len(all_findings),
        "model_degraded_agents": [r.get("scout_id") for r in reports if r.get("model_error")],
        "sources": sorted(all_sources.values(), key=lambda x: x["url"]),
        "findings": all_findings,
        "mail_tracks": mission["mail_tracks"],
        "evidence_policy": mission["evidence_policy"],
    }
    outdir = ROOT / "scout_swarm" / "outbox" / "public_research" / mission["mission_id"] / str(run_id)
    agents_dir = outdir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    for report in reports:
        (agents_dir / f"{report['scout_id']}.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    (outdir / "SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    state_dir = ROOT / "scout_swarm" / "state" / "public_research"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / f"{mission['mission_id']}.json"
    previous: Dict[str, Any] = {}
    if state_path.exists():
        try:
            previous = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            previous = {}
    history = list(previous.get("history", [])) if isinstance(previous.get("history"), list) else []
    history.append({
        "run_id": str(run_id),
        "controller_sha": str(sha),
        "status": summary["status"],
        "agents_observed": len(reports),
        "source_count_unique": len(all_sources),
        "finding_count": len(all_findings),
        "summary_sha256": canonical_hash(summary),
    })
    state = {
        "schema": "janus.demiurge.public_research_mission_state.v1",
        "mission_id": mission["mission_id"],
        "latest": history[-1],
        "history": history,
    }
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return outdir / "SUMMARY.json"


def self_test() -> None:
    mission = load_mission()
    assert len(mission["agents"]) == 17
    assert host_allowed("https://service.earthscope.org/a", ["earthscope.org"])
    assert not host_allowed("https://example.com/a", ["earthscope.org"])
    assert clean_search_url("https://example.com/x") == "https://example.com/x"
    ids = [a["id"] for a in mission["agents"]]
    assert len(set(ids)) == 17
    assert mission["evidence_policy"]["authenticated_ticket_links_forbidden"] is True
    print("HA10_ASCENSION_MAIL_TRIAD_SELF_TEST=PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", action="store_true")
    parser.add_argument("--run-agent")
    parser.add_argument("--output")
    parser.add_argument("--consolidate")
    parser.add_argument("--run-id")
    parser.add_argument("--sha")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0
    if args.matrix:
        mission = load_mission()
        print(json.dumps({"include": [{"id": a["id"], "track": a["track"]} for a in mission["agents"]]}, separators=(",", ":")))
        return 0
    if args.run_agent:
        if not args.output:
            parser.error("--output is required with --run-agent")
        run_agent(args.run_agent, Path(args.output))
        return 0
    if args.consolidate:
        if not args.run_id or not args.sha:
            parser.error("--run-id and --sha are required with --consolidate")
        path = consolidate(Path(args.consolidate), args.run_id, args.sha)
        print(path)
        return 0
    parser.error("choose --matrix, --run-agent, --consolidate or --self-test")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
