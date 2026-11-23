# JANUS trusted witness archive bridge (v1)

## Trust boundary

This is a **trusted GitHub-side collector/importer**, not the external ChatGPT
Silence/Private ACK Witness. Those external witnesses stay **read-only** and
must not receive GitHub write credentials. The importer independently reads the
same underlying GitHub evidence, then writes a segregated record in JANUS Meta
Registry. It cannot archive actual ChatGPT automation messages without a
separate authorized, machine-readable export channel. Therefore its receipts
must not be labeled external-witness-origin attestations.

Only the trusted `main` workflow writes `data/witness_importer/` using the
Meta Registry's own short-lived `GITHUB_TOKEN` with `contents:write` in the
import job. Pull requests only run read-only tests. The collector never
triggers jobs, modifies source repositories, ACK, Genesis HOME, Issue #21,
or grants scientific, command, runtime, or billing authority.

## Records

- `observations/YYYY-MM-DD/<run_id>-<attempt>.json`: immutable receipt **per
  importer run**, including UTC, collector provenance SHA, source metadata,
  five exact-name schedule lines, Genesis HOME high-water, SkinGPT ACK, and
  SHA-256 over canonical receipt content. Receipts do **not** contain private
  packet bodies.
- `transitions/YYYY-MM-DD/<run_id>-<attempt>.json`: first confirmed fault,
  newly affected line, or confirmed recovery only. Repeated faults do not
  generate duplicate transitions.
- `LATEST.json`: last importer receipt, remembered per-line classes, monotonically
  remembered HOME/anchor maxima, and current receipt checksum. `UNKNOWN` never
  erases the previous trusted classification or high-water maximum.

Replay the hash from the UTF-8 receipt JSON object, excluding `receipt_sha256`,
serialized with `json.dumps(sort_keys=True, ensure_ascii=False,
separators=(",", ":"))` and SHA-256. Git commit history preserves earlier states.

## Private SkinGPT

The standard GitHub Actions repository token is scoped to Meta Registry and
cannot be assumed to read `Hawkar-usls/SkinGPT`. The trusted importer supports
an **optional read-only** repository secret
`JANUS_WITNESS_PRIVATE_READ_TOKEN` authorized only for the required SkinGPT
file. Until that secret is installed by an authorized operator, SkinGPT is
recorded as `UNKNOWN / PRIVATE_READ_TOKEN_NOT_CONFIGURED`, never as an ACK
failure. Do not put tokens or private packet contents into issues, logs, or
receipts. A private SHA / batch ID is retained only as evidence metadata.

## Classification guardrails

- SCHEDULE_SILENCE requires exact event=schedule, main, completed/success,
  an independently read `completed_at` from jobs, at least the newest 100
  workflow runs per repository where available, and no newer active schedule.
  If history is insufficient, `UNKNOWN` (not evidence of silence).
- Watchdog's latest allowed `push/workflow_dispatch/schedule` success is a
  separate data field and never counts as a scheduled success.
- HOME lag requires two validated records, HOME seq > anchor seq and most
  recent HOME STATE-changing commit age >=60 minutes. Equal sequences with
  inconsistent evidence are `HIGHWATER_UNKNOWN`. HOME behind the verified
  anchor is `POSSIBLE_GENESIS_ROLLBACK`, not delivery failure.
- SkinGPT durable ACK requires strict entry numbering, exact schemas and
  target, next_sequence, batch ID and SHA match, status and zero scientific
  authority. An unmatched newest entry less than 360 minutes old is
  `ACK_PENDING`. ACK timing alone never proves runtime/science failures.
- GitHub API errors are `UNKNOWN`. This collector runs inside GitHub Actions
  and is **not** an independent cloud outage detector, so it never upgrades
  repeated internal failures to `EXTERNAL_OBSERVATION_LOSS`.

## Running locally

`python -m unittest discover -s tests -p test_witness_importer.py -v`

The import command requires trusted action provenance environment variables
`GITHUB_RUN_ID`, `GITHUB_RUN_ATTEMPT`, and `GITHUB_SHA`. It must only be run in
the trusted write job. No remote receipt is ingested as executable code.