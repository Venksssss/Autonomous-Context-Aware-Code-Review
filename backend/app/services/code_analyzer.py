"""
CodeAnalyzerService — Phase 2 Segment 2

Walks a Tree-sitter syntax tree for Python source files and deterministically
extracts:
  - class definitions  (with qualified names preserving nesting)
  - function definitions  (top-level and nested)
  - method definitions  (functions whose parent scope is a class)
  - function parameters
  - import statements  (import X / from X import Y / import X as Y)
  - function/method call sites

This module does NOT:
  - resolve cross-file symbol references   (Segment 3)
  - build call graphs or dependency graphs
  - interact with Git
  - use an LLM
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from app.schemas.code_parser import (
    CallSite,
    FileAnalysis,
    Import,
    Symbol,
    SymbolType,
)
from app.services.code_parser import CodeParserError, _count_error_nodes, CodeParserService


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _node_text(node, source: bytes) -> str:
    """Return the source text of a Tree-sitter node, decoded as UTF-8."""
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _first_named_child_of_type(node, type_: str):
    """Return the first named child with the given node type, or None."""
    for child in node.children:
        if child.type == type_:
            return child
    return None


def _extract_parameters(function_node, source: bytes) -> List[str]:
    """
    Extract parameter names from a function_definition or lambda node.
    Returns a list of plain parameter name strings (no type annotations, no defaults).
    """
    params = []
    parameters_node = _first_named_child_of_type(function_node, "parameters")
    if parameters_node is None:
        return params

    for child in parameters_node.children:
        ctype = child.type
        if ctype == "identifier":
            params.append(_node_text(child, source))
        elif ctype in ("typed_parameter", "default_parameter", "typed_default_parameter"):
            # First identifier child is the param name
            for sub in child.children:
                if sub.type == "identifier":
                    params.append(_node_text(sub, source))
                    break
        elif ctype in ("list_splat_pattern", "dictionary_splat_pattern",
                       "list_splat", "dictionary_splat"):
            # *args / **kwargs — grab the inner identifier
            for sub in child.children:
                if sub.type == "identifier":
                    params.append(_node_text(sub, source))
                    break

    return params


# ---------------------------------------------------------------------------
# Main traversal
# ---------------------------------------------------------------------------

def _traverse(
    node,
    source: bytes,
    file_path: str,
    symbols: List[Symbol],
    calls: List[CallSite],
    scope_stack: List[str],   # qualified name segments for the current scope
    class_stack: List[str],   # class names in scope (to distinguish method vs function)
) -> None:
    """
    Recursively walk the Tree-sitter CST and populate *symbols* and *calls*.

    scope_stack  tracks the dotted qualified name leading up to the current node.
    class_stack  tracks which enclosing scopes are classes (for method detection).
    """
    ntype = node.type

    # ---- class_definition ------------------------------------------------
    if ntype == "class_definition":
        name_node = _first_named_child_of_type(node, "identifier")
        if name_node is None:
            name_node = node.child_by_field_name("name")
        name = _node_text(name_node, source) if name_node else "<unknown>"
        qualified = ".".join(scope_stack + [name]) if scope_stack else name
        parent = ".".join(scope_stack) if scope_stack else None

        symbols.append(Symbol(
            name=name,
            qualified_name=qualified,
            symbol_type=SymbolType.class_,
            file_path=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            start_column=node.start_point[1],
            end_column=node.end_point[1],
            parent=parent,
        ))

        # Recurse into class body with updated stacks
        for child in node.children:
            _traverse(
                child, source, file_path, symbols, calls,
                scope_stack + [name],
                class_stack + [name],
            )
        return  # already recursed

    # ---- function_definition / decorated_definition ----------------------
    if ntype == "function_definition":
        name_node = _first_named_child_of_type(node, "identifier")
        if name_node is None:
            name_node = node.child_by_field_name("name")
        name = _node_text(name_node, source) if name_node else "<unknown>"
        qualified = ".".join(scope_stack + [name]) if scope_stack else name
        parent = ".".join(scope_stack) if scope_stack else None

        # A function is a method if the immediately enclosing scope is a class
        is_method = bool(class_stack)
        sym_type = SymbolType.method if is_method else SymbolType.function

        params = _extract_parameters(node, source)

        symbols.append(Symbol(
            name=name,
            qualified_name=qualified,
            symbol_type=sym_type,
            file_path=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            start_column=node.start_point[1],
            end_column=node.end_point[1],
            parent=parent,
            parameters=params if params else None,
        ))

        # Recurse into function body; nested functions are no longer in a class scope
        for child in node.children:
            _traverse(
                child, source, file_path, symbols, calls,
                scope_stack + [name],
                [],   # nested functions are NOT methods
            )
        return

    # ---- call expressions ------------------------------------------------
    if ntype == "call":
        func_node = node.child_by_field_name("function")
        if func_node is not None:
            call_name = _node_text(func_node, source).strip()
            # Limit to simple identifiers and attribute accesses
            if func_node.type in ("identifier", "attribute"):
                calls.append(CallSite(
                    name=call_name,
                    line=func_node.start_point[0] + 1,
                    column=func_node.start_point[1],
                    kind="call",
                ))

    # ---- default: recurse into all children ------------------------------
    for child in node.children:
        _traverse(child, source, file_path, symbols, calls, scope_stack, class_stack)


def _extract_imports(root_node, source: bytes) -> List[Import]:
    """
    Walk the top-level statements of a module node and extract imports.
    Handles:
      import os
      import numpy as np
      from app.auth import AuthService
      from typing import List, Optional
    """
    imports: List[Import] = []

    def walk(node):
        ntype = node.type

        if ntype == "import_statement":
            # import X  /  import X as Y
            for child in node.children:
                if child.type == "dotted_name":
                    imports.append(Import(
                        module=_node_text(child, source),
                        name=None,
                        alias=None,
                        line=node.start_point[0] + 1,
                    ))
                elif child.type == "aliased_import":
                    parts = [c for c in child.children if c.type in ("dotted_name", "identifier")]
                    module_name = _node_text(parts[0], source) if parts else ""
                    alias_name = _node_text(parts[-1], source) if len(parts) > 1 else None
                    imports.append(Import(
                        module=module_name,
                        name=None,
                        alias=alias_name,
                        line=node.start_point[0] + 1,
                    ))

        elif ntype == "import_from_statement":
            # from X import Y  /  from X import Y as Z
            module_node = node.child_by_field_name("module_name")
            module_name = _node_text(module_node, source) if module_node else ""
            module_start = module_node.start_byte if module_node else -1
            line = node.start_point[0] + 1

            for child in node.children:
                # Skip the module_name node by byte position (object identity is unreliable
                # because child_by_field_name and node.children return different wrappers)
                if module_node is not None and child.start_byte == module_start:
                    continue
                if child.type == "dotted_name":
                    imports.append(Import(module=module_name, name=_node_text(child, source), alias=None, line=line))
                elif child.type == "aliased_import":
                    parts = [c for c in child.children if c.type in ("dotted_name", "identifier")]
                    imp_name = _node_text(parts[0], source) if parts else ""
                    alias_name = _node_text(parts[-1], source) if len(parts) > 1 else None
                    imports.append(Import(module=module_name, name=imp_name, alias=alias_name, line=line))

        else:
            for child in node.children:
                walk(child)

    walk(root_node)
    return imports


# ---------------------------------------------------------------------------
# Public service
# ---------------------------------------------------------------------------

class CodeAnalyzerService:
    """
    Walks a Tree-sitter syntax tree produced by CodeParserService and extracts
    structured code symbols, import declarations, and call sites from a single
    Python source file.

    Responsibilities (this class):
        - class / function / method / nested symbol extraction
        - parameter name extraction
        - import statement extraction
        - call site extraction

    NOT responsible for:
        - cross-file symbol resolution  (Segment 3)
        - Git operations
        - LLM inference
    """

    @staticmethod
    def analyze_file(repository_path: str, file_path: str) -> FileAnalysis:
        """
        Parse and analyze *file_path* within *repository_path*.

        Returns a FileAnalysis Pydantic model containing all extracted symbols,
        imports, and call sites, plus error metadata.
        """
        tree, root_node, language_name, content = CodeParserService.get_tree(
            repository_path, file_path
        )

        # Unsupported file type
        if tree is None:
            return FileAnalysis(
                file_path=file_path,
                language=language_name,
                symbols=[],
                imports=[],
                calls=[],
                has_errors=False,
                error_count=0,
            )

        error_count = _count_error_nodes(root_node)
        has_errors = error_count > 0 or root_node.has_error

        symbols: List[Symbol] = []
        calls: List[CallSite] = []

        _traverse(root_node, content, file_path, symbols, calls, [], [])
        imports = _extract_imports(root_node, content)

        return FileAnalysis(
            file_path=file_path,
            language=language_name,
            symbols=symbols,
            imports=imports,
            calls=calls,
            has_errors=has_errors,
            error_count=error_count,
        )
