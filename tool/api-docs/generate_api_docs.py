from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any


TYPE_KINDS = {"class", "staticClass", "interface", "struct", "newtype", "pseudoType"}
DECLARATION_KINDS = TYPE_KINDS | {"enum"}
API_GROUPS = [
    ("class", "classes", "Classes"),
    ("staticClass", "classes", "Classes"),
    ("struct", "structs", "Structs"),
    ("interface", "interfaces", "Interfaces"),
    ("enum", "enums", "Enums"),
    ("newtype", "newtypes", "Newtypes"),
    ("function", "functions", "Functions"),
    ("variable", "constants", "Constants"),
]
API_GROUP_BY_KIND = {kind: (path, title) for kind, path, title in API_GROUPS}
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

PRIMITIVE_TYPES = [
    ("bool", "Boolean value."),
    ("byte", "Unsigned 8-bit integer."),
    ("sbyte", "Signed 8-bit integer."),
    ("short", "Signed 16-bit integer."),
    ("ushort", "Unsigned 16-bit integer."),
    ("int", "Signed 32-bit integer."),
    ("uint", "Unsigned 32-bit integer."),
    ("long", "Signed 64-bit integer."),
    ("ulong", "Unsigned 64-bit integer."),
    ("nint", "Pointer-sized signed integer."),
    ("nuint", "Pointer-sized unsigned integer."),
    ("float", "32-bit floating-point value."),
    ("double", "64-bit floating-point value."),
]
CHAR_PRIMITIVE_TYPES = [
    ("achar", "Narrow character code unit."),
    ("char", "UTF-8 character code unit."),
    ("wchar", "Wide character code unit."),
    ("uchar", "Unicode scalar value."),
]
PRIMITIVE_TYPE_NAMES = {name for name, _ in [*PRIMITIVE_TYPES, *CHAR_PRIMITIVE_TYPES]}
STRING_TYPES = [
    ("string", "Null-terminated UTF-8 string."),
    ("astring", "Null-terminated narrow string."),
    ("wstring", "Null-terminated wide string."),
]
STRING_TYPE_NAMES = {name for name, _ in STRING_TYPES}
CHAR_ARRAY_STRING_OWNERS = {
    "char": "string",
    "achar": "astring",
    "wchar": "wstring",
}


def generate_api_docs(api_src: Path, docs_root: Path) -> None:
    version = read_text(api_src / "campc-version.txt", "unknown").strip() or "unknown"
    std_metadata = api_src / "stdlib" / "std_api.json"
    if std_metadata.exists():
        ApiReference(std_metadata, docs_root / "stdlib", "Standard Library API", "stdlib", 3, version, grouped_sidebar=True).write()
    else:
        write_placeholder(docs_root / "stdlib", "Standard Library API", 3, "The standard library API reference has not been generated yet.")

    packages_root = docs_root / "packages"
    write_section(packages_root, "Package APIs", weight=4)
    write_page(
        packages_root / "overview.md",
        "Package APIs",
        1,
        "# Package APIs\n\nPackage API references are not available yet.\n",
        nav_title="Overview",
    )


