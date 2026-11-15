# JANUS SENTINEL — GitHub Actions data-only state
This branch contains state only; NEVER execute Python, actions, scripts, or policy from this branch.
The authoritative code and fail-closed allowlist live in main.

SENTINEL A and B run identical GitHub-only controller code with staggered cron triggers. Either can take the other's workload while available. C is a distinct deterministic recovery lane which probes A and B; A and B probe C. GitHub Actions provides ephemeral jobs rather than always-on processes; all three are in the SAME GitHub failure domain, not independent uptime guarantees.

The JSON state stores a monotonic recovery epoch and at most one outstanding 60-minute cooldown claim per recovery target. Commit+Git non-fast-forward rejection is the compare-and-swap fence; a role must establish its claim before any network dispatch. It must never force push. A failed post-claim dispatch is a visible unresolved claim, not silently forgotten.

Neural checkpoint promotion is research-only, requires chronological holdout improvement and deterministic fallbacks. The model NEVER directly grants workflow dispatch authority. Externally verified scientific gain and live production promotion remain blocked.
