#!/usr/bin/env python3
from __future__ import annotations

import html
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
STAGING = ROOT / "tool" / "staging"
DEV_DOCS = WORKSPACE / "dev" / "docs"

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
FENCED_CAMP_RE = re.compile(r"```(?:camp|Camp)\n(.*?)\n```", re.DOTALL)
SOURCE_FRONT_MATTER_RE = re.compile(r"\A\+\+\+\n(.*?)\n\+\+\+\n\n?", re.DOTALL)
SOURCE_FRONT_MATTER_VALUE_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"(.*)"\s*$', re.MULTILINE)


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
        highlighted = highlight_camp_code(match.group(1))
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
    (path / "_index.md").write_text("\n".join(lines) + content, encoding="utf-8")


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
        destination.write_text(front_matter + text, encoding="utf-8")


def write_generated_docs() -> None:
    docs_root = STAGING / "content" / "docs"
    write_section(docs_root, "Docs")
    copy_docs(DEV_DOCS / "language", docs_root / "language", "Language Guide", section_weight=1)
    copy_docs(DEV_DOCS / "compiler", docs_root / "compiler", "Compiler Guide", section_weight=2)

    stdlib = docs_root / "stdlib"
    write_section(stdlib, "Standard Library API", weight=3)
    (stdlib / "overview.md").write_text(
        "+++\n"
        'title = "Standard Library API"\n'
        "weight = 1\n"
        'template = "docs_page.html"\n'
        "+++\n\n"
        "# Standard Library API\n\n"
        "The standard library API reference will be generated from Camp metadata. "
        "This placeholder exists so the first site build has the final navigation shape.\n",
        encoding="utf-8",
    )

    packages = docs_root / "packages"
    write_section(packages, "Package APIs", weight=4)
    package_root = WORKSPACE / "pkg.camplang.org"
    entries = [path for path in sorted(package_root.iterdir()) if path.is_dir() and not path.name.startswith(".")]
    if not entries:
        (packages / "overview.md").write_text(
            "+++\n"
            'title = "Package APIs"\n'
            "weight = 1\n"
            'template = "docs_page.html"\n'
            "+++\n\n"
            "# Package APIs\n\nNo package API references are available yet.\n",
            encoding="utf-8",
        )
    for index, package in enumerate(entries, start=1):
        package_dir = packages / package.name
        write_section(package_dir, package.name, weight=index)
        (package_dir / "overview.md").write_text(
            "+++\n"
            f'title = "{package.name} API"\n'
            f"weight = {index}\n"
            'template = "docs_page.html"\n'
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
