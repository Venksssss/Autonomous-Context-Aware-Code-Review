import os
from pathlib import Path

try:
    import tree_sitter_python
    from tree_sitter import Language, Parser
    
    PY_LANGUAGE = Language(tree_sitter_python.language())
except ImportError:
    PY_LANGUAGE = None

class CodeParserError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(self.message)

class CodeParserService:
    """
    A service class for parsing source code files into syntax trees using Tree-sitter.
    Ensures safe path boundaries within the target repository.
    """
    
    SUPPORTED_EXTENSIONS = {
        ".py": "python"
    }

    @staticmethod
    def parse_file(repository_path: str, file_path: str) -> dict:
        """
        Parses the specified file within the given repository.
        Returns a structured dictionary representing the parse result.
        """
        repo_path = Path(repository_path).resolve()
        
        if not repo_path.exists() or not repo_path.is_dir():
            raise CodeParserError("INVALID_REPOSITORY", "The specified repository path is invalid.")

        # Resolve the target file safely
        try:
            target_file = (repo_path / file_path).resolve()
        except Exception:
            raise CodeParserError("INVALID_FILE_PATH", "Could not resolve the file path.")

        # Ensure target_file is inside repo_path
        if not str(target_file).startswith(str(repo_path)):
            raise CodeParserError("PATH_TRAVERSAL_DETECTED", "The file path is outside the repository boundary.")
            
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
                "error_count": 0
            }

        language_name = CodeParserService.SUPPORTED_EXTENSIONS[ext]
        
        if language_name == "python" and PY_LANGUAGE is not None:
            parser = Parser(PY_LANGUAGE)
        else:
            raise CodeParserError("PARSER_NOT_INITIALIZED", f"Parser for {language_name} is not available.")

        # Try to read the file
        try:
            content = target_file.read_bytes()
        except Exception:
            raise CodeParserError("FILE_READ_ERROR", "Could not read the file contents.")
            
        tree = parser.parse(content)
        root_node = tree.root_node
        
        # Count error nodes recursively
        def count_errors(node) -> int:
            errs = 1 if node.type == "ERROR" or node.is_missing else 0
            for child in node.children:
                errs += count_errors(child)
            return errs
            
        error_count = count_errors(root_node)
        has_errors = error_count > 0 or root_node.has_error

        return {
            "path": file_path,
            "language": language_name,
            "parsed": True,
            "has_errors": has_errors,
            "root_node_type": root_node.type,
            "error_count": error_count
        }
