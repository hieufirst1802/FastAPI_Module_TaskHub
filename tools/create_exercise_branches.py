"""Create five local lesson branches in a new, uncommitted repository. No network calls."""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRANCHES = [
    ("codex/day1-core-setup", "day1", "feat: complete lesson 1 core setup and in-memory CRUD"),
    ("codex/day2-database", "day2", "feat: complete lesson 2 async database and Alembic"),
    ("codex/day3-auth-rbac", "day3", "feat: complete lesson 3 JWT RBAC and ownership"),
    ("codex/day4-core-features", "day4", "feat: complete lesson 4 Redis middleware and Docker"),
    ("main", None, "chore: complete lesson 5 review quality checks and documentation"),
]


def git(
    *args: str, cwd: Path = ROOT, env: dict[str, str] | None = None, content: str | None = None
) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        input=content,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    ).stdout.strip()


if __name__ == "__main__":
    if git("for-each-ref", "--format=%(refname)", "refs/heads", "refs/tags"):
        raise SystemExit("Refusing to overwrite an existing Git history")
    previous = ""
    for branch, snapshot, message in BRANCHES:
        directory = ROOT / ".exercise-build" / snapshot if snapshot else ROOT
        environment = os.environ.copy()
        index_name = snapshot or "main"
        environment["GIT_INDEX_FILE"] = str(ROOT / ".exercise-build" / f"index-{index_name}")
        common = ["--git-dir", str(ROOT / ".git"), "--work-tree", str(directory)]
        git(*common, "read-tree", "--empty", cwd=directory, env=environment)
        git(*common, "add", "--all", "--", ".", cwd=directory, env=environment)
        files = git(*common, "ls-files", cwd=directory, env=environment).splitlines()
        if any(
            name == ".env" or name.endswith(".db") or name.startswith(".exercise-build/")
            for name in files
        ):
            raise SystemExit("Unexpected private/build files in index")
        tree = git(*common, "write-tree", cwd=directory, env=environment)
        parent = ["-p", previous] if previous else []
        commit = git("commit-tree", tree, *parent, content=message + "\n")
        git("update-ref", f"refs/heads/{branch}", commit, "0" * 40)
        previous = commit
        print(branch, commit[:12], len(files), "files")
    git("symbolic-ref", "HEAD", "refs/heads/main")
    git("read-tree", "main")
