#!/usr/bin/env python3
"""Render the selector's verdict for `squad-sessions`.

A file of its own because the caller needs a pipe for the selector's output and a
heredoc would take the same stdin — the script would reach the interpreter and the
JSON would be thrown away, which is exactly what happened on the first attempt.
"""
import json
import sys

try:
    report = json.load(open(sys.argv[1], encoding="utf-8"))
except (OSError, ValueError, IndexError):
    print("could not be read")
    raise SystemExit

verdict = report.get("verdict", "?")
print(f'{verdict}  {report.get("item_id") or ""}')
if verdict != "ITEM_SELECTED":
    print("            " + str(report.get("reason", ""))[:130])
