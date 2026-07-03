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

echo "[1/7] Environment"
python -m hybridml.environment

echo "[2/7] Protected paths"
python .course/local_check.py protected

echo "[3/7] Repository hygiene"
python .course/local_check.py hygiene

echo "[4/7] Native contract"
python .course/local_check.py native

echo "[5/7] Native build"
bash scripts/build.sh

echo "[6/7] Public tests"
python -m pytest -q tests/public

if [[ "$mode" == "project" ]]; then
    echo "Project checks passed."
    exit 0
fi

echo "[7/7] Final checkpoint and history"
python -m hybridml.checkpoint \
  validate \
  artifacts/model.ckpt

python .course/local_check.py history

echo "All final public checks passed."
