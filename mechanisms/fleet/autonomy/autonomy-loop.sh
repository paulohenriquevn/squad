#!/bin/bash
# autonomy-loop.sh — integrate decision classification and autonomous resolution
# into Squad's main loop. Runs after fleet_supervisor backlog check.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTONOMY_DIR="${SCRIPT_DIR}"

# Auto-detect paths
if [ -z "$BACKLOG_FILE" ]; then
    # Try to find BACKLOG.md in common locations
    for candidate in \
        /home/paulo/dev/theo/BACKLOG.md \
        /home/paulo/Projetos/theo/theo-platform/theo/BACKLOG.md \
        ../../../BACKLOG.md \
        /dev/theo/BACKLOG.md; do
        if [ -f "$candidate" ]; then
            BACKLOG_FILE="$candidate"
            break
        fi
    done
fi

if [ -z "$BACKLOG_FILE" ]; then
    echo "ERROR: BACKLOG_FILE not found. Set BACKLOG_FILE env var or run from Theo dir." >&2
    exit 1
fi

# Defaults
CLASSIFIER="${AUTONOMY_DIR}/decision-classifier.py"
RESOLVER="${AUTONOMY_DIR}/autonomous-decision-resolver.py"
DRY_RUN="${DRY_RUN:-false}"
VERBOSE="${VERBOSE:-false}"

log_info() {
    echo "[autonomy-loop] $(date '+%H:%M:%S') $*" >&2
}

log_verbose() {
    if [ "$VERBOSE" = "true" ]; then
        echo "[autonomy-loop:verbose] $(date '+%H:%M:%S') $*" >&2
    fi
}

# Classify blocked decisions
log_info "Classifying AWAITING_HUMAN decisions..."
CLASSIFICATIONS=$(python3 "$CLASSIFIER" "$BACKLOG_FILE" 2>/dev/null)
log_verbose "Classifications: $CLASSIFICATIONS"

# Resolve autonomously
log_info "Attempting autonomous resolution..."
RESOLUTIONS=$(python3 "$RESOLVER" <(echo "$CLASSIFICATIONS") 2>/dev/null)
log_verbose "Resolutions: $RESOLUTIONS"

# Extract summary
AUTONOMY_RATE=$(echo "$RESOLUTIONS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('autonomy_rate', '0%'))")
RESOLVED_COUNT=$(echo "$RESOLUTIONS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['summary'].get('resolved', 0))")
ESCALATED_COUNT=$(echo "$RESOLUTIONS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['summary'].get('escalated', 0))")
TOTAL_BLOCKED=$(echo "$RESOLUTIONS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('total', 0))")

# Report
log_info "Autonomy Report:"
log_info "  Total blocked: $TOTAL_BLOCKED"
log_info "  Autonomously resolved: $RESOLVED_COUNT"
log_info "  Escalated to human: $ESCALATED_COUNT"
log_info "  Autonomy rate: $AUTONOMY_RATE"

# Write report to file for monitoring
REPORT_FILE="${AUTONOMY_DIR}/autonomy-report.json"
if [ "$DRY_RUN" != "true" ]; then
    echo "$RESOLUTIONS" | python3 -m json.tool > "$REPORT_FILE" 2>/dev/null || {
        log_info "Note: Could not write report to $REPORT_FILE (permissions), but autonomy loop completed"
    }
    if [ -f "$REPORT_FILE" ]; then
        log_info "Report written to $REPORT_FILE"
    fi
else
    log_info "[DRY_RUN] Would write report to $REPORT_FILE"
fi

# Extract items that can progress
log_info "Items ready to progress:"
echo "$RESOLUTIONS" | python3 -c "
import sys, json
try:
    data = json.loads(sys.stdin.read())
    for res in data.get('resolutions', []):
        if res.get('status') == 'resolved':
            item_id = res.get('item_id')
            action = res.get('action', 'unknown action')
            print(f'  {item_id}: {action}')
except Exception as e:
    print(f'  (Could not parse resolutions: {e})', file=sys.stderr)
"

exit 0
