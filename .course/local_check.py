from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

BASE = "course/base-v3"
START = "course/broken-start-v3"
NATIVE_TIP = "course/native-integration-v3"
TRAINING_TIP = "course/training-observability-v3"
BAD_COMMIT = "course/bad-parallel-loader-v3"
RECOVERY = "course/recovery-data-v3"
IMMUTABLE = "course/immutable-v3"

EXPECTED_SUBJECTS = [
    "fix: repair native build",
    "fix: repair Python native loader",
    "merge: integrate native diagnostics",
    "feat: deterministic repository dataset",
    "merge: integrate training observability",
    'Revert "perf: enable nondeterministic data loading"',
    "train: produce reproducible checkpoint",
]

PATH_POLICY = {
    "fix: repair native build": {"CMakeLists.txt", "cpp/src/fastops.cpp"},
    "fix: repair Python native loader": {"hybridml/native.py"},
    "merge: integrate native diagnostics": {"CMakeLists.txt", "cpp/src/fastops.cpp"},
    "feat: deterministic repository dataset": {"hybridml/data.py"},
    "merge: integrate training observability": {"hybridml/train.py", "config/train.toml"},
    'Revert "perf: enable nondeterministic data loading"': {"config/train.toml"},
    "train: produce reproducible checkpoint": {"artifacts/model.ckpt"},
}

PROTECTED_PATHS_FILE = Path(".course/protected_paths.txt")


def load_path_list(path: Path) -> list[str]:
    result: list[str] = []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        result.append(line)

    return result


PROTECTED_PATHS = load_path_list(PROTECTED_PATHS_FILE)

ALLOWED_FROM_START = set().union(*PATH_POLICY.values())


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def require_ancestor(ancestor: str, descendant: str = "HEAD") -> None:
    result = subprocess.run(["git", "merge-base", "--is-ancestor", ancestor, descendant], check=False)
    require(result.returncode == 0, f"{ancestor} is not an ancestor of {descendant}.")


def parents(commit: str) -> list[str]:
    return git("show", "-s", "--format=%P", commit).split()


def diff_names(a: str, b: str) -> set[str]:
    output = git("diff", "--name-only", "--no-renames", a, b)
    return {line for line in output.splitlines() if line}


def changed_after_start() -> set[str]:
    return diff_names(START, "HEAD")


