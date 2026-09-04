# Security Policy

## Scope

The Squad ecosystem includes **runtime hooks** (`hooks/*.sh`) that execute shell
commands in the user's environment. A vulnerability in hook logic (e.g., command
injection via crafted branch names, regex bypass in `validate-command.py`) could
affect any project using this plugin.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x (current alpha) | Yes |
| Older than 0.1 | No |

## Reporting a Vulnerability

**Do NOT open a public issue for security vulnerabilities.**

1. Email the maintainer directly or use GitHub's
   [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
   feature on this repository.
2. Include:
   - Which hook or script is affected
   - Steps to reproduce (e.g., a crafted git branch name, a malicious JSON payload)
   - Impact assessment (command execution, data exfiltration, gate bypass)
3. You will receive an acknowledgment within **72 hours**.
4. A fix will be released within **14 days** for critical issues.

## Security Design

- **Hooks use `set -euo pipefail`** — fail-fast on any unexpected state.
- **`validate-command.py`** blocks destructive git operations at the regex level.
- **`stop-validation.py`** blocks secret file commits (`.env`, `*.pem`, `*.key`).
- **`boundary-check.py`** enforces read-only access on `study-material/`.
- **`check_xrefs.py`** validates all internal references exist (anti-hallucination).
- **`attest_plan.sh`** uses SHA256 for plan tamper detection.

Retired 2026-09-01: the prior-art study zone under `records/references/` is no
longer guarded, because Squad's DISCOVER stopped studying peer projects and the
directory left the zone with the practice that filled it. A consumer still
holding material there must move it (`rules/reference-provenance.md`).

## Known Limitations

- Hook regex patterns are heuristic-based — edge cases in command parsing may
  exist. If you find a bypass, report it as a vulnerability.
- Hooks rely on `jq` for JSON parsing of tool input. Malformed input is rejected or produces an
  explicit no-op according to each hook's contract; regression tests cover both outcomes.
