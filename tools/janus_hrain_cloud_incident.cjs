"use strict";

/* Pure, fail-closed incident classifier. Never read workflow logs or owner data. */
const EXPECTED_REPO = "Hawkar-usls/Janus-Demiurge";
const EXPECTED_WORKFLOW = "JANUS HRAiN Unattended Integrity Gate";
const TITLE = "JANUS HRAiN · cloud integrity gate failed";

function classify(run, repo) {
  if (!run || !repo || repo.owner + "/" + repo.repo !== EXPECTED_REPO) return null;
  if (run.name !== EXPECTED_WORKFLOW || run.conclusion !== "failure"
    || run.status !== "completed" || run.head_branch !== "main"
    || run.head_repository?.full_name !== EXPECTED_REPO
    || !Number.isSafeInteger(run.id) || run.id <= 0) return null;

  // Derive the URL from validated GitHub identifiers, not untrusted event text.
  const url = "https://github.com/" + EXPECTED_REPO + "/actions/runs/" + run.id;
  const commit = typeof run.head_sha === "string" && /^[0-9a-f]{40}$/.test(run.head_sha)
    ? run.head_sha : "not-verified";
  return {
    title: TITLE,
    body: [
      "Automated JANUS safety gate failed on the default branch.",
      "",
      "Run: " + url,
      "Commit: " + commit,
      "Verdict: HOLD — production HRAiN activation is NOT authorized by this signal.",
      "",
      "Inspect the specific CI job; distinguish actual regression from transient runner/network failure.",
      "Do not auto-disable the guard, auto-merge a repair, restart owner processes,",
      "upload private graph snapshots, or change Rowan/TOPA authority.",
      "",
      "This incident is intentionally created once; subsequent matching failures remain in CI history.",
    ].join("\n")
  };
}
module.exports = { classify, TITLE };
