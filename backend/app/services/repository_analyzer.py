import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set

from app.schemas.repository_analyzer import (
    RepoAnalyzeRequest, RepoContextRequest, Relationship,
    ResolvedSymbol, UnresolvedReference, RepositoryGraph,
    SymbolContext, ContextDefinition, ContextCall, ContextImport
)
from app.schemas.code_parser import FileAnalysis, Symbol as ParsedSymbol, Import, CallSite
from app.services.code_parser import safe_resolve_file, CodeParserError
from app.services.code_analyzer import CodeAnalyzerService

class RepositoryAnalyzerService:

    @staticmethod
    def _file_to_module(repo_path: Path, file_path: Path) -> str:
        """
        Convert repository-relative file path to a Python module name.
        E.g., app/auth.py -> app.auth
        app/__init__.py -> app
        """
        rel_path = file_path.relative_to(repo_path)
        parts = list(rel_path.parts)
        if not parts:
            return ""
        
        # Remove .py
        if parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        
        # Handle __init__
        if parts[-1] == "__init__":
            parts = parts[:-1]
            
        return ".".join(parts)

    @staticmethod
    def discover_python_files(repo_path: Path) -> List[Path]:
        """Discover all .py files in the repository, excluding common ignored dirs."""
        ignore_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", "env"}
        found_files = []
        for root, dirs, files in os.walk(repo_path):
            # Prune ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]
            
            for file in files:
                if file.endswith(".py"):
                    found_files.append(Path(root) / file)
        
        # Return sorted relative paths for determinism
        rel_paths = [f.relative_to(repo_path) for f in found_files]
        return sorted(rel_paths)

    @staticmethod
    def analyze_repository(repository_path: str) -> RepositoryGraph:
        repo_path = Path(repository_path).resolve()
        if not repo_path.exists() or not repo_path.is_dir():
            raise CodeParserError("INVALID_REPOSITORY", "The specified repository path is invalid.")

        file_paths = RepositoryAnalyzerService.discover_python_files(repo_path)
        
        files_analyzed = []
        all_symbols: List[ResolvedSymbol] = []
        all_relationships: List[Relationship] = []
        unresolved_refs: List[UnresolvedReference] = []
        
        file_analyses: Dict[str, FileAnalysis] = {}
        
        # 1. Parse and Analyze all files
        for rel_path in file_paths:
            file_str = rel_path.as_posix()
            try:
                analysis = CodeAnalyzerService.analyze_file(str(repo_path), file_str)
                file_analyses[file_str] = analysis
                files_analyzed.append(file_str)
            except Exception:
                continue
                
        # 2. Build Symbol Index
        # mapping: module -> name -> ResolvedSymbol
        module_exports: Dict[str, Dict[str, ResolvedSymbol]] = {}
        # mapping: globally unique name -> list of ResolvedSymbols (for ambiguous resolution)
        global_names: Dict[str, List[ResolvedSymbol]] = {}
        
        for file_str, analysis in file_analyses.items():
            module_name = RepositoryAnalyzerService._file_to_module(repo_path, repo_path / file_str)
            if module_name not in module_exports:
                module_exports[module_name] = {}
                
            for sym in analysis.symbols:
                sym_id = f"{module_name}::{sym.qualified_name}::{sym.file_path}"
                resolved_sym = ResolvedSymbol(
                    id=sym_id,
                    name=sym.name,
                    qualified_name=sym.qualified_name,
                    symbol_type=sym.symbol_type.value,
                    file_path=sym.file_path,
                    start_line=sym.start_line,
                    end_line=sym.end_line,
                    start_column=sym.start_column,
                    end_column=sym.end_column,
                    parent=sym.parent,
                    parameters=sym.parameters
                )
                all_symbols.append(resolved_sym)
                
                # Add to module exports
                # Note: We index by qualified name to allow importing specific classes/functions
                # We also index top-level names for standard imports
                module_exports[module_name][sym.qualified_name] = resolved_sym
                
                # For global uniqueness check
                if sym.name not in global_names:
                    global_names[sym.name] = []
                global_names[sym.name].append(resolved_sym)
                
                # defines relationship
                all_relationships.append(Relationship(
                    relationship_type="defines",
                    source_file=file_str,
                    source_symbol=None,
                    target_symbol=sym.qualified_name,
                    source_line=sym.start_line,
                    resolution_status="resolved"
                ))

        # 3. Resolve Imports & Calls
        for file_str, analysis in file_analyses.items():
            current_module = RepositoryAnalyzerService._file_to_module(repo_path, repo_path / file_str)
            
            # Map of local name -> (target_module, target_qualified_name)
            local_name_bindings: Dict[str, Tuple[str, Optional[str]]] = {}
            
            for imp in analysis.imports:
                target_module = imp.module
                imported_name = imp.name
                alias = imp.alias
                
                resolved = False
                target_symbol = None
                target_file = None
                
                if target_module in module_exports:
                    # The module exists in our repo
                    # Need to find a representative file for the module
                    # Just pick the file of the first exported symbol, or infer it
                    mod_syms = list(module_exports[target_module].values())
                    if mod_syms:
                        target_file = mod_syms[0].file_path
                    else:
                        # Fallback for empty modules
                        target_file = target_module.replace(".", "/") + ".py"
                        if target_file not in file_analyses:
                            target_file = target_module.replace(".", "/") + "/__init__.py"
                    
                    if imported_name:
                        if imported_name in module_exports[target_module]:
                            resolved = True
                            target_symbol = module_exports[target_module][imported_name].qualified_name
                            local_bind = alias if alias else imported_name
                            local_name_bindings[local_bind] = (target_module, target_symbol)
                    else:
                        resolved = True
                        local_bind = alias if alias else target_module.split(".")[-1]
                        local_name_bindings[local_bind] = (target_module, None)
                        
                if resolved:
                    all_relationships.append(Relationship(
                        relationship_type="imports",
                        source_file=file_str,
                        target_file=target_file,
                        target_symbol=target_symbol,
                        source_line=imp.line,
                        resolution_status="resolved"
                    ))
                else:
                    unresolved_refs.append(UnresolvedReference(
                        file_path=file_str,
                        name=imported_name if imported_name else target_module,
                        line=imp.line,
                        kind="import",
                        resolution_status="unresolved"
                    ))

            # Find the enclosing symbol for a given line to attribute calls properly
            def get_enclosing_symbol(line: int) -> Optional[str]:
                best_match = None
                for sym in analysis.symbols:
                    if sym.start_line <= line <= sym.end_line:
                        # For nested symbols, we want the tightest bound, but ordering or size check might be needed.
                        # Since we only really need *a* valid caller, the tightest bounds work.
                        if best_match is None:
                            best_match = sym
                        else:
                            size = sym.end_line - sym.start_line
                            best_size = best_match.end_line - best_match.start_line
                            if size < best_size:
                                best_match = sym
                return best_match.qualified_name if best_match else None

            for call in analysis.calls:
                call_name = call.name
                source_sym = get_enclosing_symbol(call.line)
                
                parts = call_name.split(".")
                base_name = parts[0]
                
                resolved = False
                ambiguous = False
                target_file = None
                target_symbol = None
                
                # 1. Is the base name defined in this file?
                local_candidates = [s for s in analysis.symbols if s.name == base_name]
                if local_candidates and len(parts) == 1:
                    resolved = True
                    target_file = file_str
                    target_symbol = local_candidates[0].qualified_name
                
                # 2. Is the base name imported?
                elif base_name in local_name_bindings:
                    t_mod, t_sym = local_name_bindings[base_name]
                    
                    if t_sym and len(parts) == 1:
                        resolved = True
                        target_symbol = t_sym
                    elif not t_sym and len(parts) > 1:
                        # it's a module import, and we're accessing an attribute
                        # e.g., import auth -> auth.verify_token
                        attr = ".".join(parts[1:])
                        if attr in module_exports.get(t_mod, {}):
                            resolved = True
                            target_symbol = module_exports[t_mod][attr].qualified_name
                    
                    if resolved and t_mod in module_exports:
                        if target_symbol in module_exports[t_mod]:
                            target_file = module_exports[t_mod][target_symbol].file_path
                        else:
                            mod_syms = list(module_exports[t_mod].values())
                            if mod_syms:
                                target_file = mod_syms[0].file_path

                # 3. Global uniqueness fallback (useful for class methods like `service.process`)
                elif len(parts) > 1:
                    attr = parts[-1]
                    if attr in global_names:
                        cands = global_names[attr]
                        if len(cands) == 1:
                            resolved = True
                            target_symbol = cands[0].qualified_name
                            target_file = cands[0].file_path
                        elif len(cands) > 1:
                            ambiguous = True
                else:
                    # Function call without dots, not local, not imported, check global
                    if base_name in global_names:
                        cands = global_names[base_name]
                        if len(cands) == 1:
                            resolved = True
                            target_symbol = cands[0].qualified_name
                            target_file = cands[0].file_path
                        elif len(cands) > 1:
                            ambiguous = True

                if resolved:
                    all_relationships.append(Relationship(
                        relationship_type="calls",
                        source_file=file_str,
                        target_file=target_file,
                        source_symbol=source_sym,
                        target_symbol=target_symbol,
                        source_line=call.line,
                        resolution_status="resolved"
                    ))
                elif ambiguous:
                    all_relationships.append(Relationship(
                        relationship_type="calls",
                        source_file=file_str,
                        source_symbol=source_sym,
                        target_symbol=call_name,
                        source_line=call.line,
                        resolution_status="ambiguous"
                    ))
                    unresolved_refs.append(UnresolvedReference(
                        file_path=file_str,
                        name=call_name,
                        line=call.line,
                        kind="call",
                        resolution_status="ambiguous"
                    ))
                else:
                    unresolved_refs.append(UnresolvedReference(
                        file_path=file_str,
                        name=call_name,
                        line=call.line,
                        kind="call",
                        resolution_status="unresolved"
                    ))

        return RepositoryGraph(
            repository_path=repository_path,
            files_analyzed=len(files_analyzed),
            symbols_count=len(all_symbols),
            relationships_count=len(all_relationships),
            files=files_analyzed,
            symbols=all_symbols,
            relationships=all_relationships,
            unresolved_references=unresolved_refs
        )

    @staticmethod
    def get_symbol_context(repository_path: str, symbol: str) -> SymbolContext:
        """
        Returns contextual information for a given symbol (qualified name) by traversing the graph.
        """
        graph = RepositoryAnalyzerService.analyze_repository(repository_path)
        
        definition = None
        for sym in graph.symbols:
            if sym.qualified_name == symbol:
                definition = ContextDefinition(
                    file=sym.file_path,
                    start_line=sym.start_line,
                    end_line=sym.end_line
                )
                break
                
        if not definition:
            raise CodeParserError("SYMBOL_NOT_FOUND", f"Symbol '{symbol}' not found in repository.")
            
        calls: List[ContextCall] = []
        called_by: List[ContextCall] = []
        imports: List[ContextImport] = []
        imported_by: List[ContextImport] = []
        
        # We need to map file imports to see what the symbol imports and who imports it
        for rel in graph.relationships:
            if rel.relationship_type == "calls":
                if rel.source_symbol == symbol and rel.target_symbol and rel.resolution_status == "resolved":
                    calls.append(ContextCall(
                        symbol=rel.target_symbol,
                        file=rel.target_file,
                        line=rel.source_line
                    ))
                elif rel.target_symbol == symbol and rel.resolution_status == "resolved":
                    called_by.append(ContextCall(
                        symbol=rel.source_symbol or "",
                        file=rel.source_file,
                        line=rel.source_line
                    ))
            elif rel.relationship_type == "imports":
                if rel.source_file == definition.file:
                    mod = RepositoryAnalyzerService._file_to_module(Path(repository_path), Path(repository_path) / (rel.target_file or ""))
                    imports.append(ContextImport(
                        module=mod,
                        name=rel.target_symbol,
                        file=rel.source_file,
                        line=rel.source_line
                    ))
                if rel.target_symbol == symbol or (rel.target_file == definition.file and not rel.target_symbol):
                    mod = RepositoryAnalyzerService._file_to_module(Path(repository_path), Path(repository_path) / (rel.target_file or ""))
                    imported_by.append(ContextImport(
                        module=mod,
                        name=rel.target_symbol,
                        file=rel.source_file,
                        line=rel.source_line
                    ))
                    
        return SymbolContext(
            symbol=symbol,
            definition=definition,
            calls=calls,
            called_by=called_by,
            imports=imports,
            imported_by=imported_by
        )
