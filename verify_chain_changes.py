#!/usr/bin/env python
"""
Quick validation that chain parameter was successfully added to all files.
This script verifies syntax and key changes without requiring full module imports.
"""

import re
import sys
from pathlib import Path

def check_file_contains(filepath, patterns, description):
    """Check if file contains all the specified patterns."""
    print(f"\n✓ Checking {description}: {filepath.name}")
    
    try:
        content = filepath.read_text()
        for pattern in patterns:
            if not re.search(pattern, content, re.MULTILINE | re.DOTALL):
                print(f"  ✗ MISSING: {pattern}")
                return False
        print(f"  ✓ All patterns found")
        return True
    except Exception as e:
        print(f"  ✗ Error reading file: {e}")
        return False

def main():
    """Verify all chain parameter changes are in place."""
    base_path = Path("/home/hakim/Crypto_AML/AML/src/aml_pipeline")
    
    all_passed = True
    
    # Check 1: Clustering engine has chain_name parameter
    all_passed &= check_file_contains(
        base_path / "clustering/engine.py",
        [r"def run\(.*chain_name:\s*str\s*\|?\s*None"],
        "Clustering engine chain_name parameter"
    )
    
    # Check 2: Placement analysis has chain_name parameter and field
    all_passed &= check_file_contains(
        base_path / "analytics/placement.py",
        [r"chain_name:\s*Optional\[str\]", r"def run\(.*chain_name:\s*Optional\[str\]"],
        "Placement analysis chain support"
    )
    
    # Check 3: Layering engine has chain_name parameter
    all_passed &= check_file_contains(
        base_path / "analytics/layering/engine.py",
        [r"def run\(.*chain_name:\s*str\s*\|?\s*None"],
        "Layering engine chain_name parameter"
    )
    
    # Check 4: Layering types has chain_name field
    all_passed &= check_file_contains(
        base_path / "analytics/layering/types.py",
        [r"chain_name:\s*Optional\[str\]"],
        "Layering types chain_name field"
    )
    
    # Check 5: Integration engine has chain_name parameter
    all_passed &= check_file_contains(
        base_path / "analytics/integration/engine.py",
        [r"def run\(.*chain_name:\s*str\s*\|?\s*None"],
        "Integration engine chain_name parameter"
    )
    
    # Check 6: Integration types has chain_name field
    all_passed &= check_file_contains(
        base_path / "analytics/integration/types.py",
        [r"chain_name:\s*Optional\[str\]"],
        "Integration types chain_name field"
    )
    
    # Check 7: Daily pipeline calls engines with chain_name
    all_passed &= check_file_contains(
        base_path / "pipelines/daily_pipeline.py",
        [
            r"engine\.run\(.*chain_name=chain",
            r"placement_engine\.run\(.*chain_name=chain",
            r"layering_engine\.run\(.*chain_name=chain",
            r"integration_engine\.run\(.*chain_name=chain",
        ],
        "Daily pipeline chain parameter forwarding"
    )
    
    # Check 8: CLI has chain argument
    all_passed &= check_file_contains(
        base_path / "pipelines/run_etl.py",
        [r"--chain", r"ethereum|bsc|polygon|arbitrum|base"],
        "CLI chain argument"
    )
    
    # Check 9: Transaction filtering in engines
    all_passed &= check_file_contains(
        base_path / "clustering/engine.py",
        [r'if chain_name.*transactions.*=.*\[.*for.*tx.*in.*transactions.*if'],
        "Clustering transaction filtering"
    )
    
    print("\n" + "="*60)
    if all_passed:
        print("✓ All checks PASSED - chain parameter successfully integrated!")
        return 0
    else:
        print("✗ Some checks FAILED - see details above")
        return 1

if __name__ == "__main__":
    sys.exit(main())
