from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any


TYPE_KINDS = {"class", "interface", "struct", "newtype"}
DECLARATION_KINDS = TYPE_KINDS | {"enum"}
API_GROUPS = [
    ("class", "classes", "Classes"),
    ("struct", "structs", "Structs"),
    ("interface", "interfaces", "Interfaces"),
    ("enum", "enums", "Enums"),
    ("newtype", "newtypes", "Newtypes"),
    ("function", "functions", "Functions"),
    ("variable", "constants", "Constants"),
]
API_GROUP_BY_KIND = {kind: (path, title) for kind, path, title in API_GROUPS}


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

    def write(self, metadata: dict[str, Any] | None = None) -> None:
        metadata = metadata or read_metadata(self.metadata_path)
        declarations = [d for d in metadata.get("declarations") or [] if is_public_declaration(d)]
        module = metadata.get("module") or {}
        module_name = module.get("namespace") or module.get("name") or self.title

        write_section(self.output_dir, self.title, weight=self.weight)
        self.type_names = {d.get("name") for d in declarations if d.get("kind") in TYPE_KINDS and d.get("name")}

        types = sorted_declarations([d for d in declarations if d.get("kind") in TYPE_KINDS])
        enums = sorted_declarations([d for d in declarations if d.get("kind") == "enum"])
        variables = sorted_declarations([d for d in declarations if d.get("kind") == "variable"])
        functions = sorted_declarations([d for d in declarations if d.get("kind") == "function"])
        self.assign_page_weights(types, enums, variables, functions)

        if self.grouped_sidebar:
            self.write_group_sections(types, enums, variables, functions)

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
                self.detail_urls[fn["id"]] = self.top_level_detail_url(fn)

        self.write_overview(module_name, declarations, types, enums, variables, functions)
        for obj in types:
            self.write_type_page(obj, functions)
        for obj in enums:
            self.write_enum_page(obj)
        self.write_functions_page(functions)
        self.write_constants_page(variables)

    def assign_page_weights(self, types: list[dict[str, Any]], enums: list[dict[str, Any]], variables: list[dict[str, Any]], functions: list[dict[str, Any]]) -> None:
        if not self.grouped_sidebar:
            for index, obj in enumerate(sorted_declarations([*types, *enums]), start=1):
                self.page_weights[declaration_key(obj)] = index
            return

        groups = [
            [d for d in types if d.get("kind") == "class"],
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

    def write_group_sections(self, types: list[dict[str, Any]], enums: list[dict[str, Any]], variables: list[dict[str, Any]], functions: list[dict[str, Any]]) -> None:
        groups = {
            "class": [d for d in types if d.get("kind") == "class"],
            "struct": [d for d in types if d.get("kind") == "struct"],
            "interface": [d for d in types if d.get("kind") == "interface"],
            "enum": enums,
            "newtype": [d for d in types if d.get("kind") == "newtype"],
            "function": [d for d in functions if not receiver_type(d)],
            "variable": variables,
        }
        for index, (kind, path_name, title) in enumerate(API_GROUPS, start=1):
            items = sorted_declarations(groups[kind])
            content = self.declaration_rows(items, kind) + "\n" + self.footer()
            write_section(self.output_dir / path_name, title, weight=index + 1, content=content)

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
            ("Classes", [d for d in types if d.get("kind") == "class"], "class"),
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
                    f'<span class="api-index-main"><span class="api-signature">{declaration_signature(obj)}</span>'
                    f"{self.summary(obj)}</span></a>"
                )
            body.append("</div></section>")
        body.append(self.footer())
        write_page(self.output_dir / "overview.md", self.title, 1, "\n".join(body), nav_title="Overview")

    def write_type_page(self, obj: dict[str, Any], all_functions: list[dict[str, Any]]) -> None:
        name = display_name(obj)
        extensions = [fn for fn in all_functions if is_public_member(fn, None) and normalize_receiver_base(receiver_type(fn)) == obj.get("name")]
        lifecycle_members, fields, instance_members, static_members = split_members(obj, extensions)
        body = [
            f"<h1>{esc(name)}</h1>",
            "",
            f'<div class="api-declaration"><pre><code>{declaration_signature(obj)}</code></pre></div>',
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
        write_page(self.declaration_path(obj), name, self.declaration_weight(obj), "\n".join(filter(None, body)), nav_title=name)
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
            f'<div class="api-declaration"><pre><code>{declaration_signature(obj)}</code></pre></div>',
            self.metadata(obj),
            self.member_section("Values", obj, values, preserve_order=True),
            self.footer(),
        ]
        write_page(self.declaration_path(obj), name, self.declaration_weight(obj), "\n".join(filter(None, body)), nav_title=name)

    def write_functions_page(self, functions: list[dict[str, Any]]) -> None:
        free = [fn for fn in functions if not receiver_type(fn)]
        if not self.grouped_sidebar:
            body = ["<h1>Functions</h1>", "", self.declaration_rows(free, "function"), self.footer()]
            write_page(self.output_dir / "functions.md", "Functions", 9000, "\n".join(body), nav_hidden=True)
        for index, fn in enumerate(sorted_declarations(free), start=1):
            self.write_top_level_detail(fn, index)
        for item in collapse_overload_items([("function", fn, False, {}) for fn in sorted_declarations(free)]):
            if item[0] == "overload-group":
                self.write_top_level_overload_group_detail(item)

    def write_constants_page(self, variables: list[dict[str, Any]]) -> None:
        if not self.grouped_sidebar:
            body = ["<h1>Constants</h1>", "", self.declaration_rows(variables, "variable"), self.footer()]
            write_page(self.output_dir / "constants.md", "Constants", 9001, "\n".join(body), nav_hidden=True)
        for index, variable in enumerate(sorted_declarations(variables), start=1):
            self.write_constant_detail(variable, index)

    def write_member_detail(self, owner: dict[str, Any], item: tuple[str, dict[str, Any], bool, dict[str, Any]]) -> None:
        kind, obj, omit_receiver, options = item
        title = f"{owner.get('name', 'Type')}.{obj.get('name', 'member')}"
        body = [
            f"<h1>{esc(title)}</h1>",
            "",
            f'<p class="api-backlink"><a href="{attr(self.object_url(owner))}">Back to {esc(display_name(owner))}</a></p>',
            f'<div class="api-declaration"><pre><code>{self.detail_signature(kind, obj, omit_receiver, full_receiver=options.get("extension", False))}</code></pre></div>',
            self.metadata(obj),
        ]
        if kind == "function":
            body.append(self.parameters(obj.get("parameters") or [], omit_receiver, full_receiver=options.get("extension", False)))
        body.append(self.footer())
        write_page(self.member_detail_path(owner, obj), title, 10000, "\n".join(filter(None, body)), nav_hidden=True)

    def write_top_level_detail(self, fn: dict[str, Any], index: int = 10000) -> None:
        title = fn.get("name") or "Function"
        body = [
            f"<h1>{esc(title)}</h1>",
            "",
            f'<p class="api-backlink"><a href="{attr(self.prefix())}functions/">Back to Functions</a></p>',
            f'<div class="api-declaration"><pre><code>{self.detail_signature("function", fn, False, full_receiver=True)}</code></pre></div>',
            self.metadata(fn),
            self.parameters(fn.get("parameters") or []),
            self.footer(),
        ]
        write_page(self.top_level_detail_path(fn), title, index if self.grouped_sidebar else 10000, "\n".join(filter(None, body)), nav_title=signature_plain(fn, False), nav_hidden=True)

    def write_top_level_overload_group_detail(self, item: tuple[str, dict[str, Any], bool, dict[str, Any]]) -> None:
        _, group, _, _ = item
        title = group.get("name") or "Overloads"
        body = [
            f"<h1>{esc(title)}</h1>",
            "",
            f'<p class="api-backlink"><a href="{attr(self.prefix())}functions/">Back to Functions</a></p>',
            self.overloads(None, group),
            self.footer(),
        ]
        write_page(self.top_level_overload_group_path(group), title, 10000, "\n".join(filter(None, body)), nav_hidden=True)

    def write_constant_detail(self, variable: dict[str, Any], index: int = 10000) -> None:
        if not self.grouped_sidebar:
            return
        title = variable.get("name") or "Constant"
        body = [
            f"<h1>{esc(title)}</h1>",
            "",
            f'<p class="api-backlink"><a href="{attr(self.prefix())}constants/">Back to Constants</a></p>',
            f'<div class="api-declaration"><pre><code>{self.detail_signature("variable", variable, False)}</code></pre></div>',
            self.metadata(variable),
            self.footer(),
        ]
        write_page(self.constant_detail_path(variable), title, index, "\n".join(filter(None, body)), nav_hidden=True)

    def member_section(self, title: str, owner: dict[str, Any], items: list[tuple[str, dict[str, Any], bool, dict[str, Any]]], preserve_order: bool = False) -> str:
        if not items:
            return ""
        ordered_items = items if preserve_order else collapse_overload_items(sorted(items, key=member_sort_key))
        rows = [self.row(owner, item) for item in ordered_items]
        return f'<section class="api-member-section"><h2>{esc(title)}</h2><div class="api-member-list">' + "\n".join(rows) + "</div></section>"

    def declaration_rows(self, items: list[dict[str, Any]], kind: str) -> str:
        if not items:
            return '<p class="api-empty">No declarations.</p>'
        row_items = [("function", item, False, {}) for item in sorted_declarations(items)] if kind == "function" else [(kind, item, False, {}) for item in sorted_declarations(items)]
        rows = [self.row(None, item) for item in collapse_overload_items(row_items)]
        return '<div class="api-member-list api-declaration-list">' + "\n".join(rows) + "</div>"

    def row(self, owner: dict[str, Any] | None, item: tuple[str, dict[str, Any], bool, dict[str, Any]]) -> str:
        kind, obj, omit_receiver, options = item
        first = ""
        signature = ""
        if kind == "overload-group":
            first = esc(obj.get("returnType") or "void")
            signature = f"<strong>{esc(obj.get('name') or '')}</strong>()"
        elif kind == "function":
            first = esc(lifecycle_kind(obj) or obj.get("returnType") or "void")
            signature = member_signature(obj, omit_receiver, full_receiver=options.get("extension", False))
        elif kind in DECLARATION_KINDS:
            first = esc(kind)
            signature = declaration_signature(obj)
        elif kind == "field":
            first = esc(field_type_display(obj))
            signature = f"<strong>{esc(obj.get('name', ''))}</strong>{constant_value_display(obj)}"
        elif kind == "variable":
            first = esc(inline_constant_type(obj))
            signature = f"<strong>{esc(obj.get('name', ''))}</strong>{constant_value_display(obj)}"
        elif kind == "enum-value":
            signature = f"<strong>{esc(obj.get('name', ''))}</strong>{enum_value_display(obj)}"
        href = ""
        if owner and kind == "overload-group":
            href = self.overload_group_url(owner, obj)
        elif kind == "overload-group":
            href = self.top_level_overload_group_url(obj)
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
        for param in parameters:
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
                f'<div class="api-declaration"><pre><code>{self.detail_signature("function", obj, omit_receiver, full_receiver=overload.get("extension", False))}</code></pre></div>'
                f"{self.metadata(obj)}"
                f"{self.parameters(obj.get('parameters') or [], omit_receiver, show_title=False, full_receiver=overload.get('extension', False))}"
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
        write_page(self.overload_group_path(owner, group), title, 10000, "\n".join(filter(None, body)), nav_hidden=True)

    def metadata(self, obj: dict[str, Any], compact: bool = False, summary_only: bool = False) -> str:
        items = obj.get("metadata") or []
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
                section_blocks.append(f'<section class="api-doc-section"><h3>Example</h3><pre><code>{esc(example_text(str(raw_content or "")))}</code></pre></section>')
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

    def detail_signature(self, kind: str, obj: dict[str, Any], omit_receiver: bool, full_receiver: bool = False) -> str:
        if kind == "function":
            return esc((obj.get("returnType") or "void") + " " + signature_plain(obj, omit_receiver, full_receiver=full_receiver))
        if kind == "field":
            text = (field_type_display(obj) + " " + obj.get("name", "")).strip()
            if "value" in obj:
                text += " = " + str(obj["value"])
            return esc(text)
        if kind == "variable":
            text = (inline_constant_type(obj) + " " + obj.get("name", "")).strip()
            if "value" in obj:
                text += " = " + str(obj["value"])
            return esc(text)
        if kind == "enum-value":
            return esc(obj.get("name", "") + (" = " + str(obj["value"]) if "value" in obj else ""))
        return esc(obj.get("name", ""))

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
        prefix = self.prefix() + ("functions/" if self.grouped_sidebar else "")
        return prefix + "function-" + slug(signature_plain(fn, False)) + "/"

    def top_level_overload_group_url(self, group: dict[str, Any]) -> str:
        prefix = self.prefix() + ("functions/" if self.grouped_sidebar else "")
        return prefix + "function-" + slug(group.get("name") or "overloads") + "-overloads/"

    def constant_detail_url(self, variable: dict[str, Any]) -> str:
        return self.prefix() + "constants/" + slug(variable.get("name") or "constant") + "/"

    def member_detail_path(self, owner: dict[str, Any], member: dict[str, Any]) -> Path:
        return self.output_dir / f"{self.declaration_group_path(owner)}" / f"{detail_slug(owner, member)}.md" if self.grouped_sidebar else self.output_dir / f"{detail_slug(owner, member)}.md"

    def overload_group_path(self, owner: dict[str, Any], group: dict[str, Any]) -> Path:
        return self.output_dir / f"{self.declaration_group_path(owner)}" / f"{overload_group_slug(owner, group)}.md" if self.grouped_sidebar else self.output_dir / f"{overload_group_slug(owner, group)}.md"

    def top_level_detail_path(self, fn: dict[str, Any]) -> Path:
        return (self.output_dir / "functions" if self.grouped_sidebar else self.output_dir) / f"function-{slug(signature_plain(fn, False))}.md"

    def top_level_overload_group_path(self, group: dict[str, Any]) -> Path:
        return (self.output_dir / "functions" if self.grouped_sidebar else self.output_dir) / f"function-{slug(group.get('name') or 'overloads')}-overloads.md"

    def constant_detail_path(self, variable: dict[str, Any]) -> Path:
        return self.output_dir / "constants" / f"{slug(variable.get('name') or 'constant')}.md"

    def declaration_path(self, obj: dict[str, Any]) -> Path:
        group = self.declaration_group_path(obj)
        return (self.output_dir / group if group else self.output_dir) / f"{slug(display_name(obj))}.md"

    def declaration_group_path(self, obj: dict[str, Any]) -> str:
        if not self.grouped_sidebar:
            return ""
        info = API_GROUP_BY_KIND.get(obj.get("kind"))
        return info[0] if info else ""

    def declaration_weight(self, obj: dict[str, Any]) -> int:
        return self.page_weights.get(declaration_key(obj), 10000)

    def prefix(self) -> str:
        return f"/docs/{self.url_slug}/"

    def footer(self) -> str:
        return f'<p class="api-generated">Generated with campc {esc(self.campc_version)}.</p>'


