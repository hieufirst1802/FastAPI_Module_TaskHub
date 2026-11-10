"""Run each lesson in a separate interpreter so imports cannot leak across lessons."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify(name: str) -> dict[str, object]:
    directory = ROOT if name == "main" else ROOT / ".exercise-build" / name
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(directory)
    environment["PYTHONIOENCODING"] = "utf-8"
    output = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=directory,
        env=environment,
        capture_output=True,
        check=False,
        encoding="utf-8",
        timeout=90,
    )
    return {"lesson": name, "exit_code": output.returncode, "output": output.stdout + output.stderr}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(verify, ["day1", "day2", "day3", "day4", "main"]))
    destination = ROOT / ".exercise-build" / "verification.json"
    destination.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    for result in results:
        print(result["lesson"], result["exit_code"])
        print(result["output"])
    sys.exit(1 if any(result["exit_code"] for result in results) else 0)
