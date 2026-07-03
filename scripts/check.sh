#!/usr/bin/env bash
set -euo pipefail

mode="${1:-project}"

case "$mode" in
  project|final)
    ;;
  *)
    echo "usage: bash scripts/check.sh [project|final]"
    exit 2
    ;;
esac

echo "[1/6] Environment"
python -m hybridml.environment

echo "[2/6] Protected paths"
python .course/local_check.py protected

echo "[3/6] Repository hygiene"
python .course/local_check.py hygiene

echo "[4/6] Native build"
bash scripts/build.sh

echo "[5/6] Public tests"
pytest -q tests/public

if [[ "$mode" == "project" ]]; then
    echo "Project checks passed."
    exit 0
fi

echo "[6/6] Final checkpoint and history"
python -m hybridml.checkpoint validate artifacts/model.ckpt
python .course/local_check.py history

echo "All final public checks passed."
