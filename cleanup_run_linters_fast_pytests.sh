#! /bin/bash -ex

# Run this here in the funfuzz directory, e.g.:
# ./cleanup_run_linters_fast_pytests.sh

# Run shellcheck and bashate first
find . -type d \( -name venv \) -prune -o -type f -name "*.sh" -print0 |
    xargs -n 1 -0 shellcheck
find . -type d \( -name venv \) -prune -o -type f -name "*.sh" -print0 |
    xargs -n 1 -0 bashate

# This script runs flake8, pytest "not slow" and pylint tests if they are installed in python3
# Define the location of python3 using the $PY3_PATH variable, else `command -v python3` is used
PY3="${PY3_PATH:-$(command -v python3)}"
FLAKE8_EC=0
PYLINT_EC=0
PYTEST_EC=0

# Remove *.pyc, *.pyo and __pycache__ directories first
CURR_PATHLIB_PATH="for p in __import__('pathlib').Path('.')"
$PY3 -c "$CURR_PATHLIB_PATH.rglob('*.py[co]'): p.unlink()"
$PY3 -c "$CURR_PATHLIB_PATH.rglob('__pycache__'): p.rmdir()"

# Run flake8
if $PY3 -m flake8 --version > /dev/null 2>&1; then
    $PY3 -m flake8 . || {
        FLAKE8_EC=$?;
        printf '%s\n' "flake8 found errors, exiting early." >&2;
        exit "$FLAKE8_EC";
    };
    echo "flake8 finished running.";
else
    echo "flake8 module is not installed in $PY3"
fi

# Run pytest "not slow" tests
if $PY3 -m pytest --version > /dev/null 2>&1; then
    $PY3 -m pytest -q -m "not slow" || {
        PYTEST_EC=$?;
        printf '%s\n' "pytest found \"not slow\" test errors." >&2;
    };
    echo "pytest finished running."
else
    echo "pytest module is not installed in $PY3"
fi

# Run pylint
if $PY3 -m pylint --version > /dev/null 2>&1; then
    for i in $(echo ./*/); do
        $PY3 -m pylint "$i" || {
            PYLINT_EC=$?; printf '%s\n' "pylint found errors." >&2;
        };
    done
    echo "pylint finished running."
else
    echo "pytest module is not installed in $PY3"
fi

# Output exit code 1 if either flake8 or pylint or pytest ran into errors
if (( FLAKE8_EC || PYTEST_EC || PYLINT_EC )); then
    exit 1;
fi
