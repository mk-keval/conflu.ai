#!/usr/bin/env python3
"""Run pytest with proper encoding."""
import sys
import subprocess
import os

os.chdir(r"C:\_Code\conflu.ai")

# Run pytest
result = subprocess.run([
    "python", "-m", "pytest", 
    "backend/tests/test_config.py",
    "-v", "--no-header", "-p", "no:cacheprovider"
], capture_output=True, text=True, encoding='utf-8')

print("STDOUT:")
print(result.stdout)
print("STDERR:")
print(result.stderr)
print("Return code:", result.returncode)
sys.exit(result.returncode)