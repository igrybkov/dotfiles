"""Tests for symlink_dotfiles core functionality."""

import pytest
from pathlib import Path

from symlink_dotfiles.core import (
    DEFAULT_DIRECTORY_MARKER,
    DEFAULT_EXCLUDE_PATTERNS,
    SymlinkResult,
    create_symlink,
    find_marker_directories,
    is_inside_marker_dir,
    matches_exclude_pattern,
    symlink_dotfiles,
)


@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    """Create a source directory with test files."""
    src = tmp_path / "source"
    src.mkdir()
    (src / "file1.txt").write_text("content1")
    (src / "subdir").mkdir()
    (src / "subdir" / "file2.txt").write_text("content2")
    return src


@pytest.fixture
def target_dir(tmp_path: Path) -> Path:
    """Create an empty target directory."""
    target = tmp_path / "target"
    target.mkdir()
    return target


class TestSymlinkResult:
    """Tests for SymlinkResult dataclass."""

    def test_empty_result_not_changed(self):
        result = SymlinkResult()
        assert not result.changed
        assert not result.failed

    def test_created_is_changed(self):
        result = SymlinkResult(created=["a"])
        assert result.changed
        assert not result.failed

    def test_updated_is_changed(self):
        result = SymlinkResult(updated=["a"])
        assert result.changed
        assert not result.failed

    def test_conflicts_is_failed(self):
        result = SymlinkResult(conflicts=["a"])
        assert result.failed

    def test_errors_is_failed(self):
        result = SymlinkResult(errors=["a"])
        assert result.failed

    def test_to_dict(self):
        result = SymlinkResult(
            created=["a", "b"],
            updated=["c"],
            skipped=["d", "e", "f"],
            conflicts=["g"],
        )
        d = result.to_dict()
        assert d["changed"] is True
        assert d["failed"] is True
        assert d["created"] == 2
        assert d["updated"] == 1
        assert d["skipped"] == 3
        assert d["conflicts"] == ["g"]


class TestFindMarkerDirectories:
    """Tests for find_marker_directories function."""

    def test_no_markers(self, source_dir: Path):
        markers = find_marker_directories(source_dir, DEFAULT_DIRECTORY_MARKER)
        assert markers == []

    def test_single_marker(self, source_dir: Path):
        marker_dir = source_dir / "marked"
        marker_dir.mkdir()
        (marker_dir / DEFAULT_DIRECTORY_MARKER).touch()

        markers = find_marker_directories(source_dir, DEFAULT_DIRECTORY_MARKER)
        assert markers == [marker_dir]

    def test_nested_marker(self, source_dir: Path):
        marker_dir = source_dir / "level1" / "level2" / "marked"
        marker_dir.mkdir(parents=True)
        (marker_dir / DEFAULT_DIRECTORY_MARKER).touch()

        markers = find_marker_directories(source_dir, DEFAULT_DIRECTORY_MARKER)
        assert markers == [marker_dir]


class TestIsInsideMarkerDir:
    """Tests for is_inside_marker_dir function."""

    def test_not_inside(self, tmp_path: Path):
        marker_dirs = [tmp_path / "a", tmp_path / "b"]
        path = tmp_path / "c" / "file.txt"
        assert not is_inside_marker_dir(path, marker_dirs)

    def test_inside(self, tmp_path: Path):
        marker_dir = tmp_path / "marker"
        marker_dirs = [marker_dir]
        path = marker_dir / "subdir" / "file.txt"
        assert is_inside_marker_dir(path, marker_dirs)


