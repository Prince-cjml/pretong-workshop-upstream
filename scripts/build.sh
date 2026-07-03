#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${CONDA_PREFIX:-}" ]]; then
    echo "ERROR: activate hybridml-rescue first."
    exit 1
fi

if [[ -z "${CXX:-}" ]]; then
    printf '%s\n' \
      "ERROR: Conda C++ compiler variable CXX is missing."

    exit 1
fi

rm -rf build

cmake \
  -S . \
  -B build \
  -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_PREFIX_PATH="${CONDA_PREFIX}" \
  -DCMAKE_CXX_COMPILER="${CXX}"

cmake \
  --build build \
  --parallel 2

test -f build/libfastops.so
