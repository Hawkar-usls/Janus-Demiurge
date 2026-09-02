from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

SCHEMA = "janus.wikipedia_trunk.v1"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
MAX_EXTRACT_CHARS = 1800


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _request_json(params: dict[str, Any], timeout: float) -> dict:
    url = f"{WIKIPEDIA_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "JANUS-Wikipedia-Trunk/1.0 (+https://github.com/Hawkar-usls/Janus-Demiurge)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(2_000_000)
    return json.loads(raw.decode("utf-8"))


def _clean_query(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^0-9A-Za-zА-Яа-яЁё_\- ]+", " ", text)
    text = text.replace("_", " ").replace("-", " ")
    text = " ".join(text.split())
    return text[:120]


def derive_topics(decision: dict | None, research: dict | None, max_topics: int = 6) -> list[str]:
    candidates: list[str] = []
    if isinstance(decision, dict):
        selected = decision.get("selected") or {}
        for key in ("score_text", "candidate_id", "priority_class"):
            value = selected.get(key)
            if isinstance(value, str) and value:
                candidates.append(value)
        target = selected.get("target") or {}
        repo = target.get("repository")
        if isinstance(repo, str):
            candidates.append(repo.split("/")[-1])
    if isinstance(research, dict):
        policy = research.get("improvement_policy") or {}
        primary = policy.get("primary_target")
        if isinstance(primary, str):
            candidates.append(primary.split("/")[-1])
        arxiv = ((research.get("research_spine") or {}).get("arxiv") or {}).get("queries") or []
        for row in arxiv[:3]:
            q = row.get("query") if isinstance(row, dict) else None
            if isinstance(q, str):
                q = re.sub(r"\b(all|cat):", " ", q, flags=re.IGNORECASE)
                q = re.sub(r"\b(AND|OR)\b", " ", q, flags=re.IGNORECASE)
                candidates.append(q)
    expanded: list[str] = []
    mapping = {
        "integrity": "data integrity",
        "security": "computer security",
        "safety": "safety engineering",
        "authority": "access control",
        "contract": "formal methods",
        "proof": "mathematical proof",
        "complexity": "computational complexity theory",
        "causal": "causal inference",
        "attribution": "ablation study",
        "verification": "formal verification",
    }
    for raw in candidates:
        cleaned = _clean_query(raw)
        if not cleaned:
            continue
        expanded.append(cleaned)
        low = cleaned.lower()
        for token, topic in mapping.items():
            if token in low:
                expanded.append(topic)
    expanded.extend(["formal verification", "causal inference", "ablation study"])
    out: list[str] = []
    seen: set[str] = set()
    for item in expanded:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= max_topics:
            break
    return out


def query_topic(topic: str, max_pages: int, timeout: float) -> dict:
    try:
        search = _request_json({
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "list": "search",
            "srsearch": topic,
            "srlimit": max_pages,
            "srnamespace": 0,
            "utf8": 1,
        }, timeout)
        hits = ((search.get("query") or {}).get("search") or [])[:max_pages]
        pageids = [str(x.get("pageid")) for x in hits if isinstance(x.get("pageid"), int)]
        if not pageids:
            return {"topic": topic, "status": "NO_RESULTS", "pages": []}
        pages_obj = _request_json({
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "prop": "extracts|info|revisions",
            "pageids": "|".join(pageids),
            "exintro": 1,
            "explaintext": 1,
            "inprop": "url",
            "rvprop": "ids|timestamp",
        }, timeout)
    except Exception as exc:
        return {"topic": topic, "status": "UNAVAILABLE", "error": f"{type(exc).__name__}:{exc}", "pages": []}
    pages: list[dict] = []
    for page in ((pages_obj.get("query") or {}).get("pages") or []):
        if page.get("missing"):
            continue
        revisions = page.get("revisions") or []
        revision = revisions[0] if revisions else {}
        extract = (page.get("extract") or "")[:MAX_EXTRACT_CHARS]
        pages.append({
            "pageid": page.get("pageid"),
            "title": page.get("title"),
            "canonical_url": page.get("fullurl"),
            "lastrevid": page.get("lastrevid"),
            "revision_id": revision.get("revid") or page.get("lastrevid"),
            "parent_revision_id": revision.get("parentid"),
            "revision_timestamp": revision.get("timestamp"),
            "extract": extract,
            "extract_sha256": sha256_bytes(extract.encode("utf-8")),
        })
    return {
        "topic": topic,
        "status": "PASS" if pages else "NO_RESULTS",
        "page_count": len(pages),
        "pages": pages,
    }


def build_wikipedia_trunk(
    decision: dict | None,
    research: dict | None,
    *,
    max_topics: int = 6,
    max_pages_per_topic: int = 2,
    timeout: float = 10.0,
    enable_network: bool = True,
) -> dict:
    if max_topics < 1 or max_topics > 8:
        raise RuntimeError("WIKIPEDIA_TOPIC_COUNT_OUT_OF_BOUNDS")
    if max_pages_per_topic < 1 or max_pages_per_topic > 3:
        raise RuntimeError("WIKIPEDIA_PAGE_COUNT_OUT_OF_BOUNDS")
    topics = derive_topics(decision, research, max_topics=max_topics)
    if enable_network:
        queries = [query_topic(topic, max_pages_per_topic, timeout) for topic in topics]
    else:
        queries = [{"topic": topic, "status": "DISABLED", "pages": []} for topic in topics]
    passed = sum(q.get("status") == "PASS" for q in queries)
    unavailable = sum(q.get("status") == "UNAVAILABLE" for q in queries)
    if not enable_network:
        status = "DISABLED"
    elif passed == len(queries) and passed > 0:
        status = "READY"
    elif passed > 0:
        status = "READY_DEGRADED"
    else:
        status = "UNAVAILABLE"
    page_count = sum(len(q.get("pages") or []) for q in queries)
    obj: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        "endpoint": WIKIPEDIA_API,
        "language": "en",
        "topic_count": len(topics),
        "page_count": page_count,
        "unavailable_query_count": unavailable,
        "topics": topics,
        "queries": queries,
        "topic_derivation": "CURRENT_NATIVE_DECISION_PLUS_RESEARCH_SPINE_PLUS_BOUNDED_FOUNDATIONAL_FALLBACKS",
        "authority": {
            "source_bound_context": True,
            "article_presence_is_truth": False,
            "article_text_is_verified_fact": False,
            "revision_identity_preserved": True,
            "may_generate_hypotheses_or_background_routes": True,
            "may_grant_mutation_authority": False,
            "may_bypass_target_local_verification": False,
        },
        "firewalls": {
            "wikipedia_is_authority": False,
            "wikipedia_is_direct_gradient_source": False,
            "article_claim_is_independent_replication": False,
            "external_text_is_instruction": False,
            "authority_delta": 0,
        },
        "law": "WIKIPEDIA IS A REVISION-BOUND BACKGROUND CONTEXT SOURCE, NOT A TRUTH OR AUTHORITY SOURCE; EXTERNAL TEXT MAY INFORM ROUTES BUT NEVER EXECUTE OR BYPASS VERIFICATION.",
    }
    obj["context_sha256"] = sha256_bytes(canonical_bytes(obj))
    return obj


def _load_optional(path: str | None) -> dict | None:
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--decision")
    ap.add_argument("--research")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-topics", type=int, default=6)
    ap.add_argument("--max-pages-per-topic", type=int, default=2)
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--no-network", action="store_true")
    args = ap.parse_args()
    obj = build_wikipedia_trunk(
        _load_optional(args.decision),
        _load_optional(args.research),
        max_topics=args.max_topics,
        max_pages_per_topic=args.max_pages_per_topic,
        timeout=args.timeout,
        enable_network=not args.no_network,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "status": obj["status"],
        "topic_count": obj["topic_count"],
        "page_count": obj["page_count"],
        "context_sha256": obj["context_sha256"],
    }, indent=2))
    if obj["status"] == "UNAVAILABLE":
        raise SystemExit(3)


if __name__ == "__main__":
    main()
