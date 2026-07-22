#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
STAGING = ROOT / "tool" / "staging"
DEV_DOCS = WORKSPACE / "dev" / "docs"


def clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns(".DS_Store", ".gitkeep"))


def title_from_markdown(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def doc_weight(path: Path) -> int:
    match = re.match(r"^(\d+)-", path.name)
    if match:
        return int(match.group(1))
    if path.name == "index.md":
        return 0
    return 100


def write_section(path: Path, title: str, sort_by: str = "weight") -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "_index.md").write_text(
        "+++\n"
        f"title = \"{title}\"\n"
        f"sort_by = \"{sort_by}\"\n"
        "template = \"docs_section.html\"\n"
        "page_template = \"docs_page.html\"\n"
        "+++\n\n",
        encoding="utf-8",
    )


def copy_docs(source_dir: Path, destination_dir: Path, section_title: str) -> None:
    write_section(destination_dir, section_title)
    for source in sorted(source_dir.glob("*.md")):
        text = source.read_text(encoding="utf-8")
        title = title_from_markdown(text, source.stem)
        slug = "_index" if source.name == "index.md" else source.stem
        destination = destination_dir / f"{slug}.md"
        if source.name == "index.md":
            continue
        front_matter = (
            "+++\n"
            f"title = \"{title}\"\n"
            f"weight = {doc_weight(source)}\n"
            "template = \"docs_page.html\"\n"
            "+++\n\n"
        )
        destination.write_text(front_matter + text, encoding="utf-8")


def write_generated_docs() -> None:
    docs_root = STAGING / "content" / "docs"
    write_section(docs_root, "Docs")
    copy_docs(DEV_DOCS / "language", docs_root / "language", "Language Guide")
    copy_docs(DEV_DOCS / "compiler", docs_root / "compiler", "Compiler Guide")

    stdlib = docs_root / "stdlib"
    write_section(stdlib, "Standard Library API")
    (stdlib / "overview.md").write_text(
        "+++\n"
        "title = \"Standard Library API\"\n"
        "weight = 1\n"
        "template = \"docs_page.html\"\n"
        "+++\n\n"
        "# Standard Library API\n\n"
        "The standard library API reference will be generated from Camp metadata. "
        "This placeholder exists so the first site build has the final navigation shape.\n",
        encoding="utf-8",
    )

    packages = docs_root / "packages"
    write_section(packages, "Package APIs")
    package_root = WORKSPACE / "pkg.camplang.org"
    entries = [path for path in sorted(package_root.iterdir()) if path.is_dir() and not path.name.startswith(".")]
    if not entries:
        (packages / "overview.md").write_text(
            "+++\n"
            "title = \"Package APIs\"\n"
            "weight = 1\n"
            "template = \"docs_page.html\"\n"
            "+++\n\n"
            "# Package APIs\n\nNo package API references are available yet.\n",
            encoding="utf-8",
        )
    for index, package in enumerate(entries, start=1):
        package_dir = packages / package.name
        write_section(package_dir, package.name)
        (package_dir / "overview.md").write_text(
            "+++\n"
            f"title = \"{package.name} API\"\n"
            f"weight = {index}\n"
            "template = \"docs_page.html\"\n"
            "+++\n\n"
            f"# {package.name} API\n\n"
            "This package API reference will be generated from Camp metadata. "
            f"For now, this page reserves the documentation home for `{package.name}`.\n",
            encoding="utf-8",
        )


def main() -> None:
    clean_dir(STAGING)
    copy_tree(ROOT / "content", STAGING / "content")
    copy_tree(ROOT / "tool" / "templates", STAGING / "templates")
    copy_tree(ROOT / "tool" / "sass", STAGING / "sass")
    copy_tree(ROOT / "tool" / "static", STAGING / "static")
    shutil.copy2(ROOT / "tool" / "config.toml", STAGING / "config.toml")
    write_generated_docs()
    (STAGING / "static" / "CNAME").write_text("camplang.org\n", encoding="utf-8")


if __name__ == "__main__":
    main()

