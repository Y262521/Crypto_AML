#!/usr/bin/env python3
"""Test that route order is correct in clusters.py"""

import re
import sys

# Read the clusters.py file
with open('crypto-aml-tracker/backend-py/routes/clusters.py', 'r') as f:
    content = f.read()

# Find all GET route definitions and their line numbers
routes = []
for match in re.finditer(r'@router\.get\("([^"]+)"\)', content):
    path = match.group(1)
    line_no = content[:match.start()].count('\n') + 1
    routes.append((line_no, path))

print("Route order in clusters.py:")
print("=" * 60)
for line_no, path in routes:
    print(f"Line {line_no:4d}: GET {path}")

print("\n" + "=" * 60)

# Check if /summary comes before /{cluster_id}
summary_line = None
cluster_id_line = None

for line_no, path in routes:
    if path == "/summary":
        summary_line = line_no
    elif path == "/{cluster_id}":
        cluster_id_line = line_no

if summary_line and cluster_id_line:
    if summary_line < cluster_id_line:
        print("✓ CORRECT: /summary (line {}) comes BEFORE /{{cluster_id}} (line {})".format(
            summary_line, cluster_id_line))
        print("  This means /api/clusters/summary will work correctly!")
        sys.exit(0)
    else:
        print("✗ ERROR: /{{cluster_id}} (line {}) comes BEFORE /summary (line {})".format(
            cluster_id_line, summary_line))
        print("  This will cause /api/clusters/summary to return 404!")
        sys.exit(1)
else:
    print("✗ ERROR: Could not find both /summary and /{{cluster_id}} routes")
    sys.exit(1)