def preflight() -> None:
    validate_protected_manifest()
    missing = []
    for ref in (BASE, START, NATIVE_TIP, TRAINING_TIP, BAD_COMMIT, RECOVERY, IMMUTABLE):
        result = subprocess.run(["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode != 0:
            missing.append(ref)
    require(not missing, "Missing trusted course refs:\n" + "\n".join(missing))
    print("preflight passed")


def native_contract() -> None:
    cmake = Path("CMakeLists.txt").read_text(encoding="utf-8")
    cpp = Path("cpp/src/fastops.cpp").read_text(encoding="utf-8")
    native_py = Path("hybridml/native.py").read_text(encoding="utf-8")
    require("Eigen3::Eigen" in cmake, "The final CMake target must link Eigen3::Eigen.")
    require("FASTOPS_ENABLE_DIAGNOSTICS=1" in cmake, "The native diagnostics compile definition is missing.")
    require("standardize_features" in cpp, "The plural exported native symbol is missing.")
    require("!std::isfinite(epsilon)" in cpp, "The non-finite epsilon validation is missing.")
    require('"libfastops.so"' in native_py, "The Python loader must use build/libfastops.so.")
    print("native contract passed")


def validate_protected_manifest() -> None:
    duplicate_paths = {
        path
        for path in PROTECTED_PATHS
        if PROTECTED_PATHS.count(path) > 1
    }

    require(
        not duplicate_paths,
        "Duplicate protected paths: "
        + ", ".join(sorted(duplicate_paths)),
    )

    missing = [
        path
        for path in PROTECTED_PATHS
        if not Path(path).exists()
    ]

    require(
        not missing,
        "Protected-path manifest references missing files:\n"
        + "\n".join(missing),
    )


def hygiene() -> None:
    unexpected = changed_after_start() - ALLOWED_FROM_START
    require(not unexpected, "Unexpected paths modified:\n" + "\n".join(sorted(unexpected)))
    tracked = git("ls-files").splitlines()
    forbidden_components = {"build", ".pytest_cache", "__pycache__"}
    forbidden_suffixes = {".so", ".o", ".a", ".pyc"}
    root = Path.cwd().resolve()
    total = 0
    for raw_path in tracked:
        path = Path(raw_path)
        if raw_path == ".gitmodules":
            raise SystemExit("Submodules are not allowed.")
        if any(part in forbidden_components for part in path.parts):
            raise SystemExit(f"Generated path is tracked: {raw_path}")
        if path.suffix in forbidden_suffixes:
            raise SystemExit(f"Compiled artifact is tracked: {raw_path}")
        if raw_path == ".env":
            raise SystemExit(".env must not be tracked")
        if path.is_symlink():
            resolved = path.resolve()
            try:
                resolved.relative_to(root)
            except ValueError as exc:
                raise SystemExit(f"Symlink escapes the repository: {raw_path} -> {resolved}") from exc
        if path.is_file():
            data = path.read_bytes()
            total += len(data)
            require(len(data) <= 2_000_000, f"Tracked file is larger than 2 MB: {raw_path}")
            if data.startswith(b"version https://git-lfs.github.com/spec"):
                raise SystemExit(f"Git LFS pointer is not allowed: {raw_path}")
            if raw_path != "artifacts/model.ckpt" and raw_path.startswith("artifacts/") and raw_path.endswith(".ckpt"):
                raise SystemExit(f"Unexpected checkpoint artifact: {raw_path}")
            lowered = raw_path.lower()
            if any(key in lowered for key in ("id_rsa", "id_ed25519", "private_key", "secret")):
                raise SystemExit(f"Potential private credential path is tracked: {raw_path}")
            open_ssh_marker = b"-----BEGIN " + b"OPENSSH PRIVATE KEY-----"
            rsa_marker = b"-----BEGIN " + b"RSA PRIVATE KEY-----"
            if open_ssh_marker in data or rsa_marker in data:
                raise SystemExit(f"Private key material is tracked: {raw_path}")
    require(total <= 10_000_000, "Tracked repository content exceeds 10 MB.")
    print("repository hygiene passed")


def protected_paths() -> None:
    validate_protected_manifest()
    for path in PROTECTED_PATHS:
        result = subprocess.run(["git", "diff", "--no-ext-diff", "--no-renames", "--exit-code", IMMUTABLE, "HEAD", "--", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        require(result.returncode == 0, f"Protected path changed: {path}")
    print("protected paths passed")


def patch_id(commit: str, path: str) -> str:
    show = subprocess.Popen(["git", "show", "--format=", commit, "--", path], stdout=subprocess.PIPE, text=True)
    return subprocess.check_output(["git", "patch-id", "--stable"], stdin=show.stdout, text=True).split()[0]


def history() -> None:
    preflight()
    for required in (START, NATIVE_TIP, TRAINING_TIP, BAD_COMMIT):
        require_ancestor(required)
    commits = git("rev-list", "--first-parent", "--reverse", f"{START}..HEAD").splitlines()
    subjects = [git("show", "-s", "--format=%s", commit) for commit in commits]
    require(subjects == EXPECTED_SUBJECTS, "First-parent subjects do not match the v3 contract.")

    for index, (commit, subject) in enumerate(zip(commits, subjects)):
        parent = f"{commit}^1"
        changed = diff_names(parent, commit)
        allowed = PATH_POLICY[subject]
        require(changed, f"{subject} is empty.")
        require(
            changed == allowed,
            (
                f"{subject} changed the wrong paths.\n"
                f"Expected: {sorted(allowed)}\n"
                f"Actual: {sorted(changed)}"
            ),
        )
        protected_touched = changed & set(PROTECTED_PATHS)
        require(not protected_touched, f"{subject} touched protected paths: {sorted(protected_touched)}")
        if index > 0:
            require(parents(commit)[0] == commits[index - 1], f"{subject} is not on the required first-parent chain.")

    native_merge = commits[2]
    training_merge = commits[4]
    revert_commit = commits[5]
    require(len(parents(native_merge)) == 2, "Native integration commit is not a two-parent merge.")
    require(parents(native_merge)[1] == git("rev-parse", f"{NATIVE_TIP}^{{commit}}"), "Wrong native merge second parent.")
    require(len(parents(training_merge)) == 2, "Training integration commit is not a two-parent merge.")
    require(parents(training_merge)[1] == git("rev-parse", f"{TRAINING_TIP}^{{commit}}"), "Wrong training merge second parent.")
    require(len(parents(revert_commit)) == 1, "Required revert must be a normal one-parent commit.")
    require_ancestor(BAD_COMMIT, f"{revert_commit}^")
    require(patch_id(RECOVERY, "hybridml/data.py") == patch_id(commits[3], "hybridml/data.py"), "Recovery patch identity does not match.")
    bad_paths = diff_names(f"{BAD_COMMIT}^", BAD_COMMIT)
    revert_paths = diff_names(f"{revert_commit}^", revert_commit)
    require(revert_paths == bad_paths == {"config/train.toml"}, "Revert paths do not match the bad commit.")
    config = git("show", f"{revert_commit}:config/train.toml")
    require("num_threads = 1" in config and "deterministic = true" in config, "Revert did not restore deterministic config.")
    native_contract()
    print("git history passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["preflight", "protected", "hygiene", "native", "history"])
    args = parser.parse_args()
    if args.command == "preflight":
        preflight()
    elif args.command == "protected":
        protected_paths()
    elif args.command == "hygiene":
        hygiene()
    elif args.command == "native":
        native_contract()
    else:
        history()


if __name__ == "__main__":
    main()
