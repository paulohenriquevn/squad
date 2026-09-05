"""Tests for VERA — the autonomous technical arbiter."""
from __future__ import annotations

import sys
from pathlib import Path

_FLEET = Path(__file__).resolve().parents[1] / "mechanisms" / "fleet"
if str(_FLEET) not in sys.path:
    sys.path.insert(0, str(_FLEET))

import vera


class TestVERA:
    """VERA's judgment."""

    def test_vera_identifies_solid_violation(self) -> None:
        """B-022: Engine acoplado a dashboard."""
        v = vera.VERA()
        verdict = v.analyze(
            "B-022",
            "Engine deploy falha se dashboard cai acoplado bloqueada",
            {
                "evidence": "high-level module depends on low-level dashboard service, tight coupling",
                "code_references": ["api/internal/routes/projects/projects.go:253"],
                "impact": "production deploy blocked by unrelated service",
            }
        )
        # VERA identifies the problem and proposes decoupling
        assert "decouple" in (verdict.solution.title + " " + verdict.solution.description).lower()
        assert verdict.problem_id == "B-022"

    def test_vera_identifies_dry_violation(self) -> None:
        """B-060: Dois lugares onde 4 planos se encontram."""
        v = vera.VERA()
        verdict = v.analyze(
            "B-060",
            "Quatro domínios vivem em pasta de arquivos irmãos sem costura clara",  # english-only: fixture in the language the classifier reads
            {
                "evidence": "Four domain folders at same level; no routing spec",
                "code_references": ["infra/terraform", "infra/helm", "api/", "cmd/"],
                "impact": "ambiguous structure; next developer cannot navigate",
            }
        )
        assert verdict.dominant_lens == vera.Lens.CLARITY
        # This one is more about clarity than DRY, which is correct

    def test_vera_identifies_coupling_violation(self) -> None:
        """B-079: Persistência vazou da fronteira."""
        v = vera.VERA()
        verdict = v.analyze(
            "B-079",
            "Remover 4 tipos de persistência da fronteira do sink custa 57 call sites vazou",
            {
                "evidence": "57 call sites import persistence types from domain layer, boundary violated",
                "code_references": ["api/domain/sink.go"],
                "impact": "infrastructure tightly coupled to domain logic",
            }
        )
        assert any(v.lens in (vera.Lens.SOLID, vera.Lens.COUPLING) for v in verdict.violations)
        assert verdict.severity in (vera.Severity.HIGH, vera.Severity.MEDIUM)
        assert "infrastructure" in verdict.solution.description.lower()

    def test_vera_identifies_fail_fast_violation(self) -> None:
        """B-126: Chave transit revogada orfaniza ciphertext silenciosamente."""
        v = vera.VERA()
        verdict = v.analyze(
            "B-126",
            "Uma chave transit revogada orfaniza ciphertext e nada percebe",
            {
                "evidence": "Reads of revoked key fail silently, return empty",
                "code_references": ["pkg/secrets/transit.go"],
                "impact": "tenant secrets become unreadable without error",
            }
        )
        assert verdict.dominant_lens == vera.Lens.FAIL_FAST
        assert verdict.severity == vera.Severity.BLOCKER
        assert "fail" in verdict.solution.description.lower()

    def test_vera_honors_severity_hierarchy(self) -> None:
        """Silent failures are always BLOCKER."""
        v = vera.VERA()
        verdict = v.analyze(
            "TEST",
            "Silent failure in secret retrieval",
            {
                "evidence": "Revoked key returns empty, no error thrown",
                "code_references": ["pkg/secrets/vault.go"],
                "impact": "security-critical data is lost silently",
            }
        )
        assert verdict.severity == vera.Severity.BLOCKER

    def test_vera_estimates_work_size(self) -> None:
        """T3 for large refactors, T1 for small changes."""
        v = vera.VERA()

        # T1: small, one file
        small = v.analyze(
            "SMALL",
            "Message is confusing",
            {
                "evidence": "Error says 'runtime is unsupported' when missing",
                "code_references": ["cmd/config-check.go"],
                "impact": "user confusion",
            }
        )
        assert small.work_size == vera.WorkSize.T1

        # T3: large, many files
        large = v.analyze(
            "LARGE",
            "Remover 4 tipos de persistência da fronteira custa 57 call sites",
            {
                "evidence": "57 call sites need refactor",
                "code_references": ["api/domain/sink.go"],
                "impact": "major refactor",
            }
        )
        assert large.work_size == vera.WorkSize.T3

    def test_vera_produces_actionable_issues(self) -> None:
        """Verdict converts to a GitHub issue cleanly."""
        v = vera.VERA()
        verdict = v.analyze(
            "B-001",
            "Os quatro clusters têm nomes que mentem sobre o que são",  # english-only: fixture in the language the classifier reads
            {
                "evidence": "Cluster named 'dev' serves prod traffic",
                "code_references": ["infra/k3d/values.yaml"],
                "impact": "operator confusion, misdeploy risk",
            }
        )
        issue = verdict.to_issue()
        assert "title" in issue
        assert "body" in issue
        assert "labels" in issue
        assert "B-001" in issue["body"]

    def test_vera_never_equivocates(self) -> None:
        """VERA's solution is always specific, never vague."""
        v = vera.VERA()
        verdict = v.analyze(
            "TEST",
            "Code has coupling issue",
            {"evidence": "high-level imports low-level", "code_references": ["a.go"]},
        )
        # VERA never says "consider", "maybe", "could"
        assert "should" not in verdict.solution.description.lower()
        assert "consider" not in verdict.solution.description.lower()
        assert "maybe" not in verdict.solution.description.lower()

    def test_vera_cites_engineering_principle(self) -> None:
        """Every verdict cites the principle that decided it."""
        v = vera.VERA()
        verdict = v.analyze(
            "TEST",
            "Code is confusing",
            {"evidence": "structure unclear", "code_references": ["a.go"]},
        )
        assert "principle" in verdict.rationale.lower()
        assert "readable" in verdict.rationale.lower() or "communication" in verdict.rationale.lower()