class ApiReference:
    def __init__(self, metadata_path: Path, output_dir: Path, title: str, url_slug: str, weight: int, campc_version: str, grouped_sidebar: bool = False) -> None:
        self.metadata_path = metadata_path
        self.output_dir = output_dir
        self.title = title
        self.url_slug = url_slug.strip("/")
        self.weight = weight
        self.campc_version = campc_version
        self.grouped_sidebar = grouped_sidebar
        self.id_to_url: dict[str, str] = {}
        self.name_to_url: dict[str, str] = {}
        self.detail_urls: dict[str, str] = {}
        self.page_weights: dict[str, int] = {}
        self.type_names: set[str] = set()
        self.written_paths: set[Path] = set()
        self.top_level_function_group_counts: dict[tuple[str, str, str], int] = {}
        self.constant_group_counts: dict[tuple[str, str], int] = {}
        self.types_by_name: dict[str, dict[str, Any]] = {}

    def write(self, metadata: dict[str, Any] | None = None) -> None:
        metadata = metadata or read_metadata(self.metadata_path)
        declarations = [d for d in metadata.get("declarations") or [] if is_public_declaration(d)]

        self.written_paths = set()
        self.write_section(self.output_dir, self.title, weight=self.weight)
        pseudo_types = pseudo_type_declarations(declarations)
        self.type_names = {d.get("name") for d in [*declarations, *pseudo_types] if d.get("kind") in TYPE_KINDS and d.get("name")}
        self.types_by_name = {d["name"]: d for d in [*declarations, *pseudo_types] if d.get("kind") in TYPE_KINDS and d.get("name")}

        types = sorted_declarations([*[d for d in declarations if d.get("kind") in TYPE_KINDS], *pseudo_types])
        enums = sorted_declarations([d for d in declarations if d.get("kind") == "enum"])
        variables = sorted_declarations([d for d in declarations if d.get("kind") == "variable"])
        functions = sorted_declarations([d for d in declarations if d.get("kind") == "function"])
        self.assign_page_weights(types, enums, variables, functions)
        self.assign_overload_group_counts(variables, functions)

        if self.grouped_sidebar:
            self.write_category_sections(declarations, types, enums, variables, functions)

        for obj in [*types, *enums]:
            url = self.object_url(obj)
            if obj.get("id"):
                self.id_to_url[obj["id"]] = url
            if obj.get("name"):
                self.name_to_url[obj["name"]] = url
            for child in public_children_of(obj):
                if child.get("id"):
                    self.id_to_url[child["id"]] = url
                    self.detail_urls[child["id"]] = self.member_detail_url(obj, child)

        for fn in functions:
            if fn.get("id"):
                owner = self.extension_function_owner(fn)
                self.detail_urls[fn["id"]] = self.member_detail_url(owner, fn) if owner is not None else self.top_level_detail_url(fn)

        for variable in variables:
            if variable.get("id"):
                owner = self.extension_variable_owner_type(variable)
                if owner is not None:
                    self.detail_urls[variable["id"]] = self.member_detail_url(owner, variable)

        for obj in types:
            self.write_type_page(obj, functions, variables)
        for obj in enums:
            self.write_enum_page(obj)
        self.write_functions_page(functions)
        self.write_constants_page(variables)
        self.remove_stale_pages()

    def assign_page_weights(self, types: list[dict[str, Any]], enums: list[dict[str, Any]], variables: list[dict[str, Any]], functions: list[dict[str, Any]]) -> None:
        if not self.grouped_sidebar:
            for index, obj in enumerate(sorted_declarations([*types, *enums]), start=1):
                self.page_weights[declaration_key(obj)] = index
            return

        groups = [
            [d for d in types if d.get("kind") in {"class", "staticClass"}],
            [d for d in types if d.get("kind") == "struct"],
            [d for d in types if d.get("kind") == "interface"],
            enums,
            [d for d in types if d.get("kind") == "newtype"],
            [d for d in functions if not receiver_type(d)],
            variables,
        ]
        for items in groups:
            for index, obj in enumerate(sorted_declarations(items), start=1):
                self.page_weights[declaration_key(obj)] = index

    def assign_overload_group_counts(self, variables: list[dict[str, Any]], functions: list[dict[str, Any]]) -> None:
        function_counts: dict[tuple[str, str, str], int] = {}
        for fn in functions:
            if self.grouped_sidebar and self.extension_function_owner(fn) is not None:
                continue
            key = top_level_function_group_key(fn, full_receiver=self.grouped_sidebar)
            function_counts[key] = function_counts.get(key, 0) + 1
        self.top_level_function_group_counts = function_counts

        constant_counts: dict[tuple[str, str], int] = {}
        for variable in variables:
            if self.extension_variable_owner_type(variable) is not None:
                continue
            owner = extension_variable_owner_name(variable)
            if owner is None:
                continue
            key = (category_name(variable), extension_variable_name(variable))
            constant_counts[key] = constant_counts.get(key, 0) + 1
        self.constant_group_counts = constant_counts

    def write_category_sections(
        self,
        declarations: list[dict[str, Any]],
        types: list[dict[str, Any]],
        enums: list[dict[str, Any]],
        variables: list[dict[str, Any]],
        functions: list[dict[str, Any]],
    ) -> None:
        category_functions_all = [fn for fn in functions if self.extension_function_owner(fn) is None]
        category_variables_all = [variable for variable in variables if self.extension_variable_owner_type(variable) is None]
        category_sources = [*types, *enums, *category_variables_all, *category_functions_all]
        for index, category in enumerate(self.categories(category_sources), start=1):
            category_root = self.output_dir / category_slug(category)
            category_declarations = [item for item in category_sources if category_name(item) == category]
            category_types = [item for item in types if category_name(item) == category]
            category_enums = [item for item in enums if category_name(item) == category]
            category_variables = [item for item in category_variables_all if category_name(item) == category]
            category_functions = [item for item in category_functions_all if category_name(item) == category]
            content = self.category_overview(category, category_declarations, category_types, category_enums, category_variables, category_functions)
            self.write_section(category_root, category, weight=index, content=content)

    def write_overview(
        self,
        module_name: str,
        declarations: list[dict[str, Any]],
        types: list[dict[str, Any]],
        enums: list[dict[str, Any]],
        variables: list[dict[str, Any]],
        functions: list[dict[str, Any]],
    ) -> None:
        groups = [
            ("Classes", [d for d in types if d.get("kind") in {"class", "staticClass"}], "class"),
            ("Structs", [d for d in types if d.get("kind") == "struct"], "struct"),
            ("Interfaces", [d for d in types if d.get("kind") == "interface"], "interface"),
            ("Enums", enums, "enum"),
            ("Newtypes", [d for d in types if d.get("kind") == "newtype"], "newtype"),
            ("Functions", [d for d in functions if not receiver_type(d)], "function"),
            ("Constants", variables, "variable"),
        ]
        body = [
            f"<h1>{esc(self.title)}</h1>",
            "",
            '<div class="api-lede">',
            f"<p>Source-level API metadata for <strong>{esc(module_name)}</strong>.</p>",
            f"<p>{len(declarations)} declarations generated with <code>campc {esc(self.campc_version)}</code>.</p>",
            "</div>",
        ]
        for title, items, kind in groups:
            if not items:
                continue
            body.append(f'<section class="api-index-group"><h2>{esc(title)}</h2><div class="api-index-list">')
            for obj in sorted_declarations(items):
                body.append(
                    f'<a class="api-index-row" href="{attr(self.object_url(obj))}">'
                    f'<span class="api-index-kind">{esc(kind)}</span>'
                    f'<span class="api-index-main"><span class="api-signature">{self.index_signature(obj)}</span>'
                    f"{self.summary(obj)}</span></a>"
                )
            body.append("</div></section>")
        body.append(self.footer())
        self.write_page(self.output_dir / "overview.md", self.title, 1, "\n".join(body), nav_title="Overview")

    def categories(self, declarations: list[dict[str, Any]]) -> list[str]:
        return sorted({category_name(item) for item in declarations}, key=lambda value: value.lower())

    def category_overview(
        self,
        category: str,
        declarations: list[dict[str, Any]],
        types: list[dict[str, Any]],
        enums: list[dict[str, Any]],
        variables: list[dict[str, Any]],
        functions: list[dict[str, Any]],
    ) -> str:
        body = [
            '<div class="api-lede">',
            f"<p>{len(declarations)} public declarations in the {esc(category)} category.</p>",
            "</div>",
        ]
        type_items = sorted_declarations([*types, *enums])
        category_functions = functions
        category_variables = variables
        if type_items:
            body.append(f'<section class="api-index-group"><h2>Types</h2>{self.type_rows(type_items, one_column=category in {"Primitives", "Strings"})}</section>')
        if category_functions:
            body.append(f'<section class="api-index-group"><h2>Functions</h2>{self.declaration_rows(category_functions, "function")}</section>')
        if category_variables:
            body.append(f'<section class="api-index-group"><h2>Constants</h2>{self.declaration_rows(category_variables, "variable")}</section>')
        body.append(self.footer())
        return "\n".join(body)

    def write_type_page(self, obj: dict[str, Any], all_functions: list[dict[str, Any]], all_variables: list[dict[str, Any]]) -> None:
        name = display_name(obj)
        extensions = [fn for fn in all_functions if is_public_member(fn, None) and self.extension_function_owner(fn) is obj]
        extension_variables = [variable for variable in all_variables if is_public_member(variable, None) and self.extension_variable_owner_type(variable) is obj]
        lifecycle_members, fields, instance_members, static_members = split_members(obj, extensions, extension_variables)
        body = [
            f"<h1>{esc(name)}</h1>",
            "",
            f'<p class="api-backlink"><a href="{attr(self.category_prefix(obj))}">Back to {esc(category_name(obj))}</a></p>' if self.grouped_sidebar else "",
            "" if obj.get("kind") == "pseudoType" else self.declaration_block(declaration_signature(obj, escape=False)),
            self.metadata(obj),
        ]
        if obj.get("kind") == "newtype" and obj.get("callableType") and obj.get("parameters"):
            body.append(self.parameters(obj.get("parameters") or []))
        body.append(self.member_section("Lifecycle members", obj, lifecycle_members))
        body.append(self.member_section("Instance fields", obj, fields))
        body.append(self.member_section("Instance members", obj, instance_members))
        body.append(self.member_section("Static members", obj, static_members))
        if not lifecycle_members and not fields and not instance_members and not static_members:
            body.append('<p class="api-empty">No members.</p>')
        body.append(self.footer())
        self.write_page(self.declaration_path(obj), name, self.declaration_weight(obj), "\n".join(filter(None, body)), nav_title=name, nav_hidden=self.grouped_sidebar)
        for member in [*lifecycle_members, *fields, *instance_members, *static_members]:
            self.write_member_detail(obj, member)
        for member in [*collapse_overload_items(instance_members), *collapse_overload_items(static_members)]:
            if member[0] == "overload-group":
                self.write_overload_group_detail(obj, member)

    def write_enum_page(self, obj: dict[str, Any]) -> None:
        name = display_name(obj)
        values = [("enum-value", v, False, {}) for v in obj.get("values") or [] if is_public_member(v, obj)]
        body = [
            f"<h1>{esc(name)}</h1>",
            "",
            f'<p class="api-backlink"><a href="{attr(self.category_prefix(obj))}">Back to {esc(category_name(obj))}</a></p>' if self.grouped_sidebar else "",
            self.declaration_block(declaration_signature(obj, escape=False)),
            self.metadata(obj),
            self.member_section("Values", obj, values, preserve_order=True),
            self.footer(),
        ]
        self.write_page(self.declaration_path(obj), name, self.declaration_weight(obj), "\n".join(filter(None, body)), nav_title=name, nav_hidden=self.grouped_sidebar)

    def write_functions_page(self, functions: list[dict[str, Any]]) -> None:
        free = [fn for fn in functions if self.extension_function_owner(fn) is None] if self.grouped_sidebar else [fn for fn in functions if not receiver_type(fn)]
        if not self.grouped_sidebar:
            body = ["<h1>Functions</h1>", "", self.declaration_rows(free, "function"), self.footer()]
            self.write_page(self.output_dir / "functions.md", "Functions", 9000, "\n".join(body), nav_hidden=True)
        for index, fn in enumerate(sorted_declarations(free), start=1):
            self.write_top_level_detail(fn, index)
        for item in collapse_overload_items([("function", fn, False, {"fullReceiver": self.grouped_sidebar}) for fn in sorted_declarations(free)]):
            if item[0] == "overload-group":
                self.write_top_level_overload_group_detail(item)

    def write_constants_page(self, variables: list[dict[str, Any]]) -> None:
        variables = [variable for variable in variables if self.extension_variable_owner_type(variable) is None] if self.grouped_sidebar else variables
        if not self.grouped_sidebar:
            body = ["<h1>Constants</h1>", "", self.declaration_rows(variables, "variable"), self.footer()]
            self.write_page(self.output_dir / "constants.md", "Constants", 9001, "\n".join(body), nav_hidden=True)
        for index, variable in enumerate(sorted_declarations(variables), start=1):
            self.write_constant_detail(variable, index)
        for item in collapse_constant_overload_items([("variable", variable, False, {}) for variable in sorted_declarations(variables)], self.type_names):
            if item[0] == "constant-overload-group":
                self.write_constant_overload_group_detail(item)

    def write_member_detail(self, owner: dict[str, Any], item: tuple[str, dict[str, Any], bool, dict[str, Any]]) -> None:
        kind, obj, omit_receiver, options = item
        title = f"{owner.get('name', 'Type')}.{options.get('memberName') or obj.get('name', 'member')}"
        backlink_url = self.member_backlink_url(owner, kind, obj)
        backlink_text = self.member_backlink_text(owner, kind, obj)
        body = [
            f"<h1>{esc(title)}</h1>",
            "",
            f'<p class="api-backlink"><a href="{attr(backlink_url)}">Back to {esc(backlink_text)}</a></p>',
            self.declaration_block(self.detail_signature(kind, obj, omit_receiver, full_receiver=options.get("extension", False), member_name=options.get("memberName"), escape=False)),
            self.metadata(obj),
        ]
        if kind == "function":
            body.append(self.parameters(obj.get("parameters") or [], omit_receiver, full_receiver=options.get("extension", False)))
        body.append(self.footer())
        self.write_page(self.member_detail_path(owner, obj), title, 10000, "\n".join(filter(None, body)), nav_hidden=True)

    def write_top_level_detail(self, fn: dict[str, Any], index: int = 10000) -> None:
        title = fn.get("name") or "Function"
        backlink_url = self.top_level_function_backlink_url(fn)
        backlink_text = self.top_level_function_backlink_text(fn)
        body = [
            f"<h1>{esc(title)}</h1>",
            "",
            f'<p class="api-backlink"><a href="{attr(backlink_url)}">Back to {esc(backlink_text)}</a></p>',
            self.declaration_block(self.detail_signature("function", fn, False, full_receiver=True, escape=False)),
            self.metadata(fn),
            self.parameters(fn.get("parameters") or []),
            self.footer(),
        ]
        self.write_page(self.top_level_detail_path(fn), title, index if self.grouped_sidebar else 10000, "\n".join(filter(None, body)), nav_title=signature_plain(fn, False), nav_hidden=True)

    def write_top_level_overload_group_detail(self, item: tuple[str, dict[str, Any], bool, dict[str, Any]]) -> None:
        _, group, _, _ = item
        title = group_display_name(group)
        body = [
            f"<h1>{esc(title)}</h1>",
            "",
            f'<p class="api-backlink"><a href="{attr(self.category_prefix(group))}">Back to {esc(category_name(group))}</a></p>',
            self.overloads(None, group),
            self.footer(),
        ]
        self.write_page(self.top_level_overload_group_path(group), title, 10000, "\n".join(filter(None, body)), nav_hidden=True)

    def write_constant_detail(self, variable: dict[str, Any], index: int = 10000) -> None:
        if not self.grouped_sidebar:
            return
        title = variable.get("name") or "Constant"
        backlink_url = self.constant_backlink_url(variable)
        backlink_text = self.constant_backlink_text(variable)
        body = [
            f"<h1>{esc(title)}</h1>",
            "",
            f'<p class="api-backlink"><a href="{attr(backlink_url)}">Back to {esc(backlink_text)}</a></p>',
            self.declaration_block(self.detail_signature("variable", variable, False, escape=False)),
            self.metadata(variable),
            self.footer(),
        ]
        self.write_page(self.constant_detail_path(variable), title, index, "\n".join(filter(None, body)), nav_hidden=True)

    def write_constant_overload_group_detail(self, item: tuple[str, dict[str, Any], bool, dict[str, Any]]) -> None:
        _, group, _, _ = item
        title = group.get("name") or "Constants"
        rows = [self.row(None, ("variable", variable, False, {})) for variable in group.get("overloads") or []]
        body = [
            f"<h1>{esc(title)}</h1>",
            "",
            f'<p class="api-backlink"><a href="{attr(self.category_prefix(group))}">Back to {esc(category_name(group))}</a></p>',
            '<div class="api-member-list api-declaration-list">' + "\n".join(rows) + "</div>",
            self.footer(),
        ]
        self.write_page(self.constant_overload_group_path(group), title, 10000, "\n".join(filter(None, body)), nav_hidden=True)

    def member_section(self, title: str, owner: dict[str, Any], items: list[tuple[str, dict[str, Any], bool, dict[str, Any]]], preserve_order: bool = False) -> str:
        if not items:
            return ""
        ordered_items = items if preserve_order else collapse_overload_items(sorted(items, key=member_sort_key))
        rows = [self.row(owner, item) for item in ordered_items]
        return f'<section class="api-member-section"><h2>{esc(title)}</h2><div class="api-member-list">' + "\n".join(rows) + "</div></section>"

    def declaration_rows(self, items: list[dict[str, Any]], kind: str) -> str:
        if not items:
            return '<p class="api-empty">No declarations.</p>'
        row_items = [("function", item, False, {"fullReceiver": True}) for item in sorted_declarations(items)] if kind == "function" else [(kind, item, False, {}) for item in sorted_declarations(items)]
        row_items = collapse_overload_items(row_items) if kind == "function" else collapse_constant_overload_items(row_items, self.type_names) if kind == "variable" else row_items
        rows = [self.row(None, item) for item in row_items]
        return '<div class="api-member-list api-declaration-list">' + "\n".join(rows) + "</div>"

    def type_rows(self, items: list[dict[str, Any]], one_column: bool = False) -> str:
        rows = []
        for obj in sorted_declarations(items):
            signature = type_list_signature(obj)
            if one_column and obj.get("kind") == "pseudoType":
                rows.append(
                    '<div class="api-member-row api-member-row--single">'
                    '<div class="api-member-main">'
                    f'<div class="api-member-sig"><a href="{attr(self.object_url(obj))}">{signature}</a></div>'
                    f'{self.metadata(obj, compact=True)}'
                    '</div>'
                    '</div>'
                )
                continue
            rows.append(
                '<div class="api-member-row">'
                f'<div class="api-member-type">{esc(declaration_kind_label(obj))}</div>'
                '<div class="api-member-main">'
                f'<div class="api-member-sig"><a href="{attr(self.object_url(obj))}">{signature}</a></div>'
                f'{self.metadata(obj, compact=True)}'
                '</div>'
                '</div>'
            )
        return '<div class="api-member-list api-declaration-list">' + "\n".join(rows) + "</div>"

    def is_external_extension_function(self, fn: dict[str, Any]) -> bool:
        receiver = receiver_type(fn)
        if not receiver:
            return False
        owner = self.extension_owner_name(receiver)
        return owner not in self.type_names

    def is_external_extension_variable(self, variable: dict[str, Any]) -> bool:
        owner = self.extension_variable_owner(variable)
        return owner is not None and owner not in self.type_names

    def extension_owner_name(self, value: str | None) -> str | None:
        return normalize_receiver_base(value)

    def extension_function_owner(self, fn: dict[str, Any]) -> dict[str, Any] | None:
        return self.logical_type_owner(receiver_type(fn))

    def extension_variable_owner_type(self, variable: dict[str, Any]) -> dict[str, Any] | None:
        return self.logical_type_owner(self.extension_variable_owner(variable))

    def logical_type_owner(self, value: str | None) -> dict[str, Any] | None:
        owner_name = logical_type_owner_name(value, self.type_names)
        return self.types_by_name.get(owner_name) if owner_name else None

    def extension_receiver_label(self, value: str | None) -> str | None:
        return normalize_receiver_label(value)

    def extension_variable_owner(self, variable: dict[str, Any]) -> str | None:
        name = variable.get("name") or ""
        if "." not in name:
            return None
        return name.split(".", 1)[0]

    def row(self, owner: dict[str, Any] | None, item: tuple[str, dict[str, Any], bool, dict[str, Any]]) -> str:
        kind, obj, omit_receiver, options = item
        first = ""
        signature = ""
        if kind == "overload-group":
            first = esc(obj.get("returnType") or "void")
            signature = f"<strong>{esc(obj.get('name') or '')}</strong>(...)"
        elif kind == "constant-overload-group":
            first = esc(obj.get("type") or "(multiple types)")
            signature = f"<strong>{esc(obj.get('name') or '')}</strong>"
        elif kind == "function":
            first = esc(lifecycle_kind(obj) or docs_return_type(obj))
            signature = member_signature(obj, omit_receiver, full_receiver=options.get("extension", False) or options.get("fullReceiver", False))
        elif kind in DECLARATION_KINDS:
            first = esc(declaration_kind_label(obj))
            signature = declaration_signature(obj)
        elif kind == "field":
            first = esc(field_type_display(obj))
            signature = f"<strong>{esc(obj.get('name', ''))}</strong>{constant_value_display(obj)}"
        elif kind == "variable":
            first = esc(inline_constant_type(obj))
            signature = f"<strong>{esc(options.get('memberName') or obj.get('name', ''))}</strong>{constant_value_display(obj)}"
        elif kind == "enum-value":
            signature = f"<strong>{esc(obj.get('name', ''))}</strong>{enum_value_display(obj)}"
        href = ""
        if owner and kind == "overload-group":
            href = self.overload_group_url(owner, obj)
        elif kind == "overload-group":
            href = self.top_level_overload_group_url(obj)
        elif kind == "constant-overload-group":
            href = self.constant_overload_group_url(obj)
        elif owner:
            href = self.member_detail_url(owner, obj)
        elif obj.get("kind") in DECLARATION_KINDS:
            href = self.object_url(obj)
        elif obj.get("kind") == "function" and not obj.get("overloadGroup"):
            href = self.top_level_detail_url(obj)
        elif obj.get("kind") == "variable" and self.grouped_sidebar:
            href = self.constant_detail_url(obj)
        if href:
            signature = f'<a href="{attr(href)}">{signature}</a>'
        if kind == "enum-value":
            return (
                '<div class="api-member-row api-member-row--single">'
                f'<div class="api-member-main"><div class="api-member-sig">{signature}{badges(obj, options)}</div>{self.metadata(obj, compact=True)}</div>'
                "</div>"
            )
        return (
            '<div class="api-member-row">'
            f'<div class="api-member-type">{first}</div>'
            f'<div class="api-member-main"><div class="api-member-sig">{signature}{badges(obj, options)}</div>{self.metadata(obj, compact=True)}</div>'
            "</div>"
        )

    def parameters(self, parameters: list[dict[str, Any]], omit_receiver: bool = False, show_title: bool = True, full_receiver: bool = False) -> str:
        rows: list[str] = []
        for param in visible_parameters(parameters):
            if omit_receiver and (param.get("name") == "this" or param.get("kind") == "receiver"):
                continue
            rows.append(
                '<div class="api-param-row">'
                f'<div class="api-param-type">{esc(param_type_plain(param, full_receiver=full_receiver))}</div>'
                '<div class="api-param-main">'
                f'<div class="api-param-name">{esc(param_name_plain(param, full_receiver=full_receiver))}{default_value_display(param)}</div>'
                f'{self.metadata(param, compact=True)}'
                '</div>'
                "</div>"
            )
        if not rows:
            return ""
        title = "<h2>Parameters</h2>" if show_title else ""
        return f'<section class="api-member-section api-param-section">{title}<div class="api-param-list">' + "\n".join(rows) + "</div></section>"

    def overloads(self, owner: dict[str, Any] | None, group: dict[str, Any]) -> str:
        rows: list[str] = []
        for overload in group.get("overloads") or []:
            obj = overload["member"]
            omit_receiver = overload["omitReceiver"]
            rows.append(
                '<section class="api-overload">'
                f'{self.declaration_block(self.detail_signature("function", obj, omit_receiver, full_receiver=overload.get("extension", False) or overload.get("fullReceiver", False), escape=False))}'
                f"{self.metadata(obj)}"
                f"{self.parameters(obj.get('parameters') or [], omit_receiver, show_title=False, full_receiver=overload.get('extension', False) or overload.get('fullReceiver', False))}"
                "</section>"
            )
        return '<div class="api-overload-list">' + "\n".join(rows) + "</div>" if rows else ""

    def write_overload_group_detail(self, owner: dict[str, Any], item: tuple[str, dict[str, Any], bool, dict[str, Any]]) -> None:
        _, group, _, _ = item
        title = f"{owner.get('name', 'Type')}.{group.get('name', 'overloads')}"
        body = [
            f"<h1>{esc(title)}</h1>",
            "",
            f'<p class="api-backlink"><a href="{attr(self.object_url(owner))}">Back to {esc(display_name(owner))}</a></p>',
            self.overloads(owner, group),
            self.footer(),
        ]
        self.write_page(self.overload_group_path(owner, group), title, 10000, "\n".join(filter(None, body)), nav_hidden=True)

    def metadata(self, obj: dict[str, Any], compact: bool = False, summary_only: bool = False) -> str:
        items = [item for item in obj.get("metadata") or [] if item.get("name") not in {"category", "overload"}]
        if summary_only:
            items = [item for item in items if item.get("name") == "summary"]
        if compact:
            items = [item for item in items if item.get("name") == "summary"]
        if not items:
            return ""
        order = ["summary", "remarks", "returns", "example", "see", "deprecated"]
        summary_blocks: list[str] = []
        section_blocks: list[str] = []
        for item in sorted(items, key=lambda item: (order.index(item.get("name")) if item.get("name") in order else 999, item.get("name") or "")):
            name = item.get("name") or ""
            raw_content = item.get("content")
            content = self.substitute(raw_content, item.get("symbols") or [])
            if not content and name in {"index", "range"}:
                continue
            if name == "summary":
                summary_blocks.append(f'<div class="api-doc-summary">{doc_text(content)}</div>')
            elif name == "example":
                section_blocks.append(f'<section class="api-doc-section"><h3>Example</h3><pre class="camp-code"><code data-lang="camp">{highlight_camp_code(example_text(str(raw_content or "")))}</code></pre></section>')
            elif name == "see":
                section_blocks.append(f'<section class="api-doc-section"><h3>See also</h3>{doc_text(content)}</section>')
            else:
                label = {"remarks": "Remarks", "returns": "Returns", "deprecated": "Deprecated"}.get(name, name[:1].upper() + name[1:])
                section_blocks.append(f'<section class="api-doc-section"><h3>{esc(label)}</h3>{doc_text(content)}</section>')
        if not summary_blocks and not section_blocks:
            return ""
        if compact:
            return "".join(summary_blocks)
        result: list[str] = []
        if summary_blocks:
            result.append('<div class="api-docblock">' + "".join(summary_blocks) + "</div>")
        result.extend(section_blocks)
        return "".join(result)

    def summary(self, obj: dict[str, Any]) -> str:
        return self.metadata(obj, compact=True, summary_only=True)

    def substitute(self, content: Any, symbols: list[dict[str, Any]]) -> str:
        if content is None:
            return ", ".join(self.symbol(symbol) for symbol in symbols)
        text = str(content)
        result: list[str] = []
        symbol_index = 0
        i = 0
        while i < len(text):
            if text.startswith("%%", i):
                result.append("%")
                i += 2
            elif text.startswith("%s", i):
                result.append(self.symbol(symbols[symbol_index]) if symbol_index < len(symbols) else "%s")
                symbol_index += 1
                i += 2
            elif text[i] == "`":
                end = text.find("`", i + 1)
                if end < 0:
                    result.append("`")
                    i += 1
                else:
                    result.append("<code>" + esc(text[i + 1 : end]) + "</code>")
                    i = end + 1
            else:
                result.append(esc(text[i]))
                i += 1
        return "".join(result)

    def symbol(self, symbol: dict[str, Any]) -> str:
        text = symbol.get("text") or symbol.get("ref") or ""
        ref = symbol.get("ref")
        if ref and ref in self.detail_urls:
            return f'<a href="{attr(self.detail_urls[ref])}">{esc(text)}</a>'
        if ref and ref in self.id_to_url:
            return f'<a href="{attr(self.id_to_url[ref])}">{esc(text)}</a>'
        if text in self.name_to_url:
            return f'<a href="{attr(self.name_to_url[text])}">{esc(text)}</a>'
        return f"<code>{esc(text)}</code>"

    def declaration_block(self, code: str) -> str:
        return f'<div class="api-declaration"><pre class="camp-code"><code data-lang="camp">{highlight_camp_code(code)}</code></pre></div>'

    def member_backlink_url(self, owner: dict[str, Any], kind: str, obj: dict[str, Any]) -> str:
        if kind == "function" and is_overload_function(obj):
            return self.overload_group_url(owner, {"name": obj.get("name") or "overloads"})
        return self.object_url(owner)

    def member_backlink_text(self, owner: dict[str, Any], kind: str, obj: dict[str, Any]) -> str:
        if kind == "function" and is_overload_function(obj):
            return f"{obj.get('name') or 'member'} overloads"
        return display_name(owner)

    def top_level_function_backlink_url(self, fn: dict[str, Any]) -> str:
        if self.top_level_function_group_counts.get(top_level_function_group_key(fn, full_receiver=self.grouped_sidebar), 0) > 1:
            return self.top_level_overload_group_url(fn)
        return self.category_prefix(fn)

    def top_level_function_backlink_text(self, fn: dict[str, Any]) -> str:
        if self.top_level_function_group_counts.get(top_level_function_group_key(fn, full_receiver=self.grouped_sidebar), 0) > 1:
            return f"{group_display_name(fn)} overloads"
        return category_name(fn)

    def constant_backlink_url(self, variable: dict[str, Any]) -> str:
        key = (category_name(variable), extension_variable_name(variable))
        if self.constant_group_counts.get(key, 0) > 1:
            return self.constant_overload_group_url({"name": extension_variable_name(variable), "metadata": variable.get("metadata") or []})
        return self.category_prefix(variable)

    def constant_backlink_text(self, variable: dict[str, Any]) -> str:
        key = (category_name(variable), extension_variable_name(variable))
        if self.constant_group_counts.get(key, 0) > 1:
            return f"{extension_variable_name(variable)} overloads"
        return category_name(variable)

    def detail_signature(self, kind: str, obj: dict[str, Any], omit_receiver: bool, full_receiver: bool = False, member_name: str | None = None, escape: bool = True) -> str:
        if kind == "function":
            text = docs_return_type(obj) + " " + signature_plain(obj, omit_receiver, full_receiver=full_receiver)
            return esc(text) if escape else text
        if kind == "field":
            text = (field_type_display(obj) + " " + obj.get("name", "")).strip()
            if "value" in obj:
                text += " = " + str(obj["value"])
            return esc(text) if escape else text
        if kind == "variable":
            text = (inline_constant_type(obj) + " " + (member_name or obj.get("name", ""))).strip()
            if "value" in obj:
                text += " = " + str(obj["value"])
            return esc(text) if escape else text
        if kind == "enum-value":
            text = obj.get("name", "") + (" = " + str(obj["value"]) if "value" in obj else "")
            return esc(text) if escape else text
        return esc(obj.get("name", "")) if escape else obj.get("name", "")

    def index_signature(self, obj: dict[str, Any]) -> str:
        if obj.get("kind") == "function":
            return f"{esc(docs_return_type(obj))} <strong>{esc(obj.get('name') or '')}</strong>{declaration_type_parameters_display(obj)}({params_display(obj, False, full_receiver=True)})"
        return declaration_signature(obj)

    def object_url(self, obj: dict[str, Any]) -> str:
        if obj.get("kind") == "function":
            return self.top_level_detail_url(obj)
        if obj.get("kind") == "variable":
            return self.constant_detail_url(obj) if self.grouped_sidebar else self.prefix() + "constants/"
        if obj.get("kind") in DECLARATION_KINDS:
            path = self.declaration_group_path(obj)
            return self.prefix() + (path + "/" if path else "") + slug(display_name(obj)) + "/"
        return self.prefix()

    def member_detail_url(self, owner: dict[str, Any], member: dict[str, Any]) -> str:
        group = self.declaration_group_path(owner)
        return self.prefix() + (group + "/" if group else "") + detail_slug(owner, member) + "/"

    def overload_group_url(self, owner: dict[str, Any], group: dict[str, Any]) -> str:
        prefix = self.prefix() + (self.declaration_group_path(owner) + "/" if self.declaration_group_path(owner) else "")
        return prefix + overload_group_slug(owner, group) + "/"

    def top_level_detail_url(self, fn: dict[str, Any]) -> str:
        prefix = self.category_prefix(fn) if self.grouped_sidebar else self.prefix()
        return prefix + "function-" + slug(signature_plain(fn, False, full_receiver=self.grouped_sidebar)) + "/"

    def top_level_overload_group_url(self, group: dict[str, Any]) -> str:
        prefix = self.category_prefix(group) if self.grouped_sidebar else self.prefix()
        return prefix + "function-" + slug(group_display_name(group)) + "-overloads/"

    def constant_detail_url(self, variable: dict[str, Any]) -> str:
        return self.category_prefix(variable) + slug(variable.get("name") or "constant") + "/" if self.grouped_sidebar else self.prefix() + "constants/" + slug(variable.get("name") or "constant") + "/"

    def constant_overload_group_url(self, group: dict[str, Any]) -> str:
        return self.category_prefix(group) + "constant-" + slug(group.get("name") or "overloads") + "-overloads/"

    def member_detail_path(self, owner: dict[str, Any], member: dict[str, Any]) -> Path:
        return self.output_dir / f"{self.declaration_group_path(owner)}" / f"{detail_slug(owner, member)}.md" if self.grouped_sidebar else self.output_dir / f"{detail_slug(owner, member)}.md"

    def overload_group_path(self, owner: dict[str, Any], group: dict[str, Any]) -> Path:
        return self.output_dir / f"{self.declaration_group_path(owner)}" / f"{overload_group_slug(owner, group)}.md" if self.grouped_sidebar else self.output_dir / f"{overload_group_slug(owner, group)}.md"

    def top_level_detail_path(self, fn: dict[str, Any]) -> Path:
        return (self.output_dir / category_slug(category_name(fn)) if self.grouped_sidebar else self.output_dir) / f"function-{slug(signature_plain(fn, False, full_receiver=self.grouped_sidebar))}.md"

    def top_level_overload_group_path(self, group: dict[str, Any]) -> Path:
        return (self.output_dir / category_slug(category_name(group)) if self.grouped_sidebar else self.output_dir) / f"function-{slug(group_display_name(group))}-overloads.md"

    def constant_detail_path(self, variable: dict[str, Any]) -> Path:
        return self.output_dir / category_slug(category_name(variable)) / f"{slug(variable.get('name') or 'constant')}.md" if self.grouped_sidebar else self.output_dir / "constants" / f"{slug(variable.get('name') or 'constant')}.md"

    def constant_overload_group_path(self, group: dict[str, Any]) -> Path:
        return self.output_dir / category_slug(category_name(group)) / f"constant-{slug(group.get('name') or 'overloads')}-overloads.md"

    def declaration_path(self, obj: dict[str, Any]) -> Path:
        group = self.declaration_group_path(obj)
        return (self.output_dir / group if group else self.output_dir) / f"{slug(display_name(obj))}.md"

    def declaration_group_path(self, obj: dict[str, Any]) -> str:
        if not self.grouped_sidebar:
            return ""
        return category_slug(category_name(obj))

    def category_prefix(self, obj: dict[str, Any]) -> str:
        return self.prefix() + category_slug(category_name(obj)) + "/"

    def kind_url(self, obj: dict[str, Any], kind: str) -> str:
        if not self.grouped_sidebar:
            info = API_GROUP_BY_KIND.get(kind)
            return self.prefix() + (info[0] + "/" if info else "")
        info = API_GROUP_BY_KIND.get(kind)
        return self.category_prefix(obj) + (info[0] + "/" if info else "")

    def declaration_weight(self, obj: dict[str, Any]) -> int:
        return self.page_weights.get(declaration_key(obj), 10000)

    def prefix(self) -> str:
        return f"/docs/{self.url_slug}/"

    def footer(self) -> str:
        return f'<p class="api-generated">Generated with campc {esc(self.campc_version)}.</p>'

    def write_section(self, path: Path, title: str, weight: int | None = None, content: str = "", nav_hidden: bool = False) -> None:
        self.written_paths.add(path / "_index.md")
        write_section(path, title, weight=weight, content=content, nav_hidden=nav_hidden)

    def write_page(self, path: Path, title: str, weight: int, content: str, nav_title: str | None = None, nav_hidden: bool = False) -> None:
        self.written_paths.add(path)
        write_page(path, title, weight, content, nav_title=nav_title, nav_hidden=nav_hidden)

    def remove_stale_pages(self) -> None:
        if not self.output_dir.exists():
            return
        for path in sorted(self.output_dir.rglob("*.md"), reverse=True):
            if path not in self.written_paths:
                path.unlink()
        for path in sorted((p for p in self.output_dir.rglob("*") if p.is_dir()), reverse=True):
            try:
                path.rmdir()
            except OSError:
                pass


