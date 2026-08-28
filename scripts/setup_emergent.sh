#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_COMMAND="${PYTHON_COMMAND:-python3}"

if ! command -v "${PYTHON_COMMAND}" >/dev/null 2>&1; then
  echo "Required Python command not found: ${PYTHON_COMMAND}" >&2
  exit 1
fi

if ! command -v yarn >/dev/null 2>&1; then
  echo "Yarn Classic is required but was not found." >&2
  exit 1
fi

echo "Installing backend dependencies..."
"${PYTHON_COMMAND}" -m pip install -r "${REPO_ROOT}/backend/requirements.txt"

echo "Installing the pinned private pricing engine..."
"${PYTHON_COMMAND}" "${REPO_ROOT}/backend/scripts/install_pricing_engine.py"

echo "Installing frozen frontend dependencies..."
(
  cd "${REPO_ROOT}/frontend"
  yarn install --frozen-lockfile
)

echo "SignGuy AI dependencies are installed."
