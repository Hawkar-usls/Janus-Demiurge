#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import re
import subprocess
from pathlib import Path
from typing import Iterable

JWT_RE = re.compile(r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-])")
GITHUB_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_])(?:gh[pousr]_[A-Za-z0-9]{20,255}|github_pat_[A-Za-z0-9_]{20,255})(?![A-Za-z0-9_])")
GOOGLE_API_KEY_RE = re.compile(r"(?<![A-Za-z0-9_-])AIza[0-9A-Za-z_-]{35}(?![A-Za-z0-9_-])")
AWS_ACCESS_KEY_RE = re.compile(r"(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])")
PEM_PRIVATE_KEY_RE = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----")
BEARER_RE = re.compile(r"(?i)\b(?:authorization|proxy-authorization)\s*[:=]\s*['\"]?\s*bearer\s+[A-Za-z0-9._~+/=-]{12,}")
BASIC_RE = re.compile(r"(?i)\b(?:authorization|proxy-authorization)\s*[:=]\s*['\"]?\s*basic\s+[A-Za-z0-9+/=]{12,}")
URL_CREDENTIAL_RE = re.compile(r"https?://[^/\s:@]+:[^/\s@]{4,}@[^/\s]+")
SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"""(?ix)
    (?P<key>
        password|passwd|pwd|
        client[_-]?secret|api[_-]?key|access[_-]?token|refresh[_-]?token|
        private[_-]?key|secret[_-]?key
    )
    \s*[\"']?\s*[:=]\s*[\"']?
    (?P<value>[^\s\"',}]{12,})
    """
)
HEX_HASH_RE = re.compile(r"^[0-9a-fA-F]{32,128}$")
TEMPLATE_RE = re.compile(r"^\$\{\{[^}]+\}\}$")
ENV_REF_RE = re.compile(r"^\$[A-Z_][A-Z0-9_]*$")

DETECTORS = (
    ("JWT", JWT_RE),
    ("GitHub token", GITHUB_TOKEN_RE),
    ("Google API key", GOOGLE_API_KEY_RE),
    ("AWS access key", AWS_ACCESS_KEY_RE),
    ("PEM private key", PEM_PRIVATE_KEY_RE),
    ("Bearer authorization", BEARER_RE),
    ("Basic authorization", BASIC_RE),
    ("URL embedded credentials", URL_CREDENTIAL_RE),
)

TEXT_SUFFIXES = {
    ".py", ".json", ".jsonl", ".yml", ".yaml", ".toml", ".ini", ".cfg",
    ".conf", ".env", ".txt", ".md", ".sh", ".bash", ".zsh", ".ps1",
    ".js", ".ts", ".tsx", ".jsx", ".xml", ".csv", ".properties",
}


def _entropy(value: str) -> float:
    if not value:
        return 0.0
    counts: dict[str, int] = {}
    for ch in value:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(value)
    return -sum((count / n) * math.log2(count / n) for count in counts.values())


def _sensitive_assignments(text: str):
    for match in SENSITIVE_ASSIGNMENT_RE.finditer(text):
        value = match.group("value").strip()
        if TEMPLATE_RE.fullmatch(value) or ENV_REF_RE.fullmatch(value):
            continue
        if HEX_HASH_RE.fullmatch(value):
            continue
        if value.lower() in {"redacted", "placeholder", "example", "dummy", "none", "null"}:
            continue
        if len(value) >= 20 and _entropy(value) >= 3.0:
            yield match.start(), f"sensitive literal under {match.group('key')}"


def scan_text(text: str, label: str) -> list[str]:
    findings: list[str] = []
    for name, detector in DETECTORS:
        for match in detector.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            findings.append(f"{label}:{line}: {name}")
    for offset, reason in _sensitive_assignments(text):
        line = text.count("\n", 0, offset) + 1
        findings.append(f"{label}:{line}: {reason}")
    return findings


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL)


def staged_items() -> Iterable[tuple[str, str]]:
    for name in _git("diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines():
        if not name:
            continue
        try:
            yield name, _git("show", f":{name}")
        except subprocess.CalledProcessError:
            continue


def range_items(commit_range: str) -> Iterable[tuple[str, str]]:
    head = commit_range.rsplit("..", 1)[-1]
    for name in _git("diff", "--name-only", "--diff-filter=ACMR", commit_range).splitlines():
        if not name:
            continue
        try:
            yield name, _git("show", f"{head}:{name}")
        except subprocess.CalledProcessError:
            path = Path(name)
            if path.is_file():
                try:
                    yield name, path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    pass


def path_items(paths: Iterable[str]) -> Iterable[tuple[str, str]]:
    for raw in paths:
        path = Path(raw)
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {".env", ".npmrc", ".pypirc"}:
            continue
        try:
            yield str(path), path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail closed if persistable text contains raw credential material.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--staged", action="store_true")
    group.add_argument("--git-range")
    group.add_argument("--paths", nargs="+")
    args = parser.parse_args()

    if args.staged:
        items = staged_items()
    elif args.git_range:
        items = range_items(args.git_range)
    else:
        items = path_items(args.paths)

    findings: list[str] = []
    for label, text in items:
        findings.extend(scan_text(text, label))

    if findings:
        print("JANUS_SECRET_PERSISTENCE_GUARD=BLOCK")
        for finding in findings:
            print(finding)
        print("RAW_CREDENTIAL_MUST_NEVER_ENTER_PERSISTENT_ARTIFACT")
        return 2

    print("JANUS_SECRET_PERSISTENCE_GUARD=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
