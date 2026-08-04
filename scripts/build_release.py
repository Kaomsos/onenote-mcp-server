#!/usr/bin/env python3
"""Build a deterministic, runtime-only source ZIP for local distribution."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[A-Za-z0-9.-]+)?$")
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
ZIP_FILE_MODE = (0o100644 & 0xFFFF) << 16

RUNTIME_FILES: tuple[Path, ...] = (
    Path("onenote_mcp/__init__.py"),
    Path("onenote_mcp/auth.py"),
    Path("onenote_mcp/config.py"),
    Path("onenote_mcp/graph.py"),
    Path("onenote_mcp/server.py"),
    Path("onenote_mcp/tools.py"),
    Path("onenote_mcp_server.py"),
    Path("pyproject.toml"),
    Path("uv.lock"),
    Path("README.md"),
    Path("CHANGELOG.md"),
    Path("LICENSE"),
    Path("docs/README.md"),
    Path("docs/acceptance_guide_zh.md"),
    Path("docs/product/README.md"),
    Path("docs/product/local_onenote_com_mcp_research.md"),
    Path("docs/product/merge_onenote_agent_handler.md"),
    Path("docs/todos/README.md"),
    Path("docs/todos/page_content_search.md"),
    Path("docs/todos/page_hierarchy_support.md"),
    Path("docs/todos/page_section_copy_move.md"),
    Path("docs/todos/reference_project_feature_parity.md"),
    Path("docs/todos/three_level_crud_gap.md"),
    Path(".claude/mcp.example.json"),
    Path(".codex/config.example.toml"),
)

FORBIDDEN_ARCHIVE_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "tests",
}
FORBIDDEN_ARCHIVE_PATHS = {
    Path(".mcp.json"),
    Path(".codex/config.toml"),
    Path(".env"),
    Path(".env.local"),
}
FORBIDDEN_CONTENT_PATTERNS: tuple[tuple[str, re.Pattern[bytes]], ...] = (
    (
        "UUID-shaped credential",
        re.compile(
            rb"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b"
        ),
    ),
    (
        "assigned client secret",
        re.compile(rb"(?i)(?:AZURE_CLIENT_SECRET|client[_ -]?secret)\s*[:=]\s*['\"][^'\"]+"),
    ),
    ("JWT-shaped token", re.compile(rb"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")),
)


@dataclass(frozen=True)
class ReleaseResult:
    version: str
    archive: Path
    checksum_file: Path
    sha256: str


def read_project_version(pyproject_path: Path) -> str:
    """Read project.version without requiring tomllib on Python 3.10."""

    section = ""
    for raw_line in pyproject_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if section != "project" or not line.startswith("version"):
            continue
        key, separator, raw_value = line.partition("=")
        if not separator or key.strip() != "version":
            continue
        value = ast.literal_eval(raw_value.strip())
        if not isinstance(value, str) or not VERSION_PATTERN.fullmatch(value):
            raise ValueError("project.version must be a semantic version string")
        return value
    raise ValueError("project.version was not found in pyproject.toml")


def validate_runtime_files(project_root: Path, files: Iterable[Path]) -> tuple[Path, ...]:
    """Resolve the explicit allow list and reject unsafe or missing paths."""

    validated: list[Path] = []
    for relative_path in sorted(files, key=lambda path: path.as_posix()):
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError(f"Unsafe release path: {relative_path}")
        if relative_path in FORBIDDEN_ARCHIVE_PATHS:
            raise ValueError(f"Sensitive release path: {relative_path}")
        if FORBIDDEN_ARCHIVE_PARTS.intersection(relative_path.parts):
            raise ValueError(f"Development-only release path: {relative_path}")
        source = project_root / relative_path
        if not source.is_file() or source.is_symlink():
            raise FileNotFoundError(f"Required release file is missing or unsafe: {relative_path}")
        content = source.read_bytes()
        for label, pattern in FORBIDDEN_CONTENT_PATTERNS:
            if pattern.search(content):
                raise ValueError(f"Potential {label} found in release file: {relative_path}")
        validated.append(relative_path)
    return tuple(validated)


def _zip_info(archive_path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(archive_path, date_time=ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = ZIP_FILE_MODE
    return info


def _write_zip(
    target: Path,
    *,
    project_root: Path,
    archive_root: str,
    version: str,
    files: Sequence[Path],
) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative_path in files:
            archive_path = f"{archive_root}/{relative_path.as_posix()}"
            archive.writestr(_zip_info(archive_path), (project_root / relative_path).read_bytes())
        archive.writestr(_zip_info(f"{archive_root}/VERSION"), f"{version}\n".encode("utf-8"))


def build_release(project_root: Path = PROJECT_ROOT, output_dir: Path | None = None) -> ReleaseResult:
    project_root = project_root.resolve()
    version = read_project_version(project_root / "pyproject.toml")
    files = validate_runtime_files(project_root, RUNTIME_FILES)
    destination = (output_dir or project_root / "dist").resolve()
    destination.mkdir(parents=True, exist_ok=True)

    archive_name = f"onenote-mcp-server-{version}.zip"
    archive_path = destination / archive_name
    checksum_path = destination / f"{archive_name}.sha256"
    archive_root = f"onenote-mcp-server-{version}"

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix=f".{archive_name}.", dir=destination, delete=False) as temporary:
            temporary_path = Path(temporary.name)
        _write_zip(
            temporary_path,
            project_root=project_root,
            archive_root=archive_root,
            version=version,
            files=files,
        )
        os.replace(temporary_path, archive_path)
        archive_path.chmod(0o644)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    checksum_path.write_text(f"{digest}  {archive_name}\n", encoding="utf-8")
    return ReleaseResult(version, archive_path, checksum_path, digest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, help="Output directory; defaults to ./dist")
    args = parser.parse_args()
    result = build_release(output_dir=args.output_dir)
    print(
        json.dumps(
            {
                "version": result.version,
                "archive": str(result.archive),
                "checksum_file": str(result.checksum_file),
                "sha256": result.sha256,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