class TestCreateSymlink:
    """Tests for create_symlink function."""

    def test_creates_new_symlink(self, source_dir: Path, target_dir: Path):
        source = source_dir / "file1.txt"
        target = target_dir / "link.txt"

        status = create_symlink(source, target)

        assert status == "created"
        assert target.is_symlink()
        assert target.resolve() == source.resolve()

    def test_skips_identical_symlink(self, source_dir: Path, target_dir: Path):
        source = source_dir / "file1.txt"
        target = target_dir / "link.txt"
        target.symlink_to(source.resolve())

        status = create_symlink(source, target)

        assert status == "skipped"

    def test_updates_different_symlink(self, source_dir: Path, target_dir: Path):
        source1 = source_dir / "file1.txt"
        source2 = source_dir / "subdir" / "file2.txt"
        target = target_dir / "link.txt"
        target.symlink_to(source1.resolve())

        status = create_symlink(source2, target)

        assert status == "updated"
        assert target.resolve() == source2.resolve()

    def test_detects_conflict_with_file(self, source_dir: Path, target_dir: Path):
        source = source_dir / "file1.txt"
        target = target_dir / "link.txt"
        target.write_text("existing")

        status = create_symlink(source, target)

        assert status == "conflict"
        # File should not be modified
        assert target.read_text() == "existing"

    def test_detects_conflict_with_directory(self, source_dir: Path, target_dir: Path):
        source = source_dir / "file1.txt"
        target = target_dir / "link"
        target.mkdir()

        status = create_symlink(source, target)

        assert status == "conflict"

    def test_dry_run_does_not_create(self, source_dir: Path, target_dir: Path):
        source = source_dir / "file1.txt"
        target = target_dir / "link.txt"

        status = create_symlink(source, target, dry_run=True)

        assert status == "created"
        assert not target.exists()

    def test_creates_parent_directories(self, source_dir: Path, target_dir: Path):
        source = source_dir / "file1.txt"
        target = target_dir / "a" / "b" / "c" / "link.txt"

        status = create_symlink(source, target)

        assert status == "created"
        assert target.is_symlink()


