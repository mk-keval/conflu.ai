#!/usr/bin/env python3
"""Run tests in isolated environment."""
import sys
import subprocess
import os
import tempfile
import shutil

# Change to project root
os.chdir(r"C:\_Code\conflu.ai")

# Create a temporary directory
with tempfile.TemporaryDirectory() as tmpdir:
    # Copy test files
    shutil.copytree(r"C:\_Code\conflu.ai\backend\tests", os.path.join(tmpdir, "tests"))
    shutil.copytree(r"C:\_Code\conflu.ai\backend\app", os.path.join(tmpdir, "app"))
    shutil.copy2(r"C:\_Code\conflu.ai\pyproject.toml", os.path.join(tmpdir, "pyproject.toml"))
    
    # Change to temp dir
    os.chdir(tmpdir)
    
    # Run pytest
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/test_config.py", "-v", "--no-header", "-p", "no:cacheprovider"
    ], capture_output=True, text=True, encoding='utf-8')

    print("STDOUT:")
    print(result.stdout)
    print("STDERR:")
    print(result.stderr)
    print("Return code:", result.returncode)
    sys.exit(result.returncode)