"""VERA against Theo's 14 AWAITING_HUMAN items.

These are the items marked as needing human decision. VERA will analyze
each one and propose the engineering-based solution.
"""
from __future__ import annotations

import sys
from pathlib import Path

_FLEET = Path(__file__).resolve().parents[1] / "mechanisms" / "fleet"
if str(_FLEET) not in sys.path:
    sys.path.insert(0, str(_FLEET))

import vera


class TestVERAVsTheo:
    """VERA judges Theo's open items."""

    def test_vera_on_all_14_items(self) -> None:
        """Run VERA on each of Theo's AWAITING_HUMAN items."""
        v = vera.VERA()

        items = [
            {
                "id": "B-001",
                "problem": "Os quatro clusters têm nomes que mentem",
                "evidence": "dev serves prod, staging contains experiments",
                "refs": ["infra/k3d/values.yaml"],
                "impact": "operator confusion, misdeploy risk",
            },
            {
                "id": "B-022",
                "problem": "Engine depends on dashboard being up",
                "evidence": "init() calls dashboard health check",
                "refs": ["api/internal/routes/engine/init.go:156"],
                "impact": "engine deploy blocked by unrelated service",
            },
            {
                "id": "B-059",
                "problem": "Transport carries payload schema from each domain (body-snooping)",
                "evidence": "Transport reads and routes by domain-specific payload structure",
                "refs": ["api/internal/transport/router.go"],
                "impact": "audit data degrades silently without error",
            },
            {
                "id": "B-060",
                "problem": "4 planes meet only in sibling file folder, no routing spec",
                "evidence": "4 domain folders at same level, no organization",
                "refs": ["infra/terraform", "infra/helm", "api/", "cmd/"],
                "impact": "ambiguous structure; next developer cannot navigate",
            },
            {
                "id": "B-067",
                "problem": "43 migrations without test, 33 alerts without runbook",
                "evidence": "gates measure but nobody ran them until now",
                "refs": ["api/migrations/", "infra/alerting/"],
                "impact": "debt accumulated but gates were silent",
            },
            {
                "id": "B-079",
                "problem": "Removing 4 persistence types from sink boundary costs 57 call sites",
                "evidence": "57 imports of persistence types from domain layer",
                "refs": ["api/domain/sink.go"],
                "impact": "infrastructure leaks into domain, layering violated",
            },
            {
                "id": "B-080",
                "problem": "43 routes files still are flat package, 263 exported symbols",
                "evidence": "All routes in one package, no substructure",
                "refs": ["api/internal/routes/"],
                "impact": "next maintainer cannot navigate, changes are risky",
            },
            {
                "id": "B-126",
                "problem": "Revoked transit key orphanizes ciphertext, nothing notices",
                "evidence": "Read of revoked key returns empty, no error",
                "refs": ["pkg/secrets/transit.go"],
                "impact": "tenant secrets become unreadable silently",
            },
            {
                "id": "B-137",
                "problem": "Real test pyramid violates ADR D7 e2e target, target never measured",
                "evidence": "e2e: 15% actual vs 10% target; e2e not counted in measurement",
                "refs": ["api/tests/", "infra/tests/"],
                "impact": "unknown if target is right or pyramid is wrong",
            },
            {
                "id": "B-139",
                "problem": "Dashboard and droplet services serve from someone's house",
                "evidence": "DNS points to personal IP, account is personal",
                "refs": ["infra/dns/records.yaml"],
                "impact": "SPOF on one person's internet connection",
            },
            {
                "id": "B-146",
                "problem": "cosign deadline verified against ConfigMap that never existed",
                "evidence": "code checks ConfigMap, ConfigMap has zero lines",
                "refs": ["pkg/signing/verify.go"],
                "impact": "supply-chain guard reports on nothing",
            },
            {
                "id": "B-154",
                "problem": "theo.yaml without runtime fails saying runtime is unsupported",
                "evidence": "Error message is wrong when field is missing",
                "refs": ["cmd/theo-yaml-check.go"],
                "impact": "user confusion, unclear fix",
            },
            {
                "id": "B-165",
                "problem": "standalone-public environment has no edge serving it",
                "evidence": "environment deprecated, no CDN endpoint left",
                "refs": ["infra/helm/edge-config.yaml"],
                "impact": "legacy environment broken but still in code",
            },
            {
                "id": "B-168",
                "problem": "Two record trees coexist, one has no tracking",
                "evidence": "records/v1 and records/v2; v2 has zero entries",
                "refs": ["api/records/"],
                "impact": "absence looks like evidence, next sweep will misread",
            },
        ]

        verdicts = []
        for item in items:
            verdict = v.analyze(
                item["id"],
                item["problem"],
                {
                    "evidence": item["evidence"],
                    "code_references": item["refs"],
                    "impact": item["impact"],
                },
            )
            verdicts.append(verdict)

        # Assertions
        assert len(verdicts) == 14, f"Expected 14 verdicts, got {len(verdicts)}"

        # Every item has a solution
        for verdict in verdicts:
            assert verdict.solution is not None
            assert verdict.solution.title
            assert verdict.solution.description
            assert verdict.dominant_lens

        # Check specific ones
        b_022 = next(v for v in verdicts if v.problem_id == "B-022")
        assert "decouple" in (b_022.solution.title + b_022.solution.description).lower()
        assert b_022.dominant_lens == vera.Lens.SOLID

        b_126 = next(v for v in verdicts if v.problem_id == "B-126")
        assert b_126.severity == vera.Severity.BLOCKER
        assert b_126.dominant_lens == vera.Lens.FAIL_FAST

        b_154 = next(v for v in verdicts if v.problem_id == "B-154")
        assert b_154.severity in (vera.Severity.LOW, vera.Severity.MEDIUM)
        assert b_154.work_size == vera.WorkSize.T1

        # Can convert each to issue
        for verdict in verdicts:
            issue = verdict.to_issue()
            assert issue["title"]
            assert issue["body"]
            assert issue["labels"]

    def test_vera_creates_issue_for_each_theo_item(self) -> None:
        """Each item becomes a GitHub-ready issue."""
        v = vera.VERA()

        b_001 = v.analyze(
            "B-001",
            "Os quatro clusters têm nomes que mentem",
            {
                "evidence": "dev serves prod, staging has experiments",
                "code_references": ["infra/k3d/values.yaml"],
                "impact": "operator confusion, risk of misdeploy",
            },
        )

        issue = b_001.to_issue()
        assert "B-001" in issue["body"]
        assert "title" in issue
        assert "labels" in issue
        assert len(issue["labels"]) >= 2  # severity and lens minimum
        assert any("severity:" in l for l in issue["labels"])
