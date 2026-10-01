from pathlib import Path
from typing import Optional

try:
    import tree_sitter_python
    from tree_sitter import Language, Parser

    PY_LANGUAGE = Language(tree_sitter_python.language())
except ImportError:
    PY_LANGUAGE = None


class CodeParserError(Exception):
    """Structured error raised by code parsing operations."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(self.message)


def safe_resolve_file(repo_root: Path, file_path: str) -> Path:
    """
    Resolve *file_path* relative to *repo_root* and assert it stays within the repository.

    Uses pathlib.Path.is_relative_to (Python 3.9+) for reliable cross-platform
    boundary checking — avoids the fragile str.startswith approach.

    Raises CodeParserError on path-traversal or resolution failure.
    """
    try:
        resolved = (repo_root / file_path).resolve()
    except Exception:
        raise CodeParserError("INVALID_FILE_PATH", "Could not resolve the file path.")

    if not resolved.is_relative_to(repo_root):
        raise CodeParserError(
            "PATH_TRAVERSAL_DETECTED",
            "The file path is outside the repository boundary.",
        )
    return resolved


def _count_error_nodes(node) -> int:
    """Recursively count ERROR and MISSING nodes in a Tree-sitter tree."""
    count = 1 if (node.type == "ERROR" or node.is_missing) else 0
    for child in node.children:
        count += _count_error_nodes(child)
    return count


def _get_parser(language_name: str) -> "Parser":
    """Return a configured Tree-sitter Parser for the given language name."""
    if language_name == "python" and PY_LANGUAGE is not None:
        return Parser(PY_LANGUAGE)
    raise CodeParserError(
        "PARSER_NOT_INITIALIZED",
        f"Parser for '{language_name}' is not available.",
    )


class CodeParserService:
    """
    Parses source code files into Tree-sitter syntax trees.

    Responsibilities:
    - language detection by file extension
    - repository-boundary enforcement
    - tree creation and parse-error detection

    AST traversal and symbol extraction live in CodeAnalyzerService.
    """

    SUPPORTED_EXTENSIONS: dict[str, str] = {
        ".py": "python",
    }

    @staticmethod
    def parse_file(repository_path: str, file_path: str) -> dict:
        """
        Parse *file_path* (relative to *repository_path*) with Tree-sitter.

        Returns a dict compatible with ParseResponse:
            path, language, parsed, has_errors, root_node_type, error_count
        """
        repo_path = Path(repository_path).resolve()

        if not repo_path.exists() or not repo_path.is_dir():
            raise CodeParserError(
                "INVALID_REPOSITORY", "The specified repository path is invalid."
            )

        target_file = safe_resolve_file(repo_path, file_path)

        if not target_file.exists():
            raise CodeParserError("FILE_NOT_FOUND", "The specified file does not exist.")

        if not target_file.is_file():
            raise CodeParserError("NOT_A_FILE", "The specified path is not a file.")

        ext = target_file.suffix.lower()
        if ext not in CodeParserService.SUPPORTED_EXTENSIONS:
            return {
                "path": file_path,
                "language": "unsupported",
                "parsed": False,
                "has_errors": False,
                "root_node_type": None,
                "error_count": 0,
            }

        language_name = CodeParserService.SUPPORTED_EXTENSIONS[ext]
        parser = _get_parser(language_name)

        try:
            content = target_file.read_bytes()
        except Exception:
            raise CodeParserError("FILE_READ_ERROR", "Could not read the file contents.")

        tree = parser.parse(content)
        root_node = tree.root_node
        error_count = _count_error_nodes(root_node)
        has_errors = error_count > 0 or root_node.has_error

        return {
            "path": file_path,
            "language": language_name,
            "parsed": True,
            "has_errors": has_errors,
            "root_node_type": root_node.type,
            "error_count": error_count,
        }

    @staticmethod
    def get_tree(repository_path: str, file_path: str):
        """
        Return the raw Tree-sitter (tree, root_node, language_name, content) tuple
        for use by CodeAnalyzerService.  Performs the same validation as parse_file.
        """
        repo_path = Path(repository_path).resolve()

        if not repo_path.exists() or not repo_path.is_dir():
            raise CodeParserError(
                "INVALID_REPOSITORY", "The specified repository path is invalid."
            )

        target_file = safe_resolve_file(repo_path, file_path)

        if not target_file.exists():
            raise CodeParserError("FILE_NOT_FOUND", "The specified file does not exist.")

        if not target_file.is_file():
            raise CodeParserError("NOT_A_FILE", "The specified path is not a file.")

        ext = target_file.suffix.lower()
        if ext not in CodeParserService.SUPPORTED_EXTENSIONS:
            return None, None, "unsupported", b""

        language_name = CodeParserService.SUPPORTED_EXTENSIONS[ext]
        parser = _get_parser(language_name)

        try:
            content = target_file.read_bytes()
        except Exception:
            raise CodeParserError("FILE_READ_ERROR", "Could not read the file contents.")

        tree = parser.parse(content)
        return tree, tree.root_node, language_name, content
