#!/usr/bin/env python3
"""Quick analysis of the STEP file structure for weld features."""
import sys
sys.path.insert(0, '/home/ubuntu/app/step-weld-analyzer')

STEP_FILE = '/home/ubuntu/app/step-weld-analyzer/data/4628964.stp'

with open(STEP_FILE, 'r') as f:
    lines = f.readlines()

# 1. Product tree (assembly structure)
print("=" * 60)
print("PRODUCT TREE (Assembly Structure)")
print("=" * 60)
for i, line in enumerate(lines):
    if line.startswith('#') and '=PRODUCT(' in line:
        # Extract product info
        parts = line.strip().split('=')
        num = parts[0]
        rest = parts[1]
        # Simple extract: name between quotes
        quotes = [s for s in rest.split("'") if s.strip()]
        if len(quotes) >= 3:
            pid = quotes[0]
            name = quotes[1]
            desc = quotes[2] if len(quotes) > 2 else ''
            print(f"  {num}: [{pid}] {name} | {desc[:60]}")

print("\n" + "=" * 60)
print("WELD-RELATED ENTITIES")
print("=" * 60)
for i, line in enumerate(lines):
    if any(kw in line.upper() for kw in ['WLD', 'WELD', 'WELDING']):
        print(f"  L{i+1}: {line.rstrip()[:200]}")

print("\n" + "=" * 60)
print("SHAPE REPRESENTATIONS (Geometry)")
print("=" * 60)
for i, line in enumerate(lines):
    if 'SHAPE_DEFINITION_REPRESENTATION' in line or 'PRODUCT_DEFINITION_SHAPE' in line:
        print(f"  L{i+1}: {line.rstrip()[:200]}")
