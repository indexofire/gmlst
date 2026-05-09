#!/bin/bash

# Build script for conda package
# This script is called by conda-build

set -e

$PYTHON -m pip install . -vv
