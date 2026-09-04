#!/usr/bin/env python3
"""Classify AWAITING_HUMAN items and attempt autonomous resolution."""
import json
import re
import sys
from pathlib import Path

class DecisionClassifier:
    """Classify blocked decisions by type and extractibility."""
    
    DECISION_PATTERNS = {
        'architecture': r'(architecture|ADR|decision record|cluster|topology|namespace)',
        'config': r'(configuration|config|helm|values|setting|variable|secret)',
        'review': r'(review|approval|code-review|PR|pull request)',
        'simple_approval': r'(approve|confirm|merge|promote|release)',
    }
    
    def __init__(self, backlog_file: Path):
        self.backlog_file = backlog_file
        self.items = self._parse_backlog()
    
    def _parse_backlog(self) -> dict:
        """Parse BACKLOG.md and extract items."""
        content = self.backlog_file.read_text()
        items = {}
        
        # Find all items (## B-NNN pattern)
        pattern = r'^## (B-\d+)\s*—\s*(.+?)\s*\[\s*([x\s])\s*\]'
        for match in re.finditer(pattern, content, re.MULTILINE):
            item_id, title, status = match.groups()
            items[item_id] = {
                'title': title.strip(),
                'completed': status.lower() == 'x',
                'section_start': match.start(),
            }
        
        # Extract decision info for each item
        for item_id in items:
            start = items[item_id]['section_start']
            # Find next item or end
            next_match = None
            for other_id, other_item in items.items():
                if other_item['section_start'] > start:
                    if next_match is None or other_item['section_start'] < next_match:
                        next_match = other_item['section_start']
            
            end = next_match or len(content)
            items[item_id]['body'] = content[start:end]
        
        return items
    
    def classify(self, item_id: str) -> dict:
        """Classify a single item."""
        if item_id not in self.items:
            return {'error': 'Item not found'}
        
        item = self.items[item_id]
        body = item['body']
        
        # Classify by pattern matching
        classification = {'item_id': item_id, 'title': item['title']}
        
        for decision_type, pattern in self.DECISION_PATTERNS.items():
            if re.search(pattern, body, re.IGNORECASE):
                classification['type'] = decision_type
                classification['confidence'] = 'high' if decision_type in body[:500] else 'medium'
                break
        
        if 'type' not in classification:
            classification['type'] = 'unknown'
            classification['confidence'] = 'low'
        
        # Extract key evidence
        if 'evidence:' in body or 'Evidence:' in body:
            classification['has_evidence'] = True
        if 'sponsor:' in body or 'Sponsor:' in body:
            sponsor_match = re.search(r'(?:sponsor|Sponsor):\s*(.+?)(?:\n|$)', body)
            if sponsor_match:
                classification['sponsor'] = sponsor_match.group(1).strip()
        
        return classification

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: decision-classifier.py <backlog_file> [item_id]")
        sys.exit(1)
    
    backlog = Path(sys.argv[1])
    classifier = DecisionClassifier(backlog)
    
    if len(sys.argv) > 2:
        # Classify single item
        result = classifier.classify(sys.argv[2])
        print(json.dumps(result, indent=2))
    else:
        # Classify all items
        awaiting_human = ['B-001', 'B-022', 'B-059', 'B-060', 'B-067', 'B-079', 'B-080', 'B-126', 'B-137', 'B-139', 'B-146', 'B-154', 'B-165', 'B-168']
        results = [classifier.classify(item) for item in awaiting_human]
        print(json.dumps(results, indent=2))
