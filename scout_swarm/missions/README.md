# JANUS Scout public-research missions

Mission overlays reuse the same persistent Scout identities without replacing their normal repository reconnaissance roles.

The active HA10/Ascension three-mail mission is `HA10_ASCENSION_MAIL_TRIAD-v1.json`.

Rules:

- public sources only;
- authenticated service-desk links and secrets are never persisted;
- deterministic HTTP search/fetch produces the evidence pack;
- model interpretation is optional and is never itself evidence;
- positive findings require a fetched source URL;
- failed fetches are not evidence of absence;
- negative and unresolved results remain in the append-only mission history;
- all 17 Scouts run independently and their reports return to Janus-Demiurge.
