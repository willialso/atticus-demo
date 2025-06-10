#!/bin/bash

# Create test directory if it doesn't exist
mkdir -p tests

# Run the tests
python3 -m unittest tests/test_expiry_changes.py -v

# Check the exit code
if [ $? -eq 0 ]; then
    echo "✅ All expiry tests passed successfully"
    exit 0
else
    echo "❌ Some expiry tests failed"
    exit 1
fi 