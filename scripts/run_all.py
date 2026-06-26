"""
run_all.py — Combined automation runner.

Runs main_imfl.py first, then main_cs.py sequentially.
All arguments passed to this script are forwarded to both sub-scripts.

Usage:
    python run_all.py                  # Headless by default (normal use)
    python run_all.py --no-headless    # Show browser (debug mode)
    python run_all.py --auto           # Auto mode, headless
    python run_all.py --no-headless --auto  # Auto mode, with visible browser
"""

import subprocess
import sys
import os

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable  # Uses same venv/interpreter as the caller

# Any args passed to run_all.py are forwarded to both scripts
extra_args = sys.argv[1:]
scripts = [
    ("main_imfl.py", "IMFL"),
    ("main_cs.py",   "CS"),
]

print("=" * 60)
print("🚀 Starting Full Automation Run")
debug_mode = "--no-headless" in extra_args
headless_note = "⚠️  DEBUG MODE — browser will be visible" if debug_mode else "🕶  Headless mode (default)"
print(f"   {headless_note}")
if extra_args:
    print(f"   Extra args: {extra_args}")
print("=" * 60)

for filename, label in scripts:
    script_path = os.path.join(SCRIPTS_DIR, filename)
    print()
    print(f"{'=' * 60}")
    print(f"▶  Running {label}: {filename}")
    print(f"{'=' * 60}")

    result = subprocess.run(
        [PYTHON, script_path] + extra_args,
        cwd=os.path.dirname(SCRIPTS_DIR),  # Project root (one level up from scripts/)
    )

    if result.returncode != 0:
        print()
        print(f"❌ {label} ({filename}) exited with code {result.returncode}. Stopping.")
        sys.exit(result.returncode)

    print()
    print(f"✅ {label} completed successfully.")

print()
print("=" * 60)
print("🎉 All scripts completed successfully!")
print("=" * 60)
