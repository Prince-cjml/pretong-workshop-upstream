# Hybrid ML Rescue

You are now working in your personal assignment repository.

Verify the branch:

```bash
git branch --show-current
```

Expected:

```text
submission
```

Never run the following commands on `submission`:

```bash
git reset --hard <older-commit>
git rebase course/base-v3
git push --force
git push --force-with-lease
```

## Stage 1: install Conda if needed

Install Miniforge for Linux x86-64 if `conda` is not available.
Then run:

```bash
bash scripts/doctor.sh bootstrap
```

## Stage 2: create the locked environment

```bash
conda create \
  -y \
  -n hybridml-rescue \
  --file conda-linux-64.lock
```

## Stage 3: activate and verify the environment

```bash
conda activate hybridml-rescue
bash scripts/doctor.sh environment
python -m hybridml.environment
```

## Stage 4: build and observe the native failure

```bash
bash scripts/build.sh
```

The first build is expected to fail. Search terms:

```text
CMake imported target
find_package Eigen3
Eigen3 target_link_libraries
```

## Stage 5: repair CMake and the exported C++ symbol

First repair the CMake configuration and rebuild:

```bash
bash scripts/build.sh
```

After the shared library is produced, inspect its exported symbols:

```bash
nm -D build/libfastops.so \
  | grep standardize
```

Compare the exported symbol with the names used by the header and Python loader:

```bash
grep -R \
  "standardize_features" \
  cpp/include \
  hybridml
```

The exported C function name must match the symbol loaded by Python exactly.

Repair:

```text
CMakeLists.txt
cpp/src/fastops.cpp
```

Then rebuild again:

```bash
bash scripts/build.sh
```

Confirm the exported symbol now matches the Python loader:

```bash
nm -D build/libfastops.so \
  | grep standardize_features
```

Only after both native faults are repaired, commit:

```bash
git add \
  CMakeLists.txt \
  cpp/src/fastops.cpp

git commit \
  -m "fix: repair native build"
```

## Stage 6: repair the Python shared-library path

Find the shared library produced by the native build:

```bash
find build \
  -maxdepth 1 \
  -type f \
  -name '*fastops*.so' \
  -print
```

Repair:

```text
hybridml/native.py
```

Run the native public test:

```bash
python -m pytest \
  -q \
  tests/public/test_native.py
```

```bash
git add hybridml/native.py
git commit \
  -m "fix: repair Python native loader"
```

## Stage 7: merge native diagnostics and resolve the one conflict

```bash
git merge \
  --no-ff \
  course/native-integration-v3 \
  -m "merge: integrate native diagnostics"
```

Expected conflicts:

```text
CMakeLists.txt
cpp/src/fastops.cpp
```

Do not use `git checkout --ours .` or `git checkout --theirs .`.
Combine the required lines:

```text
CMakeLists.txt:
- keep the correct Eigen3 target;
- keep FASTOPS_ENABLE_DIAGNOSTICS=1;
- remove all conflict markers.

cpp/src/fastops.cpp:
- keep the plural exported symbol standardize_features;
- keep the non-finite epsilon validation;
- remove all conflict markers.
```

Complete the merge:

```bash
git status
git add CMakeLists.txt cpp/src/fastops.cpp
git commit
```

## Stage 8: cherry-pick deterministic dataset generation

```bash
git cherry-pick course/recovery-data-v3
```

## Stage 9: merge training observability

```bash
git merge \
  --no-ff \
  course/training-observability-v3 \
  -m "merge: integrate training observability"
```

This merge should complete without conflict. Inspect what it introduced:

```bash
git show --stat HEAD
git show HEAD -- config/train.toml
```

## Stage 10: revert the known-bad nondeterministic commit

```bash
git revert \
  --no-edit \
  course/bad-parallel-loader-v3
```

The bad commit and its revert must both remain visible in `git log`.
Do not reset, rebase, or force-push to remove the bad commit.

## Stage 11: validate the project before training

```bash
bash scripts/check.sh project
```

## Stage 12: train and validate the checkpoint

```bash
bash scripts/train.sh

python -m hybridml.checkpoint \
  validate \
  artifacts/model.ckpt
```

## Stage 13: commit the checkpoint

```bash
git add artifacts/model.ckpt

git commit \
  -m "train: produce reproducible checkpoint"
```

## Stage 14: run final public checks

```bash
bash scripts/check.sh final
```

## Stage 15: inspect and push normally

```bash
git log \
  --graph \
  --oneline \
  --decorate \
  --all

git push origin submission
```
