"""Publish the five prepared branches using the user's existing Git credential.

Never prints/stores authentication tokens. Refuses a different account or remote.
Run only after the user completes the Git Credential Manager login.
"""

import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNER = "hieufirst1802"
REPOSITORY = "FastAPI_Module_TaskHub"
REMOTE = f"https://github.com/{OWNER}/{REPOSITORY}.git"
BRANCHES = [
    "main",
    "codex/day1-core-setup",
    "codex/day2-database",
    "codex/day3-auth-rbac",
    "codex/day4-core-features",
]


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout.strip()


def main() -> None:
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["GCM_INTERACTIVE"] = "Never"
    credential = subprocess.run(
        ["git", "credential", "fill"],
        input=f"protocol=https\nhost=github.com\nusername={OWNER}\n\n",
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    fields = dict(line.split("=", 1) for line in credential.stdout.splitlines() if "=" in line)
    token = fields.get("password")
    if not token:
        raise SystemExit("GitHub sign-in has not completed")

    def api(path: str, method: str = "GET", data: dict[str, object] | None = None) -> object:
        request = urllib.request.Request(
            "https://api.github.com" + path,
            data=json.dumps(data).encode() if data is not None else None,
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/vnd.github+json",
                "User-Agent": "TaskHub-Practice",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            },
            method=method,
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    account = api("/user")
    if not isinstance(account, dict) or str(account.get("login", "")).lower() != OWNER:
        raise SystemExit("The signed-in Git account does not match the selected browser account")
    try:
        api(f"/repos/{OWNER}/{REPOSITORY}")
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        api(
            "/user/repos",
            "POST",
            {
                "name": REPOSITORY,
                "private": False,
                "description": "FastAPI practice: 5 independent lesson branches, async SQLAlchemy, JWT, RBAC and Redis",
                "auto_init": False,
            },
        )
        print("Created repository", OWNER + "/" + REPOSITORY)
    remotes = git("remote").splitlines()
    if "origin" not in remotes:
        git("remote", "add", "origin", REMOTE)
    elif git("remote", "get-url", "origin") != REMOTE:
        raise SystemExit("Refusing to change an existing origin")
    # Normal atomic push: no force, no mirror, no deletion of remote branches.
    result = subprocess.run(
        ["git", "push", "--atomic", "--set-upstream", "origin", *BRANCHES],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    print(result.stdout)
    print(result.stderr)
    if result.returncode:
        raise SystemExit(result.returncode)
    api(f"/repos/{OWNER}/{REPOSITORY}", "PATCH", {"default_branch": "main"})
    remote_branches = api(f"/repos/{OWNER}/{REPOSITORY}/branches?per_page=100")
    if not isinstance(remote_branches, list):
        raise SystemExit("Could not verify remote branches")
    names = {item["name"] for item in remote_branches}
    if not set(BRANCHES).issubset(names):
        raise SystemExit("Remote verification failed")
    print("Verified branches:", ", ".join(sorted(names)))
    print("Repository:", f"https://github.com/{OWNER}/{REPOSITORY}")


if __name__ == "__main__":
    main()
