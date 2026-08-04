#!/usr/bin/env python3
from __future__ import annotations

import html
import importlib.util
import os
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
STAGING = ROOT / "tool" / "staging"
DEV_DOCS = Path(os.environ.get("CAMP_DEV_DOCS", WORKSPACE / "dev" / "docs"))
API_SRC = Path(os.environ.get("CAMP_API_SRC", ROOT / "api-src"))

CAMP_DECLARATION_KEYWORDS = {
    "abstract",
    "alias",
    "class",
    "enum",
    "export",
    "extern",
    "fixed",
    "inline",
    "interface",
    "internal",
    "namespace",
    "newtype",
    "override",
    "public",
    "sealed",
    "shadow",
    "static",
    "struct",
    "virtual",
}

CAMP_STATEMENT_KEYWORDS = {
    "await",
    "break",
    "case",
    "catch",
    "continue",
    "default",
    "delete",
    "do",
    "else",
    "finally",
    "for",
    "foreach",
    "goto",
    "if",
    "import",
    "init",
    "new",
    "postpone",
    "return",
    "switch",
    "throw",
    "try",
    "while",
    "within",
    "yield",
}

CAMP_MODIFIER_KEYWORDS = {
    "const",
    "constof",
    "copyable",
    "escaped",
    "implements",
    "in",
    "once",
    "out",
    "overload",
    "scoped",
    "thrown",
    "unsafe",
    "unscoped",
    "volatile",
}

CAMP_TYPE_KEYWORDS = {
    "achar",
    "any",
    "astring",
    "async",
    "auto",
    "bool",
    "byte",
    "char",
    "classtype",
    "delegate",
    "double",
    "float",
    "fn",
    "int",
    "iter",
    "long",
    "nint",
    "nuint",
    "sbyte",
    "short",
    "string",
    "uchar",
    "uint",
    "ulong",
    "ushort",
    "void",
    "wchar",
    "wstring",
}

CAMP_CONSTANTS = {"false", "null", "true"}
CAMP_INTRINSICS = {"caller", "sizeof", "sourceof", "typenameof", "vtableof"}
CAMP_KEYWORDS = CAMP_DECLARATION_KEYWORDS | CAMP_STATEMENT_KEYWORDS | CAMP_MODIFIER_KEYWORDS
CAMP_TOKEN_RE = re.compile(
    r"(?P<comment>//[^\n]*|/\*.*?\*/)"
    r"|(?P<string>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')"
    r"|(?P<attribute>@[A-Za-z_][A-Za-z0-9_]*)"
    r"|(?P<number>\b(?:0x[0-9A-Fa-f_]+|0b[01_]+|\d(?:[\d_]*\d)?(?:\.\d(?:[\d_]*\d)?)?(?:[eE][+-]?\d(?:[\d_]*\d)?)?)\b)"
    r"|(?P<word>\b[A-Za-z_][A-Za-z0-9_]*\b)",
    re.DOTALL,
)
FENCED_CAMP_RE = re.compile(r"^(`{3,})(?:camp|Camp)[^\n]*\n(.*?)^\1[ \t]*$", re.MULTILINE | re.DOTALL)
SOURCE_FRONT_MATTER_RE = re.compile(r"\A\+\+\+\n(.*?)\n\+\+\+\n\n?", re.DOTALL)
SOURCE_FRONT_MATTER_VALUE_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"(.*)"\s*$', re.MULTILINE)


def clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def write_text_if_changed(path: Path, text: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def copy_file_if_changed(source: Path, destination: Path) -> None:
    if destination.exists() and source.read_bytes() == destination.read_bytes():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def sync_tree(source: Path, destination: Path, preserve_extra: set[str] | None = None) -> None:
    preserve_extra = preserve_extra or set()
    destination.mkdir(parents=True, exist_ok=True)
    expected: set[Path] = set()

    for source_path in source.rglob("*"):
        if source_path.name in {".DS_Store", ".gitkeep"}:
            continue
        relative = source_path.relative_to(source)
        expected.add(relative)
        destination_path = destination / relative
        if source_path.is_dir():
            destination_path.mkdir(parents=True, exist_ok=True)
        else:
            copy_file_if_changed(source_path, destination_path)

    for destination_path in sorted(destination.rglob("*"), reverse=True):
        relative = destination_path.relative_to(destination)
        if relative.parts and relative.parts[0] in preserve_extra:
            continue
        if relative in expected:
            continue
        if destination_path.is_dir():
            try:
                destination_path.rmdir()
            except OSError:
                pass
        else:
            destination_path.unlink()


def copy_vendor_scripts() -> None:
    swup_source = ROOT / "node_modules" / "swup" / "dist" / "Swup.umd.js"
    if not swup_source.exists():
        raise FileNotFoundError("Swup is not installed. Run `npm install` before building the website.")

    js_dir = STAGING / "static" / "js"
    js_dir.mkdir(parents=True, exist_ok=True)
    copy_file_if_changed(swup_source, js_dir / "swup.umd.js")


def title_from_markdown(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def read_source_front_matter(text: str) -> tuple[dict[str, str], str]:
    match = SOURCE_FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text

    values = {item.group(1): item.group(2) for item in SOURCE_FRONT_MATTER_VALUE_RE.finditer(match.group(1))}
    return values, text[match.end() :]


def doc_weight(path: Path) -> int:
    match = re.match(r"^(\d+)-", path.name)
    if match:
        return int(match.group(1))
    if path.name == "index.md":
        return 0
    return 100


def numbered_title(path: Path, title: str) -> str:
    match = re.match(r"^(\d+)-", path.name)
    if not match:
        return title
    return f"{int(match.group(1))}. {title}"


def replace_markdown_title(text: str, title: str) -> str:
    return re.sub(r"^# .*$", f"# {title}", text, count=1, flags=re.MULTILINE)


def camp_token_class(match: re.Match[str]) -> str | None:
    group = match.lastgroup
    value = match.group()
    if group == "comment":
        return "c-comment"
    if group == "string":
        return "c-string"
    if group == "attribute":
        return "c-attribute"
    if group == "number":
        return "c-number"
    if group == "word":
        if value in CAMP_KEYWORDS:
            return "c-keyword"
        if value in CAMP_TYPE_KEYWORDS:
            return "c-type"
        if value in CAMP_INTRINSICS:
            return "c-intrinsic"
        if value in CAMP_CONSTANTS:
            return "c-constant"
    return None


def highlight_camp_code(code: str) -> str:
    result: list[str] = []
    offset = 0
    for match in CAMP_TOKEN_RE.finditer(code):
        result.append(html.escape(code[offset : match.start()]))
        token = html.escape(match.group())
        token_class = camp_token_class(match)
        if token_class is None:
            result.append(token)
        else:
            result.append(f'<span class="{token_class}">{token}</span>')
        offset = match.end()
    result.append(html.escape(code[offset:]))
    return "".join(result)


def render_camp_fences(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        highlighted = highlight_camp_code(match.group(2))
        return f'<pre class="camp-code"><code data-lang="camp">{highlighted}</code></pre>'

    return FENCED_CAMP_RE.sub(replace, text)


def remove_markdown_title(text: str) -> str:
    return re.sub(r"^# .*$\n?", "", text, count=1, flags=re.MULTILINE).lstrip()


def write_section(
    path: Path,
    title: str,
    sort_by: str = "weight",
    weight: int | None = None,
    content: str = "",
) -> None:
    path.mkdir(parents=True, exist_ok=True)
    lines = [
        "+++",
        f'title = "{title}"',
        f'sort_by = "{sort_by}"',
    ]
    if weight is not None:
        lines.append(f"weight = {weight}")
    lines.extend(
        [
            'template = "docs_section.html"',
            'page_template = "docs_page.html"',
            "+++",
            "",
        ]
    )
    write_text_if_changed(path / "_index.md", "\n".join(lines) + content)


def copy_docs(source_dir: Path, destination_dir: Path, section_title: str, section_weight: int) -> None:
    index = source_dir / "index.md"
    section_content = ""
    if index.exists():
        _, index_text = read_source_front_matter(index.read_text(encoding="utf-8"))
        section_content = render_camp_fences(remove_markdown_title(index_text))
    write_section(destination_dir, section_title, weight=section_weight, content=section_content)
    for source in sorted(source_dir.glob("*.md")):
        if source.name == "index.md":
            continue

        source_front_matter, text = read_source_front_matter(source.read_text(encoding="utf-8"))
        title = title_from_markdown(text, source.stem)
        nav_title = source_front_matter.get("nav_title", numbered_title(source, title))
        text = replace_markdown_title(text, title)
        text = render_camp_fences(text)
        destination = destination_dir / f"{source.stem}.md"
        front_matter_lines = [
            "+++",
            f'title = "{title}"',
        ]
        front_matter_lines.extend(
            [
                f"weight = {doc_weight(source)}",
                'template = "docs_page.html"',
            ]
        )
        if nav_title != title:
            front_matter_lines.extend(
                [
                    "",
                    "[extra]",
                    f'nav_title = "{nav_title}"',
                ]
            )
        front_matter_lines.extend(["+++", ""])
        front_matter = "\n".join(front_matter_lines)
        write_text_if_changed(destination, front_matter + text)


def docs_index_content() -> str:
    return """
The Camp documentation is split into guides for learning the language, using the
compiler, and reading generated API references. Start with the language guide if
you are new to Camp; use the other sections when you need the compiler,
standard library, or package surface in front of you.

<div class="link-list">
    <a href="/docs/language/01-camp-in-one-page/">
        <span>Language Guide</span>
        <small>Learn Camp as a language for writing clear C-like code, from small programs through declarations, types, allocation, errors, generics, iterators, async, and interop.</small>
    </a>
    <a href="/docs/compiler/01-campc-command-line/">
        <span>Compiler Guide</span>
        <small>Use campc, build files, packages, targets, metadata, diagnostics, editor tooling, debugging, and standard-library build integration.</small>
    </a>
    <a href="/docs/stdlib/overview/">
        <span>Standard Library API</span>
        <small>Browse the standard library surface generated from Camp metadata.</small>
    </a>
    <a href="/docs/packages/overview/">
        <span>Package APIs</span>
        <small>Package API references will appear here when they are available.</small>
    </a>
</div>
"""


def generate_api_docs(docs_root: Path) -> bool:
    generator_path = ROOT / "tool" / "api-docs" / "generate_api_docs.py"
    if not generator_path.exists():
        return False

    spec = importlib.util.spec_from_file_location("camp_api_docs_generator", generator_path)
    if spec is None or spec.loader is None:
        return False

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.generate_api_docs(API_SRC, docs_root)
    return True


def write_generated_docs() -> None:
    docs_root = STAGING / "content" / "docs"
    write_section(docs_root, "Docs", content=docs_index_content())
    copy_docs(DEV_DOCS / "language", docs_root / "language", "Language Guide", section_weight=1)
    copy_docs(DEV_DOCS / "compiler", docs_root / "compiler", "Compiler Guide", section_weight=2)
    generate_api_docs(docs_root)


def main() -> None:
    STAGING.mkdir(parents=True, exist_ok=True)
    sync_tree(ROOT / "content", STAGING / "content", preserve_extra={"docs"})
    sync_tree(ROOT / "tool" / "templates", STAGING / "templates")
    sync_tree(ROOT / "tool" / "sass", STAGING / "sass")
    sync_tree(ROOT / "tool" / "static", STAGING / "static", preserve_extra={"CNAME", "pagefind"})
    copy_vendor_scripts()
    copy_file_if_changed(ROOT / "tool" / "config.toml", STAGING / "config.toml")
    write_generated_docs()
    write_text_if_changed(STAGING / "static" / "CNAME", "camplang.org\n")


if __name__ == "__main__":
    main()
