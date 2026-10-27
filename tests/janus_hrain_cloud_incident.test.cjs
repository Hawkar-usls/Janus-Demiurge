"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { classify, TITLE } = require("../tools/janus_hrain_cloud_incident.cjs");
const repo = { owner: "Hawkar-usls", repo: "Janus-Demiurge" };
const good = {
  id: 100101,
  name: "JANUS HRAiN Unattended Integrity Gate",
  conclusion: "failure",
  status: "completed",
  head_branch: "main",
  head_repository: { full_name: "Hawkar-usls/Janus-Demiurge" },
  head_sha: "a".repeat(40),
};
test("creates precise incident for failed main safety gate", () => {
  const incident = classify(good, repo);
  assert.equal(incident.title, TITLE);
  assert.match(incident.body, /actions\/runs\/100101/);
  assert.match(incident.body, /production HRAiN activation is NOT authorized/);
  assert.doesNotMatch(incident.body, /raw_logs|private_password/);
});
test("cannot turn PR failure into privileged incident creation", () => {
  for (const head_branch of ["feature", "safety/test", null]) {
    assert.equal(classify({...good, head_branch}, repo), null);
  }
});
test("rejects wrong repositories, workflows, incomplete runs or successes", () => {
  for (const patch of [
    { conclusion: "success" },
    { conclusion: "cancelled" },
    { status: "queued" },
    { name: "Unrelated" },
    { head_repository: { full_name: "attacker/fork" } },
    { id: 0 }, { id: "100101" },
  ]) {
    assert.equal(classify({...good, ...patch}, repo), null);
  }
  assert.equal(classify(good, {owner:"Hawkar-usls",repo:"another"}), null);
});
test("ignores untrusted event URL and unverified commit SHA", () => {
  const result = classify({
    ...good, html_url:"https://untrusted.invalid/private",
    head_sha:"not-a-real-hash",
  }, repo);
  assert.match(result.body, /Commit: not-verified/);
  assert.doesNotMatch(result.body, /untrusted.invalid/);
});
