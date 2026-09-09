"""Behaviour tests for acceptance-criteria extraction."""
from __future__ import annotations

import pytest
from extract_acceptance_criteria import GateViolation, extract


class TestExtract:
    def test_it_uses_the_milestones_definition_of_done_bullets(self, roadmap_text: str) -> None:
        payload = extract(roadmap_text, "M2")

        assert payload["milestone_id"] == "M2"
        assert payload["milestone_name"] == "Streaming"
        assert [c["text"] for c in payload["criteria"]] == [
            "Response streams token by token.",
            "Cancelling stops the stream within 1s.",
            "A dropped connection resumes without data loss.",
        ]

    def test_it_numbers_the_criteria_and_declares_their_origin(self, roadmap_text: str) -> None:
        criteria = extract(roadmap_text, "M2")["criteria"]

        assert [c["id"] for c in criteria] == ["AC1", "AC2", "AC3"]
        assert {c["source"] for c in criteria} == {"roadmap-dod"}

    def test_it_stops_at_the_next_bold_label(self, roadmap_text: str) -> None:
        """`**Dependencies:**` and `**Top risks:**` must not become acceptance criteria."""
        texts = [c["text"] for c in extract(roadmap_text, "M2")["criteria"]]

        assert not any("Proxy buffering" in t for t in texts)
        assert not any("M1" == t for t in texts)

    def test_it_reads_the_definition_of_done_of_an_already_released_milestone(self, roadmap_text: str) -> None:
        """`[x]` bullets are still criteria — the bullet's state is not the verdict."""
        assert len(extract(roadmap_text, "M1")["criteria"]) == 2

    def test_it_refuses_a_milestone_with_no_definition_of_done(self, roadmap_text: str) -> None:
        with pytest.raises(GateViolation, match="no `\\*\\*Definition of done"):
            extract(roadmap_text, "M3")

    def test_it_refuses_a_definition_of_done_with_no_bullets(self) -> None:
        text = (
            "### M4 — [ ] Empty\n\n"
            "**Definition of done (all must hold):**\n\n"
            "**Dependencies:** none.\n"
        )

        with pytest.raises(GateViolation, match="no `- \\[ \\]` bullets"):
            extract(text, "M4")

    def test_it_refuses_a_missing_milestone(self, roadmap_text: str) -> None:
        with pytest.raises(GateViolation, match="M9 is not in the roadmap"):
            extract(roadmap_text, "M9")

    def test_it_refuses_a_malformed_id(self, roadmap_text: str) -> None:
        with pytest.raises(GateViolation, match="invalid milestone id"):
            extract(roadmap_text, "milestone-2")