class TestSymlinkDotfiles:
    """Tests for symlink_dotfiles main function."""

    def test_creates_symlinks(self, source_dir: Path, target_dir: Path):
        result = symlink_dotfiles([source_dir], target_dir)

        assert len(result.created) == 2
        assert result.changed
        assert not result.failed
        assert (target_dir / "file1.txt").is_symlink()
        assert (target_dir / "subdir" / "file2.txt").is_symlink()

    def test_with_prefix(self, source_dir: Path, target_dir: Path):
        result = symlink_dotfiles([source_dir], target_dir, prefix=".")

        assert (target_dir / ".file1.txt").is_symlink()
        assert (target_dir / ".subdir" / "file2.txt").is_symlink()
        assert len(result.created) == 2

    def test_idempotent(self, source_dir: Path, target_dir: Path):
        symlink_dotfiles([source_dir], target_dir)
        result = symlink_dotfiles([source_dir], target_dir)

        assert len(result.skipped) == 2
        assert len(result.created) == 0
        assert not result.changed

    def test_detects_conflicts(self, source_dir: Path, target_dir: Path):
        (target_dir / "file1.txt").write_text("existing")

        result = symlink_dotfiles([source_dir], target_dir)

        assert len(result.conflicts) == 1
        assert result.failed

    def test_exclude_dirs(self, source_dir: Path, target_dir: Path):
        result = symlink_dotfiles([source_dir], target_dir, exclude_dirs=["subdir"])

        assert len(result.created) == 1
        assert not (target_dir / "subdir").exists()

    def test_marker_directory(self, source_dir: Path, target_dir: Path):
        marker_dir = source_dir / "marked_dir"
        marker_dir.mkdir()
        (marker_dir / DEFAULT_DIRECTORY_MARKER).touch()
        (marker_dir / "nested.txt").write_text("nested")

        _result = symlink_dotfiles([source_dir], target_dir)

        # Should symlink the directory, not individual files
        assert (target_dir / "marked_dir").is_symlink()
        # The nested file should be accessible through the symlink
        assert (target_dir / "marked_dir" / "nested.txt").read_text() == "nested"
        # But we should NOT have created a symlink for the nested file
        assert not (target_dir / "marked_dir" / "nested.txt").is_symlink()

    def test_dry_run(self, source_dir: Path, target_dir: Path):
        result = symlink_dotfiles([source_dir], target_dir, dry_run=True)

        assert len(result.created) == 2
        assert not any(target_dir.iterdir())  # Nothing actually created

    def test_multiple_source_dirs(self, tmp_path: Path, target_dir: Path):
        # Create two source directories
        src1 = tmp_path / "src1"
        src1.mkdir()
        (src1 / "file1.txt").write_text("from src1")

        src2 = tmp_path / "src2"
        src2.mkdir()
        (src2 / "file2.txt").write_text("from src2")

        result = symlink_dotfiles([src1, src2], target_dir)

        assert len(result.created) == 2
        assert (target_dir / "file1.txt").is_symlink()
        assert (target_dir / "file2.txt").is_symlink()

    def test_nonexistent_source_skipped(self, tmp_path: Path, target_dir: Path):
        nonexistent = tmp_path / "nonexistent"

        result = symlink_dotfiles([nonexistent], target_dir)

        assert len(result.created) == 0
        assert not result.failed

    def test_skips_marker_files(self, source_dir: Path, target_dir: Path):
        # Add a marker file to source (not in a directory to be symlinked)
        (source_dir / DEFAULT_DIRECTORY_MARKER).touch()

        _result = symlink_dotfiles([source_dir], target_dir)

        # Marker file should not be symlinked
        assert not (target_dir / DEFAULT_DIRECTORY_MARKER).exists()

    def test_excludes_dotfiles_by_default(self, source_dir: Path, target_dir: Path):
        # Add hidden files that should be excluded by default
        (source_dir / ".DS_Store").touch()
        (source_dir / ".gitignore").write_text("*.pyc")

        _result = symlink_dotfiles([source_dir], target_dir)

        # Dotfiles in source should not be symlinked
        assert not (target_dir / ".DS_Store").exists()
        assert not (target_dir / ".gitignore").exists()
        # But regular files should still be symlinked
        assert (target_dir / "file1.txt").is_symlink()

    def test_exclude_patterns_custom(self, source_dir: Path, target_dir: Path):
        (source_dir / "file.log").write_text("log")
        (source_dir / "data.tmp").write_text("tmp")

        _result = symlink_dotfiles(
            [source_dir], target_dir, exclude_patterns=["*.log", "*.tmp"]
        )

        assert not (target_dir / "file.log").exists()
        assert not (target_dir / "data.tmp").exists()
        assert (target_dir / "file1.txt").is_symlink()

    def test_exclude_patterns_empty_includes_all(
        self, source_dir: Path, target_dir: Path
    ):
        # Add a dotfile that would normally be excluded
        (source_dir / ".hidden").write_text("hidden")

        _result = symlink_dotfiles([source_dir], target_dir, exclude_patterns=[])

        # With empty exclude patterns, even dotfiles should be symlinked
        assert (target_dir / ".hidden").is_symlink()


class TestMatchesExcludePattern:
    """Tests for matches_exclude_pattern function."""

    def test_exact_match(self):
        assert matches_exclude_pattern(".DS_Store", [".DS_Store"])

    def test_wildcard_match(self):
        assert matches_exclude_pattern(".gitignore", [".*"])
        assert matches_exclude_pattern("file.bak", ["*.bak"])

    def test_no_match(self):
        assert not matches_exclude_pattern("file.txt", ["*.bak", "*.log"])

    def test_empty_patterns(self):
        assert not matches_exclude_pattern("file.txt", [])

    def test_default_patterns(self):
        assert matches_exclude_pattern(".DS_Store", DEFAULT_EXCLUDE_PATTERNS)
        assert matches_exclude_pattern(".gitignore", DEFAULT_EXCLUDE_PATTERNS)
        assert matches_exclude_pattern("file.swp", DEFAULT_EXCLUDE_PATTERNS)
        assert matches_exclude_pattern("file~", DEFAULT_EXCLUDE_PATTERNS)
        assert not matches_exclude_pattern("regular_file.txt", DEFAULT_EXCLUDE_PATTERNS)
