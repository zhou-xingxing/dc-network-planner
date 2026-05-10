#!/usr/bin/env python3
"""按项目区域统计代码行数。

本脚本只使用 Python 标准库，方便在尚未安装前端/后端依赖的全新开发环境中直接运行。

统计规则：
- 每一行物理文本行先去掉首尾空白；如果不是空行，也不是整行注释，就统计为 1 行代码。
- Python、YAML、TOML 中，以 ``#`` 开头的行视为整行注释，不计入代码行。
- JS、Vue、CSS、HTML 中，以 ``//``、``/*``、``<!--`` 开头的行视为整行注释，不计入代码行；
  多行块注释中的后续行也不计入代码行。
- 行尾注释仍按代码行统计，例如 ``name = "hcs"  # operator``。
- 只有 ``{``、``}``、``)`` 这类语法结构的行也按代码行统计。
- Python docstring 会按代码行统计，因为它在语法上是字符串表达式，不是 ``#`` 注释。
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


README_START_MARKER = "<!-- code-lines:start -->"
README_END_MARKER = "<!-- code-lines:end -->"

SOURCE_EXTENSIONS = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".mjs",
    ".py",
    ".toml",
    ".ts",
    ".vue",
    ".yaml",
    ".yml",
}

EXCLUDED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "coverage",
    "dist",
    "htmlcov",
    "node_modules",
    "venv",
}

EXCLUDED_FILES = {
    "package-lock.json",
}

FRONTEND_TEST_MARKERS = (
    ".spec.",
    ".test.",
)


@dataclass
class LineStats:
    """Aggregated line counts for a group of files."""

    files: int = 0
    code: int = 0

    def add_file(self, path: Path) -> None:
        """Read one source file and add its counts.

        Args:
            path: Source file to count.
        """
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()

        self.files += 1

        in_block_comment = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            is_comment, in_block_comment = _is_comment_line(
                stripped, path.suffix, in_block_comment
            )
            if not is_comment:
                self.code += 1


def _is_comment_line(
    stripped: str, suffix: str, in_block_comment: bool
) -> tuple[bool, bool]:
    """Return whether a line is comment-only and the next block-comment state."""
    if suffix == ".py":
        return stripped.startswith("#"), False

    if suffix in {".js", ".mjs", ".ts", ".vue", ".css", ".html"}:
        if in_block_comment:
            return True, "*/" not in stripped and "-->" not in stripped
        if stripped.startswith("//"):
            return True, False
        if stripped.startswith(("/*", "<!--")):
            return True, "*/" not in stripped and "-->" not in stripped

    if suffix in {".yaml", ".yml", ".toml"}:
        return stripped.startswith("#"), False

    return False, False


def _iter_source_files(root: Path) -> list[Path]:
    """Return source-like files below root, excluding generated/vendor directories."""
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.name in EXCLUDED_FILES:
            continue
        if path.suffix in SOURCE_EXTENSIONS:
            files.append(path)
    return sorted(files)


def _category_for(path: Path, project_root: Path) -> str | None:
    """Map a source file to a reporting category."""
    relative = path.relative_to(project_root)
    parts = relative.parts

    if parts[:2] == ("backend", "tests"):
        return "backend_tests"
    if parts[0] == "backend":
        return "backend_code"

    if _is_frontend_test(relative):
        return "frontend_tests"
    if parts[0] == "frontend":
        return "frontend_code"

    return None


def _is_frontend_test(relative: Path) -> bool:
    """Return whether a frontend file should be grouped as test code."""
    parts = relative.parts
    name = relative.name
    return parts[0] == "frontend" and (
        "tests" in parts
        or "__tests__" in parts
        or any(marker in name for marker in FRONTEND_TEST_MARKERS)
    )


def count_code_lines(project_root: Path) -> dict[str, LineStats]:
    """Count source lines by fixed project categories.

    Args:
        project_root: Repository root.

    Returns:
        Mapping from category name to line statistics.
    """
    stats = {
        "backend_code": LineStats(),
        "backend_tests": LineStats(),
        "frontend_code": LineStats(),
        "frontend_tests": LineStats(),
    }

    for path in _iter_source_files(project_root):
        category = _category_for(path, project_root)
        if category is None:
            continue
        stats[category].add_file(path)

    return stats


def print_report(stats: dict[str, LineStats]) -> None:
    """Print a compact table for the collected statistics."""
    total = _total_stats(stats)
    rows = _labeled_rows(stats)

    print(f"{'分类':<14} {'文件数':>6} {'代码行':>8}")
    print("-" * 32)
    for label, value in rows:
        print(f"{label:<14} {value.files:>6} {value.code:>8}")

    print("-" * 32)
    print(f"{'合计':<14} {total.files:>6} {total.code:>8}")


def markdown_report(stats: dict[str, LineStats]) -> str:
    """Return a GitHub-friendly Markdown table."""
    total = _total_stats(stats)
    rows = _labeled_rows(stats)
    lines = [
        "| 分类 | 文件数 | 代码行 |",
        "|---|---:|---:|",
    ]

    for label, value in rows:
        lines.append(
            f"| {label} | {_format_number(value.files)} | {_format_number(value.code)} |"
        )

    lines.append(
        f"| 合计 | {_format_number(total.files)} | {_format_number(total.code)} |"
    )
    return "\n".join(lines)


def update_readme(readme_path: Path, stats: dict[str, LineStats]) -> None:
    """Replace the code line statistics block in a README file.

    Args:
        readme_path: README file to update.
        stats: Statistics to render into the README.

    Raises:
        ValueError: If the marker block is missing or malformed.
    """
    original = readme_path.read_text(encoding="utf-8")
    if README_START_MARKER not in original or README_END_MARKER not in original:
        raise ValueError(
            f"README must contain {README_START_MARKER} and {README_END_MARKER}"
        )

    before, rest = original.split(README_START_MARKER, 1)
    _, after = rest.split(README_END_MARKER, 1)
    replacement = (
        f"{README_START_MARKER}\n{markdown_report(stats)}\n{README_END_MARKER}"
    )
    readme_path.write_text(f"{before}{replacement}{after}", encoding="utf-8")


def _labeled_rows(stats: dict[str, LineStats]) -> list[tuple[str, LineStats]]:
    """Return report rows in display order."""
    labels = {
        "backend_code": "后端代码",
        "backend_tests": "后端测试",
        "frontend_code": "前端代码",
        "frontend_tests": "前端测试",
    }
    return [(labels[key], stats[key]) for key in labels]


def _total_stats(stats: dict[str, LineStats]) -> LineStats:
    """Return totals across all categories."""
    total = LineStats()
    for value in stats.values():
        total.files += value.files
        total.code += value.code
    return total


def _format_number(value: int) -> str:
    """Return a number formatted for Markdown tables."""
    return f"{value:,}"


def main() -> None:
    """Parse CLI arguments and print line count statistics."""
    parser = argparse.ArgumentParser(
        description="统计 DC Network Planner 项目前端、后端、测试代码行数"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="项目根目录，默认自动取脚本所在仓库根目录",
    )
    parser.add_argument(
        "--format",
        choices=("text", "markdown"),
        default="text",
        help="输出格式，默认 text",
    )
    parser.add_argument(
        "--update-readme",
        type=Path,
        help="更新 README 中 code-lines 标记包围的统计表",
    )
    args = parser.parse_args()

    stats = count_code_lines(args.root.resolve())
    if args.update_readme:
        update_readme(args.update_readme.resolve(), stats)
    elif args.format == "markdown":
        print(markdown_report(stats))
    else:
        print_report(stats)


if __name__ == "__main__":
    main()
