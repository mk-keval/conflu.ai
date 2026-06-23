import sys
import subprocess
import os

# Set up environment
os.environ['PYTHONPATH'] = os.getcwd() + '/backend'

# Run pytest
result = subprocess.run([
    'python', '-m', 'pytest', 
    'backend/tests/test_config.py', 
    '-v'
], capture_output=True, text=True)

print("STDOUT:")
print(result.stdout)
print("STDERR:")
print(result.stderr)
print("Return code:", result.returncode)