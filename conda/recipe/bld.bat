@echo off
:: Build script for conda package on Windows
:: This script is called by conda-build

%PYTHON% -m pip install . -vv
if errorlevel 1 exit 1
