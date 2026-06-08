"""Run all Phase 6 tests and report results."""
import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short", "--no-header"],
    cwd=r"C:\Users\yona\Desktop\Crypto_AML\AML",
    capture_output=True,
    text=True,
)
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr[:3000])
sys.exit(result.returncode)
