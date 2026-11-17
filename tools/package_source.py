"""Build a clean source distribution: python tools/package_source.py."""

import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist" / "FastAPI_Module_TaskHub_Complete.zip"
EXCLUDED = {
    ".git",
    ".venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    ".uv-cache",
    "dist",
    ".exercise-build",
    ".agents",
    ".codex",
    ".aws",
}


def main() -> None:
    OUTPUT.parent.mkdir(exist_ok=True)
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        for source in sorted(ROOT.rglob("*")):
            relative = source.relative_to(ROOT)
            if not source.is_file() or any(
                part in EXCLUDED or part.endswith(".egg-info") for part in relative.parts
            ):
                continue
            if source.name.startswith(".env") and source.name != ".env.example":
                continue
            if source.suffix in {".db", ".pyc", ".zip"} or ".db-" in source.name:
                continue
            archive.write(source, Path("FastAPI_Module_TaskHub") / relative)
    with ZipFile(OUTPUT) as archive:
        assert archive.testzip() is None
        for entry in archive.infolist():
            source = ROOT.joinpath(*Path(entry.filename).parts[1:])
            assert (
                hashlib.sha256(archive.read(entry)).digest()
                == hashlib.sha256(source.read_bytes()).digest()
            )
        print(f"Verified {len(archive.namelist())} files")
    checksum = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    OUTPUT.with_suffix(".zip.sha256").write_text(f"{checksum}  {OUTPUT.name}\n", encoding="utf-8")
    print(OUTPUT)
    print(f"SHA256: {checksum}")


if __name__ == "__main__":
    main()
