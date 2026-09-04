#!/usr/bin/env python3
"""Autonomous decision resolver — attempt to resolve blocked items with policies."""
import json
import re
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

@dataclass
class Resolution:
    """A resolved decision with justification."""
    item_id: str
    decision_type: str
    confidence: str
    status: str  # resolved | escalated | timeout
    reason: str
    action: Optional[str] = None
    escalate_to: Optional[str] = None

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if v is not None}

class AutonomousResolver:
    """Apply pre-approved policies to resolve blocker items."""

    # Policy matrix: decision_type -> (resolvable, escalation_contact)
    POLICIES = {
        'config': {
            'resolvable': True,
            'escalate_to': 'DevOps Lead',
            'action_template': 'Apply standard config pattern from rules/config-defaults.yaml',
        },
        'review': {
            'resolvable': True,
            'escalate_to': None,
            'action_template': 'Run automated code review gate; approve if passing',
        },
        'simple_approval': {
            'resolvable': True,
            'escalate_to': 'Tech Lead',
            'action_template': 'Verify criteria met; auto-approve if evidence sufficient',
        },
        'architecture': {
            'resolvable': False,
            'escalate_to': 'CTO / Architect',
            'action_template': 'Requires ADR + human decision',
        },
        'unknown': {
            'resolvable': False,
            'escalate_to': 'Squad Lead',
            'action_template': 'Insufficient context; human triage required',
        },
    }

    def __init__(self, backlog_file: Path):
        self.backlog_file = backlog_file
        self.backlog_content = backlog_file.read_text()

    def resolve(self, item_id: str, classification: dict) -> Resolution:
        """Attempt autonomous resolution of one item."""
        decision_type = classification.get('type', 'unknown')
        confidence = classification.get('confidence', 'low')
        policy = self.POLICIES.get(decision_type, self.POLICIES['unknown'])

        # Core rule: architecture decisions never auto-resolve
        if decision_type == 'architecture':
            return Resolution(
                item_id=item_id,
                decision_type=decision_type,
                confidence=confidence,
                status='escalated',
                reason=f'Architecture decision requires {policy["escalate_to"]}',
                escalate_to=policy['escalate_to'],
            )

        # Config decisions auto-resolve if evidence exists
        if decision_type == 'config':
            has_evidence = classification.get('has_evidence', False)
            if has_evidence:
                return Resolution(
                    item_id=item_id,
                    decision_type=decision_type,
                    confidence=confidence,
                    status='resolved',
                    reason='Config policy exists and evidence sufficient',
                    action=policy['action_template'],
                )
            else:
                return Resolution(
                    item_id=item_id,
                    decision_type=decision_type,
                    confidence=confidence,
                    status='timeout',
                    reason='Config type but insufficient evidence for auto-resolution',
                    escalate_to=policy['escalate_to'],
                )

        # Review decisions auto-resolve if they pass gate
        if decision_type == 'review':
            return Resolution(
                item_id=item_id,
                decision_type=decision_type,
                confidence=confidence,
                status='resolved',
                reason='Review can run automated gates',
                action=policy['action_template'],
            )

        # Everything else: escalate
        return Resolution(
            item_id=item_id,
            decision_type=decision_type,
            confidence=confidence,
            status='escalated',
            reason=f'Decision type {decision_type} requires human judgment',
            escalate_to=policy.get('escalate_to', 'Squad Lead'),
        )

def main():
    if len(sys.argv) < 2:
        print("Usage: autonomous-decision-resolver.py <classifications.json>")
        sys.exit(1)

    # Parse input
    with open(sys.argv[1]) as f:
        classifications = json.load(f)

    resolver = AutonomousResolver(Path('/dev/null'))  # Not needed for this demo

    # Resolve all items
    resolutions = []
    stats = {'resolved': 0, 'escalated': 0, 'timeout': 0}

    for classification in (classifications if isinstance(classifications, list) else [classifications]):
        item_id = classification.get('item_id', 'unknown')
        resolution = resolver.resolve(item_id, classification)
        resolutions.append(resolution.to_dict())
        stats[resolution.status] += 1

    # Output
    output = {
        'resolutions': resolutions,
        'summary': stats,
        'total': len(resolutions),
        'autonomy_rate': f"{(stats['resolved'] / len(resolutions) * 100):.1f}%",
    }

    print(json.dumps(output, indent=2))

if __name__ == '__main__':
    main()
