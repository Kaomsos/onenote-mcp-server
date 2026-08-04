import hashlib
import os
import zipfile
from pathlib import Path

from scripts.build_release import (
    FORBIDDEN_CONTENT_PATTERNS,
    RUNTIME_FILES,
    build_release,
    read_project_version,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_project_and_lock_versions_are_2_1_0():
    assert read_project_version(PROJECT_ROOT / "pyproject.toml") == "2.1.0"
    lock = (PROJECT_ROOT / "uv.lock").read_text(encoding="utf-8")
    package_block = 'name = "onenote-mcp-server"\nversion = "2.1.0"'
    assert package_block in lock


def test_release_archive_has_expected_runtime_files_and_checksum(tmp_path):
    result = build_release(PROJECT_ROOT, tmp_path)

    assert result.version == "2.1.0"
    assert result.archive.name == "onenote-mcp-server-2.1.0.zip"
    assert result.checksum_file.name == "onenote-mcp-server-2.1.0.zip.sha256"
    assert hashlib.sha256(result.archive.read_bytes()).hexdigest() == result.sha256
    assert result.checksum_file.read_text(encoding="utf-8") == (
        f"{result.sha256}  {result.archive.name}\n"
    )
    if os.name != "nt":
        assert result.archive.stat().st_mode & 0o777 == 0o644

    prefix = "onenote-mcp-server-2.1.0/"
    expected = {f"{prefix}{path.as_posix()}" for path in RUNTIME_FILES}
    expected.add(f"{prefix}VERSION")
    with zipfile.ZipFile(result.archive) as archive:
        assert set(archive.namelist()) == expected
        assert {
            f"{prefix}docs/README.md",
            f"{prefix}docs/product/README.md",
            f"{prefix}docs/product/local_onenote_com_mcp_research.md",
            f"{prefix}docs/product/merge_onenote_agent_handler.md",
            f"{prefix}docs/todos/README.md",
            f"{prefix}docs/todos/page_content_search.md",
            f"{prefix}docs/todos/page_hierarchy_support.md",
            f"{prefix}docs/todos/page_section_copy_move.md",
            f"{prefix}docs/todos/reference_project_feature_parity.md",
            f"{prefix}docs/todos/three_level_crud_gap.md",
        } <= set(archive.namelist())
        assert archive.read(f"{prefix}VERSION") == b"2.1.0\n"
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())

        forbidden = (
            ".git",
            ".venv",
            "__pycache__",
            ".pytest_cache",
            ".mcp.json",
            ".codex/config.toml",
            ".env",
            "tests/",
            "dist/",
        )
        assert not any(marker in name for name in archive.namelist() for marker in forbidden)
        for name in archive.namelist():
            content = archive.read(name)
            assert not any(pattern.search(content) for _, pattern in FORBIDDEN_CONTENT_PATTERNS)


def test_release_archive_is_reproducible(tmp_path):
    first = build_release(PROJECT_ROOT, tmp_path / "first")
    second = build_release(PROJECT_ROOT, tmp_path / "second")

    assert first.archive.read_bytes() == second.archive.read_bytes()
    assert first.sha256 == second.sha256
