#!/usr/bin/env bash
set +euo pipefail
mode="${1:-bootstrap}"
failures=0

check() {
  label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "[PASS] $label"
  else
    echo "[FAIL] $label"
    failures=$((failures + 1))
  fi
}

skip() {
  echo "[SKIP] $1"
}

if [[ "$mode" == "bootstrap" ]]; then
  check git command -v git
  if command -v conda >/dev/null 2>&1; then
    echo "[PASS] conda"
  else
    echo "[FAIL] conda"
    failures=$((failures + 1))
  fi
  check "Linux x86_64" bash -c '[[ "$(uname -s)" == "Linux" && "$(uname -m)" == "x86_64" ]]'
elif [[ "$mode" == "environment" ]]; then
  if [[ -n "${CONDA_PREFIX:-}" ]]; then echo "[PASS] CONDA_PREFIX"; else echo "[FAIL] CONDA_PREFIX"; failures=$((failures + 1)); fi
  check "Conda environment active" bash -c '[[ -n "${CONDA_DEFAULT_ENV:-}" ]]'
  check "Python contract" python -m hybridml.environment
  check tomli python -c 'import tomli'
  check cmake command -v cmake
  check ninja command -v ninja
  if [[ -n "${CXX:-}" ]]; then echo "[PASS] CXX=$CXX"; else echo "[FAIL] CXX"; failures=$((failures + 1)); fi
  if [[ -n "${CONDA_PREFIX:-}" ]]; then
    check "Eigen CMake package" test -e "${CONDA_PREFIX}/share/eigen3/cmake/Eigen3Config.cmake"
    echo "[INFO] lock sha256 $(python - <<'PY'
from pathlib import Path
import hashlib
print(hashlib.sha256(Path("conda-linux-64.lock").read_bytes()).hexdigest())
PY
)"
  else
    skip "Eigen CMake package"
    skip "lock sha256"
  fi
else
  echo "usage: bash scripts/doctor.sh [bootstrap|environment]"
  exit 2
fi

exit "$failures"
