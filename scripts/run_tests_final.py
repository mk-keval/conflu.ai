#!/usr/bin/env python3
"""Run tests with proper module resolution."""
import sys
import subprocess
import os
import tempfile
import shutil
import sys

# Change to project root
os.chdir(r"C:\_Code\conflu.ai")

# Add the project root to sys.path so 'backend' module can be found
sys.path.insert(0, r"C:\_Code\conflu.ai")

# Run pytest
result = subprocess.run([
    sys.executable, "-m", "pytest", 
    "backend/tests/test_config.py", "-v", "--no-header", "-p", "no:cacheprovider"
], capture_output=True, text=True, encoding='utf-8')

print("STDOUT:")
print(result.stdout)
print("STDERR:")
print(result.stderr)
print("Return code:", result.returncode)
sys.exit(result.returncode)