def read_metadata(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != "camp.metadata":
        raise ValueError(f"{path} is not Camp metadata JSON")
    if data.get("version") != 1:
        raise ValueError(f"{path} has unsupported metadata version {data.get('version')}")
    return data


def read_text(path: Path, fallback: str) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else fallback


def write_section(path: Path, title: str, weight: int | None = None, content: str = "", nav_hidden: bool = False) -> None:
    path.mkdir(parents=True, exist_ok=True)
    lines = ["+++", f'title = "{toml(title)}"', 'sort_by = "weight"']
    if weight is not None:
        lines.append(f"weight = {weight}")
    lines.extend(['template = "docs_section.html"', 'page_template = "docs_page.html"'])
    if nav_hidden:
        lines.extend(["", "[extra]", "nav_hidden = true"])
    lines.extend(["+++", "", content])
    (path / "_index.md").write_text("\n".join(lines), encoding="utf-8")


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
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_placeholder(path: Path, title: str, weight: int, message: str) -> None:
    write_section(path, title, weight)
    write_page(path / "overview.md", title, 1, f"# {esc(title)}\n\n{esc(message)}\n", nav_title="Overview")


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=False)


def attr(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def toml(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def slug(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", str(value or "")).strip("-").lower() or "item"


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


def children_of(obj: dict[str, Any]) -> list[dict[str, Any]]:
    return [*(obj.get("fields") or []), *(obj.get("functions") or []), *(obj.get("values") or [])]


def public_children_of(obj: dict[str, Any]) -> list[dict[str, Any]]:
    return [child for child in children_of(obj) if is_public_member(child, obj)]


def is_public_declaration(obj: dict[str, Any]) -> bool:
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
            return f"newtype {obj.get('callableType')} {obj.get('returnType') or 'void'} {declaration_display_name(obj)}({params_plain(obj, omit_receiver, full_receiver=full_receiver)})"
        if obj.get("underlyingType"):
            return f"newtype {declaration_display_name(obj)}: {obj.get('underlyingType')}"
        return f"newtype {declaration_display_name(obj)}"
    return f"{declaration_display_name(obj)}({params_plain(obj, omit_receiver, full_receiver=full_receiver)})"


def params_plain(obj: dict[str, Any], omit_receiver: bool, full_receiver: bool = False) -> str:
    return ", ".join(filter(None, (param_plain(p, omit_receiver, full_receiver=full_receiver) for p in obj.get("parameters") or [])))


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
    return ", ".join(esc(text) for text in (param_plain(p, omit_receiver, full_receiver=full_receiver) for p in obj.get("parameters") or []) if text)


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


def declaration_signature(obj: dict[str, Any]) -> str:
    kind = obj.get("kind")
    if kind in {"class", "interface", "struct", "enum"}:
        parts: list[str] = []
        if obj.get("modifier"):
            parts.append(esc(obj["modifier"]))
        parts.extend([esc(kind), "<strong>" + esc(obj.get("name") or "") + declaration_type_parameters_display(obj) + "</strong>"])
        if obj.get("baseTypes"):
            parts.append(": " + ", ".join(esc(item) for item in obj["baseTypes"]))
        return " ".join(parts)
    if kind == "newtype":
        if obj.get("callableType"):
            return f"newtype {esc(obj.get('callableType'))} {esc(obj.get('returnType') or 'void')} <strong>{esc(obj.get('name') or '')}{declaration_type_parameters_display(obj)}</strong>({params_display(obj, False)})"
        if obj.get("underlyingType"):
            return f"newtype <strong>{esc(obj.get('name') or '')}{declaration_type_parameters_display(obj)}</strong>: {esc(obj.get('underlyingType'))}"
    if kind == "function":
        return f"{esc(obj.get('returnType') or 'void')} <strong>{esc(obj.get('name') or '')}</strong>{declaration_type_parameters_display(obj)}({params_display(obj, False)})"
    if kind == "variable":
        return f"{esc(inline_constant_type(obj))} <strong>{esc(obj.get('name') or '')}</strong>{constant_value_display(obj)}"
    return "<strong>" + esc(display_name(obj)) + "</strong>"


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


def split_members(obj: dict[str, Any], extensions: list[dict[str, Any]]) -> tuple[list[tuple[str, dict[str, Any], bool, dict[str, Any]]], list[tuple[str, dict[str, Any], bool, dict[str, Any]]], list[tuple[str, dict[str, Any], bool, dict[str, Any]]], list[tuple[str, dict[str, Any], bool, dict[str, Any]]]]:
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
    return rank, obj.get("name", "").lower(), signature_plain(obj, omit_receiver, full_receiver=options.get("extension", False)).lower()


def collapse_overload_items(items: list[tuple[str, dict[str, Any], bool, dict[str, Any]]]) -> list[tuple[str, dict[str, Any], bool, dict[str, Any]]]:
    result: list[tuple[str, dict[str, Any], bool, dict[str, Any]]] = []
    groups: dict[tuple[str, str, bool, bool], list[tuple[str, dict[str, Any], bool, dict[str, Any]]]] = {}
    group_order: list[tuple[str, str, bool, bool]] = []

    for item in items:
        kind, obj, omit_receiver, options = item
        if kind != "function" or not is_overload_function(obj):
            result.append(item)
            continue

        key = (
            obj.get("name") or "",
            obj.get("modifier") or "",
            omit_receiver,
            options.get("extension", False),
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
        return_types = {item[1].get("returnType") or "void" for item in group}
        result.append((
            "overload-group",
            {
                "kind": "function",
                "name": first.get("name") or "",
                "returnType": next(iter(return_types)) if len(return_types) == 1 else "overload",
                "modifier": first.get("modifier"),
                "static": first.get("static"),
                "overloadGroup": True,
                "overloads": [
                    {"member": item[1], "omitReceiver": item[2], "extension": item[3].get("extension", False)}
                    for item in sorted(group, key=member_sort_key)
                ],
                "metadata": first.get("metadata") or [],
            },
            group[0][2],
            {"extension": group[0][3].get("extension", False)},
        ))

    return sorted(result, key=member_sort_key)


def is_overload_function(obj: dict[str, Any]) -> bool:
    return any(parameter.get("overload") for parameter in obj.get("parameters") or [])


def detail_slug(owner: dict[str, Any], member: dict[str, Any]) -> str:
    return slug((owner.get("name") or "type") + "-" + signature_plain(member, False))


def overload_group_slug(owner: dict[str, Any], group: dict[str, Any]) -> str:
    return slug((owner.get("name") or "type") + "-" + (group.get("name") or "overloads") + "-overloads")