def read_metadata(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != "camp.metadata":
        raise ValueError(f"{path} is not Camp metadata JSON")
    if data.get("version") != 1:
        raise ValueError(f"{path} has unsupported metadata version {data.get('version')}")
    return data


def read_text(path: Path, fallback: str) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else fallback


def pseudo_type_declarations(metadata_declarations: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    declarations: list[dict[str, Any]] = []
    for name, summary in PRIMITIVE_TYPES:
        declarations.append(pseudo_type_declaration(name, "Primitives", summary))
    char_extension_owners = char_primitive_extension_owners(metadata_declarations if metadata_declarations is not None else [])
    for name, summary in CHAR_PRIMITIVE_TYPES:
        if name in char_extension_owners:
            declarations.append(pseudo_type_declaration(name, "Primitives", summary))
    for name, summary in STRING_TYPES:
        declarations.append(pseudo_type_declaration(name, "Strings", summary))
    return declarations


def pseudo_type_declaration(name: str, category: str, summary: str) -> dict[str, Any]:
    return {
        "id": f"pseudoType:{name}",
        "kind": "pseudoType",
        "name": name,
        "category": category,
        "metadata": [{"name": "summary", "content": summary}],
    }


def char_primitive_extension_owners(declarations: list[dict[str, Any]]) -> set[str]:
    owners: set[str] = set()
    char_names = {name for name, _ in CHAR_PRIMITIVE_TYPES}
    for declaration in declarations:
        if declaration.get("kind") == "function":
            parsed = parse_receiver_type(receiver_type(declaration))
            if parsed is None:
                continue
            base, is_array, is_const = parsed
            if is_array and is_const and base in CHAR_ARRAY_STRING_OWNERS:
                continue
            if base in char_names:
                owners.add(base)
        elif declaration.get("kind") == "variable":
            owner = extension_variable_owner_name(declaration)
            if owner in char_names:
                owners.add(owner)
    return owners


def write_text_if_changed(path: Path, text: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_section(path: Path, title: str, weight: int | None = None, content: str = "", nav_hidden: bool = False) -> None:
    path.mkdir(parents=True, exist_ok=True)
    lines = ["+++", f'title = "{toml(title)}"', 'sort_by = "weight"']
    if weight is not None:
        lines.append(f"weight = {weight}")
    lines.extend(['template = "docs_section.html"', 'page_template = "docs_page.html"'])
    if nav_hidden:
        lines.extend(["", "[extra]", "nav_hidden = true"])
    lines.extend(["+++", "", content])
    write_text_if_changed(path / "_index.md", "\n".join(lines))


def write_page(path: Path, title: str, weight: int, content: str, nav_title: str | None = None, nav_hidden: bool = False) -> None:
    lines = ["+++", f'title = "{toml(title)}"', f"weight = {weight}", 'template = "docs_page.html"']
    extra: list[str] = []
    if nav_title:
        extra.append(f'nav_title = "{toml(nav_title)}"')
    if nav_hidden:
        extra.append("nav_hidden = true")
    if extra:
        lines.extend(["", "[extra]", *extra])
    lines.extend(["+++", "", content])
    write_text_if_changed(path, "\n".join(lines) + "\n")


def write_placeholder(path: Path, title: str, weight: int, message: str) -> None:
    write_section(path, title, weight)
    write_page(path / "overview.md", title, 1, f"# {esc(title)}\n\n{esc(message)}\n", nav_title="Overview")


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=False)


def attr(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def toml(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


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


def slug(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", str(value or "")).strip("-").lower() or "item"


def display_name(obj: dict[str, Any]) -> str:
    parameters = obj.get("typeParameters") or []
    return (obj.get("name") or "") + ("<" + ", ".join(p.get("name") or "?" for p in parameters) + ">" if parameters else "")


def declaration_display_name(obj: dict[str, Any]) -> str:
    parameters = obj.get("typeParameters") or []
    return (obj.get("name") or "") + type_parameters_plain(parameters, include_constraints=True)


def sorted_declarations(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda obj: (display_name(obj).lower(), signature_plain(obj, False).lower(), obj.get("symbol") or ""))


def declaration_key(obj: dict[str, Any]) -> str:
    return obj.get("id") or f"{obj.get('kind')}:{display_name(obj)}:{signature_plain(obj, False)}"


def declaration_kind_label(obj: dict[str, Any]) -> str:
    if obj.get("kind") == "pseudoType":
        return "type"
    return "static class" if obj.get("kind") == "staticClass" else str(obj.get("kind") or "")


def category_name(obj: dict[str, Any]) -> str:
    if obj.get("category"):
        return str(obj["category"])
    for item in obj.get("metadata") or []:
        if item.get("name") == "category" and item.get("content"):
            return str(item["content"])
    return "Other"


def category_slug(name: str) -> str:
    return slug(name)


def children_of(obj: dict[str, Any]) -> list[dict[str, Any]]:
    return [*(obj.get("fields") or []), *(obj.get("functions") or []), *(obj.get("values") or [])]


def public_children_of(obj: dict[str, Any]) -> list[dict[str, Any]]:
    return [child for child in children_of(obj) if is_public_member(child, obj)]


def is_public_declaration(obj: dict[str, Any]) -> bool:
    if obj.get("kind") == "staticClass" and obj.get("visibility") is None:
        return True
    return obj.get("visibility") == "public"


def is_public_member(obj: dict[str, Any], owner: dict[str, Any] | None) -> bool:
    if owner and owner.get("kind") in {"interface", "struct", "enum"}:
        return True
    if owner and owner.get("kind") == "newtype" and (obj.get("static") or obj.get("modifier") == "static"):
        return obj.get("visibility") in {None, "public"}
    return obj.get("visibility") == "public"


def signature_plain(obj: dict[str, Any], omit_receiver: bool = False, full_receiver: bool = False) -> str:
    if obj.get("kind") == "newtype":
        if obj.get("callableType"):
            return f"newtype {obj.get('callableType')} {docs_return_type(obj)} {declaration_display_name(obj)}({params_plain(obj, omit_receiver, full_receiver=full_receiver)})"
        if obj.get("underlyingType"):
            return f"newtype {declaration_display_name(obj)}: {obj.get('underlyingType')}"
        return f"newtype {declaration_display_name(obj)}"
    return f"{declaration_display_name(obj)}({params_plain(obj, omit_receiver, full_receiver=full_receiver)})"


def params_plain(obj: dict[str, Any], omit_receiver: bool, full_receiver: bool = False) -> str:
    return ", ".join(filter(None, (param_plain(p, omit_receiver, full_receiver=full_receiver) for p in visible_parameters(obj.get("parameters") or []))))


def visible_parameters(parameters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [param for param in parameters if not is_prep_parameter(param)]


def is_prep_parameter(param: dict[str, Any]) -> bool:
    return param.get("modifier") == "prep"


def prep_parameter(obj: dict[str, Any]) -> dict[str, Any] | None:
    return next((param for param in obj.get("parameters") or [] if is_prep_parameter(param)), None)


def docs_return_type(obj: dict[str, Any]) -> str:
    if prep := prep_parameter(obj):
        return "prep " + str(prep.get("type") or "")
    return str(obj.get("returnType") or "void")


def is_receiver_parameter(param: dict[str, Any]) -> bool:
    return param.get("name") == "this" or param.get("kind") == "receiver"


def receiver_qualifiers(param: dict[str, Any]) -> list[str]:
    typ = str(param.get("type") or "")
    parts: list[str] = []
    for qualifier in ["const", "volatile", "escaped", "scoped", "unscoped", "in"]:
        if re.search(rf"\b{qualifier}\b", typ):
            parts.append(qualifier)
    if param.get("modifier") and param["modifier"] not in parts:
        parts.insert(0, param["modifier"])
    return parts


def param_plain(param: dict[str, Any], omit_receiver: bool, full_receiver: bool = False) -> str:
    if omit_receiver and is_receiver_parameter(param):
        return ""
    if is_receiver_parameter(param) and not full_receiver:
        parts = receiver_qualifiers(param)
        parts.append("this")
        return " ".join(parts)
    name = param.get("name") or ""
    typ = param.get("type") or ""
    if re.match(r"^sizeof_\w+$", name) and typ == "nuint":
        return f"sizeof({name.removeprefix('sizeof_')})"
    parts: list[str] = []
    if param.get("overload"):
        parts.append("overload")
    if param.get("modifier"):
        parts.append(param["modifier"])
    if typ:
        parts.append(typ)
    if name:
        parts.append(name)
    text = " ".join(parts)
    if "defaultValue" in param:
        text += " = " + str(param["defaultValue"])
    return text


def param_type_plain(param: dict[str, Any], full_receiver: bool = False) -> str:
    name = param.get("name") or ""
    typ = param.get("type") or ""
    if re.match(r"^sizeof_\w+$", name) and typ == "nuint":
        return "nuint"
    if is_receiver_parameter(param) and not full_receiver:
        return " ".join(receiver_qualifiers(param))
    parts: list[str] = []
    if param.get("overload"):
        parts.append("overload")
    if param.get("modifier"):
        parts.append(param["modifier"])
    if typ:
        parts.append(typ)
    return " ".join(parts)


def param_name_plain(param: dict[str, Any], full_receiver: bool = False) -> str:
    name = param.get("name") or ""
    typ = param.get("type") or ""
    if re.match(r"^sizeof_\w+$", name) and typ == "nuint":
        return f"sizeof({name.removeprefix('sizeof_')})"
    return name


def default_value_display(param: dict[str, Any]) -> str:
    if "defaultValue" not in param:
        return ""
    return f'<span class="api-default-value"> = {esc(param["defaultValue"])}</span>'


def params_display(obj: dict[str, Any], omit_receiver: bool, full_receiver: bool = False) -> str:
    return ", ".join(esc(text) for text in (param_plain(p, omit_receiver, full_receiver=full_receiver) for p in visible_parameters(obj.get("parameters") or [])) if text)


def type_parameters_display(obj: dict[str, Any]) -> str:
    return esc(type_parameters_plain(obj.get("typeParameters") or [], include_constraints=False))


def declaration_type_parameters_display(obj: dict[str, Any]) -> str:
    return esc(type_parameters_plain(obj.get("typeParameters") or [], include_constraints=True))


def type_parameters_plain(parameters: list[dict[str, Any]], include_constraints: bool) -> str:
    if not parameters:
        return ""
    values: list[str] = []
    for parameter in parameters:
        value = parameter.get("name") or "?"
        if include_constraints and parameter.get("constraint"):
            value += ": " + str(parameter["constraint"])
        values.append(value)
    return "<" + ", ".join(values) + ">"


def member_signature(obj: dict[str, Any], omit_receiver: bool, full_receiver: bool = False) -> str:
    return f"<strong>{esc(obj.get('name') or '')}</strong>{type_parameters_display(obj)}({params_display(obj, omit_receiver, full_receiver=full_receiver)})"


def declaration_signature(obj: dict[str, Any], escape: bool = True) -> str:
    kind = obj.get("kind")
    if not escape:
        if kind in {"class", "staticClass", "interface", "struct", "enum"}:
            parts: list[str] = []
            if obj.get("modifier"):
                parts.append(obj["modifier"])
            parts.extend([declaration_kind_label(obj), (obj.get("name") or "") + type_parameters_plain(obj.get("typeParameters") or [], include_constraints=True)])
            if obj.get("baseTypes"):
                parts.append(": " + ", ".join(obj["baseTypes"]))
            return " ".join(parts)
        if kind == "newtype":
            if obj.get("callableType"):
                return f"newtype {obj.get('callableType')} {docs_return_type(obj)} {obj.get('name') or ''}{type_parameters_plain(obj.get('typeParameters') or [], include_constraints=True)}({params_plain(obj, False)})"
            if obj.get("underlyingType"):
                return f"newtype {obj.get('name') or ''}{type_parameters_plain(obj.get('typeParameters') or [], include_constraints=True)}: {obj.get('underlyingType')}"
        if kind == "function":
            return f"{docs_return_type(obj)} {obj.get('name') or ''}{type_parameters_plain(obj.get('typeParameters') or [], include_constraints=True)}({params_plain(obj, False)})"
        if kind == "variable":
            text = f"{inline_constant_type(obj)} {obj.get('name') or ''}"
            if "value" in obj:
                text += " = " + str(obj["value"])
            return text
        return display_name(obj)

    if kind in {"class", "staticClass", "interface", "struct", "enum"}:
        parts: list[str] = []
        if obj.get("modifier"):
            parts.append(esc(obj["modifier"]))
        parts.extend([esc(declaration_kind_label(obj)), "<strong>" + esc(obj.get("name") or "") + declaration_type_parameters_display(obj) + "</strong>"])
        if obj.get("baseTypes"):
            parts.append(": " + ", ".join(esc(item) for item in obj["baseTypes"]))
        return " ".join(parts)
    if kind == "newtype":
        if obj.get("callableType"):
            return f"newtype {esc(obj.get('callableType'))} {esc(docs_return_type(obj))} <strong>{esc(obj.get('name') or '')}{declaration_type_parameters_display(obj)}</strong>({params_display(obj, False)})"
        if obj.get("underlyingType"):
            return f"newtype <strong>{esc(obj.get('name') or '')}{declaration_type_parameters_display(obj)}</strong>: {esc(obj.get('underlyingType'))}"
    if kind == "function":
        return f"{esc(docs_return_type(obj))} <strong>{esc(obj.get('name') or '')}</strong>{declaration_type_parameters_display(obj)}({params_display(obj, False)})"
    if kind == "variable":
        return f"{esc(inline_constant_type(obj))} <strong>{esc(obj.get('name') or '')}</strong>{constant_value_display(obj)}"
    return "<strong>" + esc(display_name(obj)) + "</strong>"


def type_list_signature(obj: dict[str, Any]) -> str:
    kind = obj.get("kind")
    if kind in {"class", "staticClass", "interface", "struct", "enum"}:
        parts = ["<strong>" + esc(obj.get("name") or "") + declaration_type_parameters_display(obj) + "</strong>"]
        if obj.get("baseTypes"):
            parts.append(": " + ", ".join(esc(item) for item in obj["baseTypes"]))
        return " ".join(parts)
    if kind == "newtype":
        if obj.get("callableType"):
            return f"{esc(obj.get('callableType'))} {esc(docs_return_type(obj))} <strong>{esc(obj.get('name') or '')}{declaration_type_parameters_display(obj)}</strong>({params_display(obj, False)})"
        if obj.get("underlyingType"):
            return f"<strong>{esc(obj.get('name') or '')}{declaration_type_parameters_display(obj)}</strong>: {esc(obj.get('underlyingType'))}"
    return "<strong>" + esc(display_name(obj)) + "</strong>"


def extension_function_label(obj: dict[str, Any]) -> str:
    return esc((obj.get("name") or "") + type_parameters_plain(obj.get("typeParameters") or [], include_constraints=False) + "()")


def extension_variable_name(obj: dict[str, Any]) -> str:
    name = obj.get("name") or ""
    return name.split(".", 1)[1] if "." in name else name


def extension_variable_owner_name(obj: dict[str, Any]) -> str | None:
    name = obj.get("name") or ""
    if "." not in name:
        return None
    return name.split(".", 1)[0]


def inline_constant_type(obj: dict[str, Any]) -> str:
    type_name = str(obj.get("type") or "const")
    if obj.get("inline") and not type_name.startswith("inline "):
        return "inline " + type_name
    return type_name


def field_type_display(obj: dict[str, Any]) -> str:
    type_name = str(obj.get("type") or "")
    if obj.get("inline") and not type_name.startswith("inline "):
        return "inline " + type_name
    return type_name


def constant_value_display(obj: dict[str, Any]) -> str:
    if "value" not in obj:
        return ""
    return f'<span class="api-constant-value"> = {esc(obj["value"])}</span>'


def enum_value_display(obj: dict[str, Any]) -> str:
    if "value" not in obj:
        return ""
    return f'<span class="api-constant-value"> = {esc(obj["value"])}</span>'


def doc_text(content: str) -> str:
    return "".join("<p>" + part.replace("\n", "<br>") + "</p>" for part in re.split(r"\n\s*\n", content.strip()) if part.strip()) if content else ""


def example_text(content: str) -> str:
    match = re.match(r"^```[A-Za-z0-9_-]*\n(.*?)\n```$", content.strip(), re.DOTALL)
    return match.group(1) if match else content


def badges(obj: dict[str, Any], options: dict[str, Any]) -> str:
    values: list[str] = []
    if obj.get("propertyName") or obj.get("property"):
        values.append("property")
    if obj.get("ascription"):
        values.append("ascribes " + str(obj["ascription"]))
    if obj.get("overloadGroup") or any(p.get("overload") for p in obj.get("parameters") or []):
        values.append("overload")
    if obj.get("async"):
        values.append("async")
    if obj.get("modifier") and obj.get("modifier") not in {"constructor", "destructor", "static"}:
        values.append(str(obj["modifier"]))
    if not values:
        return ""
    return '<div class="api-badges">' + "".join(f'<span class="api-badge">{esc(v)}</span>' for v in values) + "</div>"


def receiver_param(fn: dict[str, Any]) -> dict[str, Any] | None:
    parameters = fn.get("parameters") or []
    if parameters and (parameters[0].get("name") == "this" or parameters[0].get("kind") == "receiver"):
        return parameters[0]
    return next((p for p in parameters if p.get("name") == "this" or p.get("kind") == "receiver"), None)


def receiver_type(fn: dict[str, Any]) -> str | None:
    param = receiver_param(fn)
    return param.get("type") if param else None


def function_receiver_group_label(fn: dict[str, Any]) -> str:
    return normalize_receiver_label(receiver_type(fn)) or ""


def top_level_function_group_key(fn: dict[str, Any], full_receiver: bool) -> tuple[str, str, str]:
    return (
        category_name(fn),
        fn.get("name") or "",
        function_receiver_group_label(fn) if full_receiver else "",
    )


def group_display_name(group: dict[str, Any]) -> str:
    name = group.get("name") or "function"
    receiver = group.get("receiver") or function_receiver_group_label(group)
    return f"{receiver}.{name}" if receiver else name


def logical_type_owner_name(value: str | None, type_names: set[str]) -> str | None:
    parsed = parse_receiver_type(value)
    if parsed is None:
        return None
    base, is_array, is_const = parsed
    if base in STRING_TYPE_NAMES:
        return base
    if is_array and is_const and base in CHAR_ARRAY_STRING_OWNERS:
        return CHAR_ARRAY_STRING_OWNERS[base]
    if base in PRIMITIVE_TYPE_NAMES:
        return base
    if base in type_names:
        return base
    if is_generic_receiver_base(base):
        return None
    return None


def parse_receiver_type(value: str | None) -> tuple[str, bool, bool] | None:
    if not value:
        return None
    text = value.strip()
    is_const = False
    changed = True
    while changed:
        changed = False
        for qualifier in ["const ", "volatile ", "escaped ", "scoped ", "unscoped ", "in "]:
            if text.startswith(qualifier):
                if qualifier == "const ":
                    is_const = True
                text = text[len(qualifier) :].strip()
                changed = True
        new_text = re.sub(r"^(scoped|unscoped)\([^)]*\)\s+", "", text).strip()
        if new_text != text:
            text = new_text
            changed = True

    while True:
        new_text = re.sub(r"\s*\*\s*$", "", text).strip()
        if new_text == text:
            break
        text = new_text

    is_array = False
    while True:
        new_text = re.sub(r"\s*(\[\]|\[[^\]]+\])\s*$", "", text).strip()
        if new_text == text:
            break
        is_array = True
        text = new_text

    base = text.split("<", 1)[0].strip() if "<" in text else text.strip()
    return (base, is_array, is_const) if base else None


def is_generic_receiver_base(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Z][A-Za-z0-9_]*", value))


def normalize_receiver_base(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    changed = True
    while changed:
        changed = False
        for qualifier in ["const ", "volatile ", "escaped ", "scoped ", "unscoped ", "in "]:
            if text.startswith(qualifier):
                text = text[len(qualifier) :].strip()
                changed = True
        new_text = re.sub(r"^(scoped|unscoped)\([^)]*\)\s+", "", text).strip()
        if new_text != text:
            text = new_text
            changed = True
    while True:
        new_text = re.sub(r"\s*(\*|\[\]|\[[^\]]+\])\s*$", "", text).strip()
        if new_text == text:
            break
        text = new_text
    return text.split("<", 1)[0].strip() if "<" in text else text or None


def normalize_receiver_label(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    changed = True
    while changed:
        changed = False
        for qualifier in ["const ", "volatile ", "escaped ", "scoped ", "unscoped ", "in "]:
            if text.startswith(qualifier):
                text = text[len(qualifier) :].strip()
                changed = True
        new_text = re.sub(r"^(scoped|unscoped)\([^)]*\)\s+", "", text).strip()
        if new_text != text:
            text = new_text
            changed = True
    while True:
        new_text = re.sub(r"\s*\*\s*$", "", text).strip()
        if new_text == text:
            break
        text = new_text
    return text.split("<", 1)[0].strip() if "<" in text else text or None


def split_members(obj: dict[str, Any], extensions: list[dict[str, Any]], extension_variables: list[dict[str, Any]]) -> tuple[list[tuple[str, dict[str, Any], bool, dict[str, Any]]], list[tuple[str, dict[str, Any], bool, dict[str, Any]]], list[tuple[str, dict[str, Any], bool, dict[str, Any]]], list[tuple[str, dict[str, Any], bool, dict[str, Any]]]]:
    lifecycle: list[tuple[str, dict[str, Any], bool, dict[str, Any]]] = []
    fields: list[tuple[str, dict[str, Any], bool, dict[str, Any]]] = []
    instance: list[tuple[str, dict[str, Any], bool, dict[str, Any]]] = []
    static: list[tuple[str, dict[str, Any], bool, dict[str, Any]]] = []
    for field in obj.get("fields") or []:
        if not is_public_member(field, obj):
            continue
        target = static if field.get("static") or field.get("modifier") == "static" or "value" in field else fields if obj.get("kind") == "struct" else instance
        target.append(("field", field, False, {"omitVisibility": obj.get("kind") == "struct"}))
    for fn in obj.get("functions") or []:
        if not is_public_member(fn, obj):
            continue
        if lifecycle_kind(fn):
            lifecycle.append(("function", fn, False, {}))
        else:
            (static if fn.get("modifier") == "static" else instance).append(("function", fn, False, {"omitVisibility": obj.get("kind") == "interface"}))
    for fn in extensions:
        instance.append(("function", fn, False, {"extension": True}))
    for variable in extension_variables:
        static.append(("variable", variable, False, {"extension": True, "memberName": extension_variable_name(variable)}))
    return lifecycle, fields, instance, static


def lifecycle_kind(obj: dict[str, Any]) -> str | None:
    modifier = obj.get("modifier")
    if modifier == "constructor":
        return "constructor"
    if modifier == "destructor":
        return "destructor"
    return None


def member_sort_key(item: tuple[str, dict[str, Any], bool, dict[str, Any]]) -> tuple[int, str, str]:
    _, obj, omit_receiver, options = item
    rank = 0 if obj.get("modifier") == "constructor" else 1 if obj.get("modifier") == "destructor" else 2
    signature = signature_plain(obj, omit_receiver, full_receiver=options.get("extension", False)) if obj.get("kind") == "function" else obj.get("name", "")
    return rank, obj.get("name", "").lower(), signature.lower()


def collapse_overload_items(items: list[tuple[str, dict[str, Any], bool, dict[str, Any]]]) -> list[tuple[str, dict[str, Any], bool, dict[str, Any]]]:
    result: list[tuple[str, dict[str, Any], bool, dict[str, Any]]] = []
    groups: dict[tuple[str, str, bool, bool, str], list[tuple[str, dict[str, Any], bool, dict[str, Any]]]] = {}
    group_order: list[tuple[str, str, bool, bool, str]] = []

    for item in items:
        kind, obj, omit_receiver, options = item
        if kind != "function" or not (is_overload_function(obj) or options.get("fullReceiver", False)):
            result.append(item)
            continue

        key = (
            obj.get("name") or "",
            obj.get("modifier") or "",
            omit_receiver,
            options.get("extension", False),
            function_receiver_group_label(obj) if options.get("extension", False) or options.get("fullReceiver", False) else "",
        )
        if key not in groups:
            group_order.append(key)
        groups.setdefault(key, []).append(item)

    for key in group_order:
        group = groups[key]
        if len(group) == 1:
            result.append(group[0])
            continue

        first = group[0][1]
        return_types = {docs_return_type(item[1]) for item in group}
        result.append((
            "overload-group",
            {
                "kind": "function",
                "name": first.get("name") or "",
                "returnType": next(iter(return_types)) if len(return_types) == 1 else "(multiple types)",
                "modifier": first.get("modifier"),
                "static": first.get("static"),
                "category": category_name(first),
                "receiver": key[4],
                "overloadGroup": True,
                "overloads": [
                    {
                        "member": item[1],
                        "omitReceiver": item[2],
                        "extension": item[3].get("extension", False),
                        "fullReceiver": item[3].get("fullReceiver", False),
                    }
                    for item in sorted(group, key=member_sort_key)
                ],
                "metadata": overload_group_metadata([item[1] for item in group]),
            },
            group[0][2],
            {"extension": group[0][3].get("extension", False)},
        ))

    return sorted(result, key=member_sort_key)


def collapse_constant_overload_items(items: list[tuple[str, dict[str, Any], bool, dict[str, Any]]], type_names: set[str]) -> list[tuple[str, dict[str, Any], bool, dict[str, Any]]]:
    result: list[tuple[str, dict[str, Any], bool, dict[str, Any]]] = []
    groups: dict[tuple[str, str], list[tuple[str, dict[str, Any], bool, dict[str, Any]]]] = {}
    group_order: list[tuple[str, str]] = []

    for item in items:
        kind, obj, _, _ = item
        owner = extension_variable_owner_name(obj)
        if kind != "variable" or owner is None or owner in type_names:
            result.append(item)
            continue

        key = (category_name(obj), extension_variable_name(obj))
        if key not in groups:
            group_order.append(key)
        groups.setdefault(key, []).append(item)

    for key in group_order:
        group = groups[key]
        if len(group) == 1:
            result.append(group[0])
            continue
        first = group[0][1]
        types = {item[1].get("type") or "const" for item in group}
        result.append((
            "constant-overload-group",
            {
                "kind": "variable",
                "name": extension_variable_name(first),
                "type": next(iter(types)) if len(types) == 1 else "(multiple types)",
                "overloadGroup": True,
                "overloads": [item[1] for item in sorted(group, key=member_sort_key)],
                "metadata": overload_group_metadata([item[1] for item in group]),
            },
            False,
            {},
        ))

    return sorted(result, key=member_sort_key)


def is_overload_function(obj: dict[str, Any]) -> bool:
    return any(parameter.get("overload") for parameter in obj.get("parameters") or [])


def overload_group_metadata(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for obj in items:
        for item in obj.get("metadata") or []:
            if item.get("name") == "overload" and item.get("content"):
                return [{"name": "summary", "content": item["content"]}]
    first = items[0] if items else {}
    return [item for item in first.get("metadata") or [] if item.get("name") != "overload"]


def detail_slug(owner: dict[str, Any], member: dict[str, Any]) -> str:
    if member.get("modifier") in {"constructor", "destructor"}:
        text = f"{member.get('modifier')}-{signature_plain(member, False)}"
    else:
        text = signature_plain(member, False) if member.get("kind") == "function" else member.get("name", "")
    return slug((owner.get("name") or "type") + "-" + text)


def overload_group_slug(owner: dict[str, Any], group: dict[str, Any]) -> str:
    return slug((owner.get("name") or "type") + "-" + (group.get("name") or "overloads") + "-overloads")
